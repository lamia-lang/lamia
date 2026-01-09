"""
Main hybrid syntax transformer for converting hybrid syntax AST nodes into executable Python code.

Handles transformation of:
- Functions with string commands
- Web command expressions  
- Parameter substitution
- Return type handling
"""

import ast
import re
from typing import Dict, Optional, List, Any

from ..detectors.llm_command_detector import LLMCommandDetector
from lamia.internal_types import (
    WEB_METHOD_TO_ACTION,
    SELECTOR_BASED_ACTIONS,
    BrowserActionType,
)


class HybridSyntaxTransformer(ast.NodeTransformer):
    """Transform hybrid syntax AST nodes into executable Python code.
    
    ARCHITECTURE: WEB CALL TRANSFORMATION FLOW
    ==========================================
    
    Web method calls (web.click(), web.type_text(), etc.) can appear in multiple contexts:
    1. Expression statements: `web.click(...)`  -> handled by visit_Expr
    2. Assignments: `result = web.click(...)`   -> handled by visit_Call  
    3. Conditions: `if web.click(...):`         -> handled by visit_Call
    
    ALL paths converge at _transform_web_call(), which is the SINGLE point where:
    - Starred arguments are processed (_inline_starred_literal_sequences)
    - WebCommand AST is created (_create_web_command_ast)
    
    This centralized approach prevents bugs from duplicate logic in multiple places.
    
    RETURN TYPE HANDLING: WHY THREE DIFFERENT STRATEGIES?
    ====================================================
    
    This class handles three distinct syntactic constructs that all use the arrow (->)
    notation but require different validation approaches. This is NOT a code smell - 
    each construct has fundamentally different semantics:
    
    1. FUNCTIONS: `def func() -> Type:`
       - Python natively supports this syntax
       - The function's return value IS the content to validate
       - Strategy: Extract Type from node.returns, pass to lamia.run(command, return_type=Type)
    
    2. EXPRESSIONS: `web.call(...) -> Type`  
       - Python does NOT support arrows on expressions
       - The expression result IS the content to validate
       - Strategy: Preprocess to __LAMIA_WEB_RT__(Type, web.call), transform to lamia.run(command, return_type=Type)
    
    3. SESSION BLOCKS: `with session(...) -> Type:`
       - Python does NOT support arrows on with statements
       - The session block does NOT produce content - it modifies page state
       - The arrow means "validate current page state as Type after block execution"
       - Strategy: Inject validation call at end of block: lamia.run(WebCommand(GET_TEXT, 'html'), return_type=Type)
    
    Each strategy is necessary because the SOURCE of validation content differs:
    - Functions/expressions: their own return value
    - Session blocks: the current page state after execution
    
    A universal approach would be incorrect because it would try to validate
    the wrong content for session blocks.
    """
    
    def __init__(self, lamia_var_name: str = 'lamia'):
        self.lamia_var_name = lamia_var_name
        self.detector = LLMCommandDetector()
    
    def transform_code(self, source_code: str, return_types: Dict[str, str] = None) -> str:
        """
        Transform hybrid syntax code into executable Python.
        
        This is the main public interface method.
        
        Args:
            source_code: Source code with hybrid syntax
            return_types: Extracted return types from preprocessing
            
        Returns:
            Transformed executable Python code
        """
        tree = ast.parse(source_code)
        
        # First pass: detect LLM commands
        self.detector.visit(tree)
        
        # Second pass: transform the AST
        transformed_tree = self.visit(tree)
        
        # Fix all missing AST metadata
        ast.fix_missing_locations(transformed_tree)
        
        # Convert back to source code
        return self._ast_to_source(transformed_tree)
    
    def visit_FunctionDef(self, node):
        """Transform synchronous function definitions with string commands."""
        return self._transform_function(node, is_async=False)
    
    def visit_AsyncFunctionDef(self, node):
        """Transform asynchronous function definitions with string commands."""
        return self._transform_function(node, is_async=True)
    
    def visit_Expr(self, node):
        """Handle expression statements, wrapping standalone web.method() calls in lamia.run()."""
        # Support preprocessed web.expr -> Type notation: __LAMIA_WEB_RT__(Type, web.call(...))
        if self._is_web_return_type_expression(node):
            return self._transform_web_return_type_expression(node)

        # Check if this expression is a web.method() call
        if self._is_web_method_call(node):
            return self._transform_web_expression(node)
        
        # Not a web expression, continue normal processing
        return self.generic_visit(node)
    
    def visit_Call(self, node):
        """Transform web method calls directly into WebCommand objects, wrapped in lamia.run()."""
        # Check if this is a web.method_name() call
        if self._is_web_call(node):
            # Transform to WebCommand (_transform_web_call handles starred arguments internally)
            web_command = self._transform_web_call(node)
            
            # Wrap in lamia.run() call
            return ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id=self.lamia_var_name, ctx=ast.Load()),
                    attr='run',
                    ctx=ast.Load()
                ),
                args=[web_command],
                keywords=[]
            )
        
        # Not a web call, continue normal processing
        return self.generic_visit(node)
    
    def _transform_function(self, node, is_async: bool):
        """Transform function based on whether it's async or sync."""
        if node.name in self.detector.llm_functions:
            return self._transform_llm_function(node, is_async)
        elif self._is_web_command_function(node):
            return self._transform_web_command_function(node, is_async)
        
        return self.generic_visit(node)
    
    def _transform_llm_function(self, node, is_async: bool):
        """Transform function with LLM string command."""
        func_info = self.detector.llm_functions[node.name]
        command = func_info['command']
        return_type = func_info['return_type']
        parameters = func_info['parameters']
        
        # Process command for parameter substitution
        processed_command = self._create_parameter_substitution_logic(command, parameters)
        
        # Generate lamia.run() call (works for both LLM and web commands)
        return self._create_lamia_call_function(node, processed_command, return_type, is_async)
    
    def _is_web_return_type_expression(self, node) -> bool:
        """Check if expression is preprocessed web return type expression."""
        return (
            isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == '__LAMIA_WEB_RT__'
            and len(node.value.args) == 2
        )
    
    def _transform_web_return_type_expression(self, node):
        """Transform preprocessed web return type expression."""
        return_type_node = node.value.args[0]
        web_call = node.value.args[1]
        # Transform the web call into WebCommand
        web_command = self._transform_web_call(web_call)
        lamia_call = ast.Call(
            func=ast.Attribute(
                value=ast.Name(id=self.lamia_var_name, ctx=ast.Load()),
                attr='run',
                ctx=ast.Load()
            ),
            args=[web_command],
            keywords=[ast.keyword(arg='return_type', value=return_type_node)]
        )
        return ast.Expr(value=lamia_call)
    
    def _is_web_method_call(self, node) -> bool:
        """Check if expression is a web method call."""
        return (isinstance(node.value, ast.Call) and
                isinstance(node.value.func, ast.Attribute) and
                isinstance(node.value.func.value, ast.Name) and
                node.value.func.value.id == 'web')
    
    def _transform_web_expression(self, node):
        """Transform web method expression."""
        # Transform the web call into WebCommand
        # (_transform_web_call handles starred arguments internally)
        web_command = self._transform_web_call(node.value)
        
        # Wrap in lamia.run() call
        lamia_call = ast.Call(
            func=ast.Attribute(
                value=ast.Name(id=self.lamia_var_name, ctx=ast.Load()),
                attr='run',
                ctx=ast.Load()
            ),
            args=[web_command],
            keywords=[]
        )
        
        # Return new expression statement with lamia.run()
        return ast.Expr(value=lamia_call)
    
    def _is_web_call(self, node) -> bool:
        """Check if call is a web method call."""
        return (isinstance(node.func, ast.Attribute) and
                isinstance(node.func.value, ast.Name) and
                node.func.value.id == 'web')
    
    def _is_web_command_function(self, node) -> bool:
        """Check if function returns a web command from method calls like web.type_text()."""
        # Check for function with just return statement
        if (len(node.body) == 1 and 
            isinstance(node.body[0], ast.Return) and
            isinstance(node.body[0].value, ast.Call)):
            
            call_node = node.body[0].value
            return self._is_web_call(call_node)
        
        # Check for function with docstring + return statement
        elif (len(node.body) == 2 and
              isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, (ast.Constant, ast.Str)) and
              isinstance(node.body[1], ast.Return) and
              isinstance(node.body[1].value, ast.Call)):
            
            call_node = node.body[1].value
            return self._is_web_call(call_node)
        
        return False
    
    def _transform_web_command_function(self, node, is_async: bool):
        """Transform function that returns web commands to execute via lamia.run()."""
        # Find the web command call - could be in body[0] or body[1] (after docstring)
        web_command_call = self._extract_web_command_call(node)
        
        # Transform web.method() to WebCommand AST
        web_command_ast = self._transform_web_call(web_command_call)
        
        # Build optional return_type argument from function annotation for engine validation
        return_type_kw = self._build_return_type_keyword(node)

        # Create lamia.run() call with the web command
        lamia_call = self._build_lamia_call(web_command_ast, return_type_kw, is_async)
        
        # Wrap in await if async
        if is_async:
            lamia_call = ast.Await(value=lamia_call)
            return self._build_async_function(node, lamia_call)
        else:
            return self._build_sync_function(node, lamia_call)
    
    def _extract_web_command_call(self, node):
        """Extract web command call from function body."""
        if (len(node.body) == 1 and isinstance(node.body[0], ast.Return)):
            return node.body[0].value
        elif (len(node.body) == 2 and isinstance(node.body[1], ast.Return)):
            return node.body[1].value
        return None
    
    def _build_return_type_keyword(self, node) -> Optional[ast.keyword]:
        """Build return type keyword argument from function annotation."""
        if getattr(node, 'returns', None) is not None:
            rt = node.returns
            if isinstance(rt, ast.Subscript):
                # Parametric type like HTML[Model]
                return_type_node = ast.Subscript(
                    value=rt.value,
                    slice=getattr(rt, 'slice', None) or rt.slice,
                    ctx=ast.Load(),
                )
            else:
                # Simple type like HTML / JSON, or qualified name
                return_type_node = rt
            return ast.keyword(arg='return_type', value=return_type_node)
        return None
    
    def _build_lamia_call(self, web_command_call, return_type_kw, is_async: bool) -> ast.Call:
        """Build lamia.run() or lamia.run_async() call."""
        return ast.Call(
            func=ast.Attribute(
                value=ast.Name(id=self.lamia_var_name, ctx=ast.Load()),
                attr='run_async' if is_async else 'run',
                ctx=ast.Load()
            ),
            args=[web_command_call],
            keywords=[return_type_kw] if return_type_kw is not None else []
        )
    
    def _build_async_function(self, node, lamia_call) -> ast.AsyncFunctionDef:
        """Build async function definition."""
        return ast.AsyncFunctionDef(
            name=node.name,
            args=node.args,
            body=[ast.Return(value=lamia_call)],
            decorator_list=node.decorator_list,
            returns=node.returns,
            type_comment=getattr(node, 'type_comment', None),
            lineno=getattr(node, 'lineno', 1),
            col_offset=getattr(node, 'col_offset', 0)
        )
    
    def _build_sync_function(self, node, lamia_call) -> ast.FunctionDef:
        """Build sync function definition."""
        return ast.FunctionDef(
            name=node.name,
            args=node.args,
            body=[ast.Return(value=lamia_call)],
            decorator_list=node.decorator_list,
            returns=node.returns,
            type_comment=getattr(node, 'type_comment', None),
            lineno=getattr(node, 'lineno', 1),
            col_offset=getattr(node, 'col_offset', 0)
        )
    
    def _transform_web_call(self, node):
        """
        Transform a web.method_name() call into WebCommand AST.
        
        This is the SINGLE point where all web calls are transformed, regardless of
        whether they appear as expression statements or within other expressions.
        We handle starred arguments here to avoid duplicating logic.
        """
        method_name = node.func.attr
        
        action_type = WEB_METHOD_TO_ACTION.get(method_name)
        if action_type:
            # Handle starred arguments (must be done before creating WebCommand)
            processed_args = self._inline_starred_literal_sequences(node.args)
            return self._create_web_command_ast(action_type, processed_args)
        
        # If method not recognized, return original node
        return node
    
    def _create_web_command_ast(self, action_type, args: list):
        """Create AST for WebCommand construction."""
        action_type_enum: BrowserActionType
        if isinstance(action_type, BrowserActionType):
            action_type_enum = action_type
        else:
            action_type_enum = BrowserActionType[str(action_type).upper()]
        action_attr_name = action_type_enum.name

        # Check if we have any Starred nodes in args (from *variable unpacking)
        has_starred = any(isinstance(arg, ast.Starred) for arg in args)
        
        if has_starred and len(args) == 2 and isinstance(args[0], ast.Subscript) and isinstance(args[1], ast.Starred):
            # web.method(*selectors) was expanded to (selectors[0], *selectors[1:])
            # We need to generate: WebCommand(..., selector=selectors[0], fallback_selectors=list(selectors[1:]))
            # But we can't use *selectors[1:] in a keyword argument, so we convert to list()
            
            keywords = [
                ast.keyword(
                    arg='action',
                    value=ast.Attribute(
                        value=ast.Name(id='WebActionType', ctx=ast.Load()),
                        attr=action_attr_name,
                        ctx=ast.Load()
                    )
                ),
                ast.keyword(arg='selector', value=args[0])
            ]
            
            # Convert *selectors[1:] to list(selectors[1:])
            if action_type_enum in SELECTOR_BASED_ACTIONS:
                keywords.append(
                    ast.keyword(
                        arg='fallback_selectors',
                        value=ast.Call(
                            func=ast.Name(id='list', ctx=ast.Load()),
                            args=[args[1].value],  # args[1] is Starred, .value is the Subscript
                            keywords=[]
                        )
                    )
                )
            
            return ast.Call(
                func=ast.Name(id='WebCommand', ctx=ast.Load()),
                args=[],
                keywords=keywords
            )
        
        # Normal case: no starred arguments
        # Create WebCommand(action=WebActionType.ACTION, ...)
        keywords = [
            ast.keyword(
                arg='action',
                value=ast.Attribute(
                    value=ast.Name(id='WebActionType', ctx=ast.Load()),
                    attr=action_attr_name,
                    ctx=ast.Load()
                )
            )
        ]
        
        # Add selector from first argument if present
        if len(args) > 0:
            keywords.append(
                ast.keyword(arg='selector', value=args[0])
            )
        
        # Add value from second argument if present (for type_text, select_option)
        if len(args) > 1:
            if action_type_enum in {BrowserActionType.TYPE, BrowserActionType.SELECT}:
                keywords.append(
                    ast.keyword(arg='value', value=args[1])
                )
                if len(args) > 2:
                    keywords.append(
                        ast.keyword(arg='fallback_selectors', value=ast.List(elts=args[2:], ctx=ast.Load()))
                    )
            elif action_type_enum in SELECTOR_BASED_ACTIONS:
                keywords.append(
                    ast.keyword(arg='fallback_selectors', value=ast.List(elts=args[1:], ctx=ast.Load()))
                )
        
        return ast.Call(
            func=ast.Name(id='WebCommand', ctx=ast.Load()),
            args=[],
            keywords=keywords
        )
    
    def _create_lamia_call_function(self, node, processed_command: ast.AST, return_type: Optional[Dict], is_async: bool):
        """Create a function node that calls lamia.run() or lamia.run_async()."""
        func_info = self.detector.llm_functions[node.name]
        parameters = func_info['parameters']
        
        # Build lamia call arguments
        args = [processed_command]
        keywords = []
        
        # Add models parameter from function signature if present
        models_keyword = self._build_models_keyword(parameters)
        if models_keyword:
            keywords.append(models_keyword)
        
        # Add return type parameter
        return_type_keyword = self._build_return_type_keyword_from_dict(return_type)
        if return_type_keyword:
            keywords.append(return_type_keyword)
        
        # Choose method and create call based on sync/async
        if is_async:
            return self._build_async_lamia_function(node, args, keywords)
        else:
            return self._build_sync_lamia_function(node, args, keywords)
    
    def _build_models_keyword(self, parameters: List[Dict]) -> Optional[ast.keyword]:
        """Build models keyword argument from function parameters."""
        for param in parameters:
            if param['name'] == 'models' and param.get('default') is not None:
                # Create models keyword argument with the actual default value
                default_value = param['default']
                if isinstance(default_value, list):
                    # Create list literal for multiple models
                    list_elements = [ast.Constant(value=model) for model in default_value]
                    value_node = ast.List(elts=list_elements, ctx=ast.Load())
                else:
                    # Single model string
                    value_node = ast.Constant(value=default_value)
                
                return ast.keyword(arg='models', value=value_node)
        return None
    
    def _build_return_type_keyword_from_dict(self, return_type: Optional[Dict]) -> Optional[ast.keyword]:
        """Build return type keyword from return type dictionary."""
        if return_type:
            # Add return_type parameter as actual type object
            if return_type['type'] == 'simple':
                return_type_node = ast.Name(id=return_type['base_type'], ctx=ast.Load())
            else:  # parametric
                return_type_node = ast.Subscript(
                    value=ast.Name(id=return_type['base_type'], ctx=ast.Load()),
                    slice=ast.Name(id=return_type['inner_type'], ctx=ast.Load()),
                    ctx=ast.Load()
                )
            
            return ast.keyword(arg='return_type', value=return_type_node)
        return None
    
    def _build_async_lamia_function(self, node, args, keywords) -> ast.AsyncFunctionDef:
        """Build async function with lamia.run_async() call."""
        lamia_call = ast.Await(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id=self.lamia_var_name, ctx=ast.Load()),
                    attr='run_async',
                    ctx=ast.Load()
                ),
                args=args,
                keywords=keywords
            )
        )
        return ast.AsyncFunctionDef(
            name=node.name,
            args=node.args,
            body=[ast.Return(value=lamia_call)],
            decorator_list=node.decorator_list,
            returns=node.returns,
            type_comment=getattr(node, 'type_comment', None),
            lineno=getattr(node, 'lineno', 1),
            col_offset=getattr(node, 'col_offset', 0)
        )
    
    def _build_sync_lamia_function(self, node, args, keywords) -> ast.FunctionDef:
        """Build sync function with lamia.run() call."""
        lamia_call = ast.Call(
            func=ast.Attribute(
                value=ast.Name(id=self.lamia_var_name, ctx=ast.Load()),
                attr='run',
                ctx=ast.Load()
            ),
            args=args,
            keywords=keywords
        )
        return ast.FunctionDef(
            name=node.name,
            args=node.args,
            body=[ast.Return(value=lamia_call)],
            decorator_list=node.decorator_list,
            returns=node.returns,
            type_comment=getattr(node, 'type_comment', None),
            lineno=getattr(node, 'lineno', 1),
            col_offset=getattr(node, 'col_offset', 0)
        )
    
    def _create_parameter_substitution_logic(self, command: str, parameters: list) -> ast.AST:
        """Create AST logic for parameter substitution in the command string."""
        if not parameters:
            # No parameters, return command as is
            return ast.Constant(value=command)
        
        # Check if command contains parameter placeholders
        param_placeholders = re.findall(r'\{(\w+)\}', command)
        if not param_placeholders:
            # No placeholders, return command as is
            return ast.Constant(value=command)
        
        # Create format call for parameter substitution
        format_kwargs = []
        for param in parameters:
            if param['name'] in param_placeholders:
                # Create serialization logic for this parameter
                serialized_param = self._create_param_serialization(param)
                format_kwargs.append(
                    ast.keyword(
                        arg=param['name'],
                        value=serialized_param
                    )
                )
        
        # Create command.format(...) call
        return ast.Call(
            func=ast.Attribute(
                value=ast.Constant(value=command),
                attr='format',
                ctx=ast.Load()
            ),
            args=[],
            keywords=format_kwargs
        )
    
    def _create_param_serialization(self, param: dict) -> ast.AST:
        """Create AST for serializing a parameter based on its type."""
        param_name = param['name']
        param_type = param.get('type')
        
        if not param_type or param_type in ['str', 'int', 'float', 'bool']:
            # Simple types, use string representation
            return ast.Call(
                func=ast.Name(id='str', ctx=ast.Load()),
                args=[ast.Name(id=param_name, ctx=ast.Load())],
                keywords=[]
            )
        else:
            # Complex types - use SmartTypeResolver to handle LamiaResult -> Model conversion
            resolved_param = ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id='SmartTypeResolver', ctx=ast.Load()),
                    attr='resolve_for_parameter',
                    ctx=ast.Load()
                ),
                args=[
                    ast.Name(id=param_name, ctx=ast.Load()),
                    ast.Constant(value=param_type)
                ],
                keywords=[]
            )
            
            # Then serialize the resolved object
            return ast.Call(
                func=ast.Attribute(
                    value=resolved_param,
                    attr='model_dump_json' if 'Model' in param_type else 'json',
                    ctx=ast.Load()
                ),
                args=[],
                keywords=[]
            )
    
    def _ast_to_source(self, tree: ast.AST) -> str:
        """Convert AST back to source code."""
        try:
            import astor
            return astor.to_source(tree)
        except ImportError:
            # Fallback for when astor is not available
            return ast.unparse(tree)
        
    def _inline_starred_literal_sequences(self, args: list) -> list:
        """
        Inline starred sequences into the argument list.
        
        Handles two cases:
        1. Starred literal sequences: web.click(*['a', 'b']) -> web.click('a', 'b')
        2. Starred variables: web.click(*selectors) -> Expand to: selectors[0], *selectors[1:]
        
        For starred variables, we expand them at compile time to:
        - First element as selector: selectors[0]
        - Rest as individual args: *selectors[1:]
        This way they get properly distributed to selector and fallback_selectors.
        """
        new_args = None

        for i, arg in enumerate(args):
            # Handle starred literal sequences (lists/tuples)
            if isinstance(arg, ast.Starred) and isinstance(arg.value, (ast.List, ast.Tuple)):
                if new_args is None:
                    new_args = list(args[:i])  # copy everything before the first starred literal
                new_args.extend(arg.value.elts)
            # Handle starred variables - expand to selectors[0], *selectors[1:]
            elif isinstance(arg, ast.Starred):
                if new_args is None:
                    new_args = list(args[:i])
                
                # Add selectors[0] as first argument
                new_args.append(
                    ast.Subscript(
                        value=arg.value,
                        slice=ast.Constant(value=0),
                        ctx=ast.Load()
                    )
                )
                
                # Add *selectors[1:] as remaining arguments
                new_args.append(
                    ast.Starred(
                        value=ast.Subscript(
                            value=arg.value,
                            slice=ast.Slice(lower=ast.Constant(value=1), upper=None, step=None),
                            ctx=ast.Load()
                        ),
                        ctx=ast.Load()
                    )
                )
            elif new_args is not None:
                new_args.append(arg)

        return new_args if new_args is not None else args
