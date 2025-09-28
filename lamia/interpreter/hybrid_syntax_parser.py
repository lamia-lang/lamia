"""
Hybrid Python syntax parser for LLM commands.

Handles parsing and AST transformation of hybrid syntax patterns:
1. def my_func() -> HTML[MyModel]: "command"  # Function with return type
2. def my_func(): "command"  # Function without return type  
3. async def my_func(): "command"  # Async function
4. with session() -> Type: ...  # Session with return type validation
5. "regular string"  # Outside functions, treated as normal Python string
"""

import ast
import re
from typing import Optional, Dict, Any


class WithReturnTypePreprocessor:
    """Preprocesses with session() -> Type: syntax before AST parsing."""
    
    def preprocess(self, source_code: str) -> tuple[str, Dict[str, str]]:
        """
        Extract return type annotations from with session() statements.
        
        Returns:
            tuple: (processed_source_code, extracted_return_types)
        """
        return_types = {}
        
        # Pattern to match: with session("name") -> Type:
        session_pattern = r'(\s*)(with\s+session\([^)]+\))\s*->\s*([^:]+):'
        
        def replace_with_statement(match):
            indent = match.group(1)
            with_part = match.group(2)
            return_type = match.group(3).strip()
            
            # Generate a unique key for this with statement
            import hashlib
            key = hashlib.md5(f"{with_part}_{return_type}".encode()).hexdigest()[:8]
            return_types[key] = return_type
            
            # Replace with standard with statement + comment marker
            return f"{indent}{with_part}:  # LAMIA_WITH_RETURN_TYPE_{key}"
        
        processed_code = re.sub(session_pattern, replace_with_statement, source_code)

        # Pattern to match: web.method(args) -> Type at expression level
        # We rewrite to __LAMIA_WEB_RT__(Type, web.method(args)) so the transformer can handle it
        web_expr_pattern = r'(\s*)(web\.[\w_]+\([^\n]*?\))\s*->\s*([^\n]+)'
        
        def replace_web_expr(match):
            indent = match.group(1)
            call_part = match.group(2)
            return_type = match.group(3).strip()
            # Keep order: __LAMIA_WEB_RT__(Type, web.call(...))
            return f"{indent}__LAMIA_WEB_RT__({return_type}, {call_part})"
        
        processed_code = re.sub(web_expr_pattern, replace_web_expr, processed_code)
        
        return processed_code, return_types


class LLMCommandDetector(ast.NodeVisitor):
    """Detects string literal patterns in function bodies that should be LLM commands."""
    
    def __init__(self):
        self.llm_functions = {}
    
    def visit_FunctionDef(self, node):
        """Handle function definitions that might contain string LLM commands."""
        self._process_function(node, is_async=False)
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node):
        """Handle async function definitions that might contain string LLM commands."""
        self._process_function(node, is_async=True)
        self.generic_visit(node)
    
    def _process_function(self, node, is_async: bool):
        """Process both sync and async function definitions."""
        command = None
        
        # Check if function body contains a single string literal (expression statement)
        if (len(node.body) == 1 and 
            isinstance(node.body[0], ast.Expr) and
            isinstance(node.body[0].value, (ast.Constant, ast.Str))):
            
            # Single string literal case
            string_node = node.body[0].value
            if isinstance(string_node, ast.Constant) and isinstance(string_node.value, str):
                command = string_node.value
            elif isinstance(string_node, ast.Str):  # For older Python versions
                command = string_node.s
                
        # Check if function has docstring + string literal (2 statements)
        elif (len(node.body) == 2 and
              isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, (ast.Constant, ast.Str)) and
              isinstance(node.body[1], ast.Expr) and isinstance(node.body[1].value, (ast.Constant, ast.Str))):
            
            # Docstring + command case - use the second string as the command
            string_node = node.body[1].value  
            if isinstance(string_node, ast.Constant) and isinstance(string_node.value, str):
                command = string_node.value
            elif isinstance(string_node, ast.Str):  # For older Python versions
                command = string_node.s
        
        if command is None:
            # Not a pattern we recognize, skip
            return
            
        return_type = self._extract_return_type(node)
        parameters = self._extract_parameters(node)
        
        self.llm_functions[node.name] = {
            'type': 'function_with_string_command',
            'command': command,
            'return_type': return_type,
            'parameters': parameters,
            'is_async': is_async,
            'node': node
        }
    
    def _extract_return_type(self, func_node):
        """Extract return type annotation from function node."""
        if func_node.returns:
            return_type_info = self._ast_to_type_string(func_node.returns)
            # Check if it's a parametric type like HTML[MyModel]
            if '[' in return_type_info and ']' in return_type_info:
                base_type = return_type_info.split('[')[0]
                inner_type = return_type_info.split('[')[1].rstrip(']')
                return {
                    'type': 'parametric',
                    'base_type': base_type,
                    'inner_type': inner_type,
                    'full_type': return_type_info
                }
            else:
                return {
                    'type': 'simple',
                    'base_type': return_type_info,
                    'full_type': return_type_info
                }
        return None
    
    def _extract_parameters(self, func_node):
        """Extract function parameters with their type annotations and default values."""
        parameters = []
        defaults = func_node.args.defaults
        
        # Calculate offset for defaults (defaults align with the last N parameters)
        defaults_offset = len(func_node.args.args) - len(defaults)
        
        for i, arg in enumerate(func_node.args.args):
            param_info = {
                'name': arg.arg,
                'type': None,
                'default': None
            }
            
            if arg.annotation:
                param_info['type'] = self._ast_to_type_string(arg.annotation)
            
            # Check if this parameter has a default value
            if i >= defaults_offset:
                default_index = i - defaults_offset
                param_info['default'] = self._ast_node_to_value(defaults[default_index])
            
            parameters.append(param_info)
        return parameters
    
    def _ast_to_type_string(self, ast_node):
        """Convert AST type annotation to string representation."""
        if isinstance(ast_node, ast.Name):
            return ast_node.id
        elif isinstance(ast_node, ast.Subscript):
            # Handle Generic[Args] syntax like HTML[MyModel]
            base = self._ast_to_type_string(ast_node.value)
            if hasattr(ast_node.slice, 'value'):
                arg = self._ast_to_type_string(ast_node.slice.value)
            else:
                arg = self._ast_to_type_string(ast_node.slice)
            return f"{base}[{arg}]"
        elif isinstance(ast_node, ast.Attribute):
            # Handle module.Type syntax
            return f"{self._ast_to_type_string(ast_node.value)}.{ast_node.attr}"
        return str(ast_node)
    
    def _ast_node_to_value(self, node):
        """Convert AST node to value for models parameter (string or list)."""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Str):  # For older Python versions
            return node.s
        elif isinstance(node, ast.List):
            return [self._ast_node_to_value(item) for item in node.elts]
        else:
            # For unsupported types, return None
            return None



class SessionWithTransformer(ast.NodeTransformer):
    """Transforms with session() statements to handle SessionSkipException and return type validation."""
    
    def __init__(self, return_types: Dict[str, str] = None):
        self.return_types = return_types or {}
    
    def visit_With(self, node):
        """Wrap with session() in try-catch to handle skipping and add validation if return type specified."""
        # Check if this is a with session() statement
        for item in node.items:
            if (isinstance(item.context_expr, ast.Call) and
                isinstance(item.context_expr.func, ast.Name) and
                item.context_expr.func.id == 'session'):
                
                # Check for return type annotation based on line number
                return_type_key = None
                validation_call = None
                
                # Skip the complex comment matching for now
                
                # Check if we have a return type for this session
                if not validation_call and self.return_types:
                    # Use the single return type (simplified - only one return type supported)
                    return_type = next(iter(self.return_types.values()))
                    validation_call = self._create_web_validation_call(return_type)
                
                # Create the modified with statement body
                modified_body = list(node.body)
                
                # Add validation call at the END if return type is specified
                # This ensures validation happens before session.__exit__ is called
                if validation_call:
                    modified_body.append(validation_call)
                
                # Create new with statement with modified body
                modified_with = ast.With(
                    items=node.items,
                    body=modified_body,
                    lineno=getattr(node, 'lineno', 1),
                    col_offset=getattr(node, 'col_offset', 0)
                )
                
                # Wrap the with statement in try-catch
                try_node = ast.Try(
                    body=[modified_with],
                    handlers=[
                        ast.ExceptHandler(
                            type=ast.Name(id='SessionSkipException', ctx=ast.Load()),
                            name='e',
                            body=[
                                ast.Expr(
                                    value=ast.Call(
                                        func=ast.Attribute(
                                            value=ast.Name(id='logger', ctx=ast.Load()),
                                            attr='info',
                                            ctx=ast.Load()
                                        ),
                                        args=[
                                            ast.Call(
                                                func=ast.Name(id='str', ctx=ast.Load()),
                                                args=[ast.Name(id='e', ctx=ast.Load())],
                                                keywords=[]
                                            )
                                        ],
                                        keywords=[]
                                    )
                                )
                            ],
                            lineno=getattr(node, 'lineno', 1),
                            col_offset=getattr(node, 'col_offset', 0)
                        )
                    ],
                    orelse=[],
                    finalbody=[],
                    lineno=getattr(node, 'lineno', 1),
                    col_offset=getattr(node, 'col_offset', 0)
                )
                return try_node
        
        # Not a session with statement, continue normal processing
        return self.generic_visit(node)

    def _create_web_validation_call(self, return_type: str) -> ast.stmt:
        """Create: lamia.run(WebCommand(...), return_type=Type) to validate current page.

        RETURN TYPE HANDLING STRATEGY #3: Session Block Validation
        ========================================================
        
        This method handles the special case of `with session(...) -> Type:` blocks.
        Unlike functions or expressions, a session block doesn't itself produce content
        to validate. The arrow means "after this block finishes, validate the current 
        page state as Type". 
        
        We inject a GET_TEXT command at the end of the session block to explicitly 
        trigger the engine's validation pipeline for the session's return type.
        This ensures the page content after session execution matches the expected Type.

        We validate by fetching page text via a simple GET_TEXT on the root 'html' element.
        """
        # Build return_type AST
        rt_node: ast.AST
        if '[' in return_type and return_type.endswith(']'):
            base = return_type.split('[', 1)[0]
            inner = return_type[len(base)+1:-1]
            rt_node = ast.Subscript(
                value=ast.Name(id=base, ctx=ast.Load()),
                slice=ast.Name(id=inner, ctx=ast.Load()),
                ctx=ast.Load(),
            )
        else:
            rt_node = ast.Name(id=return_type, ctx=ast.Load())

        # Build WebCommand(action=WebActionType.GET_TEXT, selector='html')
        web_command_call = ast.Call(
            func=ast.Name(id='WebCommand', ctx=ast.Load()),
            args=[],
            keywords=[
                ast.keyword(
                    arg='action',
                    value=ast.Attribute(
                        value=ast.Name(id='WebActionType', ctx=ast.Load()),
                        attr='GET_TEXT',
                        ctx=ast.Load()
                    )
                ),
                ast.keyword(
                    arg='selector',
                    value=ast.Constant(value='html')
                )
            ]
        )

        # Build lamia.run(WebCommand(...), return_type=rt_node)
        lamia_run_call = ast.Call(
            func=ast.Attribute(
                value=ast.Name(id='lamia', ctx=ast.Load()),
                attr='run',
                ctx=ast.Load()
            ),
            args=[web_command_call],
            keywords=[ast.keyword(arg='return_type', value=rt_node)]
        )

        return ast.Expr(value=lamia_run_call)


class HybridSyntaxTransformer(ast.NodeTransformer):
    """Transform hybrid syntax AST nodes into executable Python code.
    
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
        """Transform hybrid syntax code into executable Python."""
        tree = ast.parse(source_code)
        
        # First pass: detect LLM commands
        self.detector.visit(tree)
        
        # Second pass: handle session with statements with return types
        session_transformer = SessionWithTransformer(return_types)
        tree = session_transformer.visit(tree)
        
        # Third pass: transform the AST
        transformed_tree = self.visit(tree)
        
        # Fix all missing AST metadata
        ast.fix_missing_locations(transformed_tree)
        
        # Convert back to source code
        try:
            import astor
            return astor.to_source(transformed_tree)
        except ImportError:
            # Fallback for when astor is not available
            return ast.unparse(transformed_tree)
    
    def visit_FunctionDef(self, node):
        """Transform synchronous function definitions with string commands."""
        return self._transform_function(node, is_async=False)
    
    def visit_AsyncFunctionDef(self, node):
        """Transform asynchronous function definitions with string commands."""
        return self._transform_function(node, is_async=True)
    
    def _transform_function(self, node, is_async: bool):
        """Transform function based on whether it's async or sync."""
        if node.name in self.detector.llm_functions:
            func_info = self.detector.llm_functions[node.name]
            command = func_info['command']
            return_type = func_info['return_type']
            parameters = func_info['parameters']
            
            # Process command for parameter substitution
            processed_command = self._create_parameter_substitution_logic(command, parameters)
            
            # Generate lamia.run() call (works for both LLM and web commands)
            return self._create_lamia_call_function(node, processed_command, return_type, is_async)
        
        # Check if function returns a web command
        elif self._is_web_command_function(node):
            return self._transform_web_command_function(node, is_async)
        
        return self.generic_visit(node)
    
    def _is_web_command_function(self, node):
        """Check if function returns a web command from method calls like web.type_text()."""
        # Check for function with just return statement
        if (len(node.body) == 1 and 
            isinstance(node.body[0], ast.Return) and
            isinstance(node.body[0].value, ast.Call)):
            
            call_node = node.body[0].value
            # Check if it's a web.method_name() call
            if (isinstance(call_node.func, ast.Attribute) and 
                isinstance(call_node.func.value, ast.Name) and
                call_node.func.value.id == 'web'):
                return True
        
        # Check for function with docstring + return statement
        elif (len(node.body) == 2 and
              isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, (ast.Constant, ast.Str)) and
              isinstance(node.body[1], ast.Return) and
              isinstance(node.body[1].value, ast.Call)):
            
            call_node = node.body[1].value
            # Check if it's a web.method_name() call
            if (isinstance(call_node.func, ast.Attribute) and 
                isinstance(call_node.func.value, ast.Name) and
                call_node.func.value.id == 'web'):
                return True
        
        return False
    
    def _transform_web_command_function(self, node, is_async: bool):
        """Transform function that returns web commands to execute via lamia.run()."""
        # Find the web command call - could be in body[0] or body[1] (after docstring)
        web_command_call = None
        if (len(node.body) == 1 and isinstance(node.body[0], ast.Return)):
            web_command_call = node.body[0].value
        elif (len(node.body) == 2 and isinstance(node.body[1], ast.Return)):
            web_command_call = node.body[1].value
        
        # Build optional return_type argument from function annotation for engine validation
        return_type_kw = None
        if getattr(node, 'returns', None) is not None:
            # Create AST node for return type similar to _create_lamia_call_function
            rt = node.returns
            return_type_node: ast.AST
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
            return_type_kw = ast.keyword(arg='return_type', value=return_type_node)

        # Create lamia.run() call with the web command
        lamia_call = ast.Call(
            func=ast.Attribute(
                value=ast.Name(id=self.lamia_var_name, ctx=ast.Load()),
                attr='run_async' if is_async else 'run',
                ctx=ast.Load()
            ),
            args=[web_command_call],
            keywords=[return_type_kw] if return_type_kw is not None else []
        )
        
        # Wrap in await if async
        if is_async:
            lamia_call = ast.Await(value=lamia_call)
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
        else:
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
    
    def visit_Expr(self, node):
        """Handle expression statements, wrapping standalone web.method() calls in lamia.run().
        
        RETURN TYPE HANDLING STRATEGY #2: Web Expression Validation
        ==========================================================
        
        This method handles `web.call(...) -> Type` expressions. Python doesn't 
        natively support arrow syntax on expressions, so we preprocess these into
        `__LAMIA_WEB_RT__(Type, web.call(...))` tokens and transform them here.
        
        The web expression itself produces the content to validate, so we pass
        the return_type directly to lamia.run(web_command, return_type=Type).
        """
        # Support preprocessed web.expr -> Type notation: __LAMIA_WEB_RT__(Type, web.call(...))
        if (
            isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == '__LAMIA_WEB_RT__'
            and len(node.value.args) == 2
        ):
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

        # Check if this expression is a web.method() call
        if (isinstance(node.value, ast.Call) and
            isinstance(node.value.func, ast.Attribute) and
            isinstance(node.value.func.value, ast.Name) and
            node.value.func.value.id == 'web'):
            
            # Transform the web call into WebCommand
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
        
        # Not a web expression, continue normal processing
        return self.generic_visit(node)
    
    def visit_Call(self, node):
        """Transform web method calls directly into WebCommand objects."""
        # Check if this is a web.method_name() call
        if (isinstance(node.func, ast.Attribute) and
            isinstance(node.func.value, ast.Name) and
            node.func.value.id == 'web'):
            
            return self._transform_web_call(node)
        
        # Not a web call, continue normal processing
        return self.generic_visit(node)
    
    def _transform_web_call(self, node):
        """Transform a web.method_name() call into WebCommand AST."""
        method_name = node.func.attr
        
        # Transform based on web method
        if method_name == 'click':
            return self._create_web_command_ast('CLICK', node.args)
        elif method_name == 'type_text':
            return self._create_web_command_ast('TYPE', node.args)
        elif method_name == 'wait_for':
            return self._create_web_command_ast('WAIT', node.args)
        elif method_name == 'get_text':
            return self._create_web_command_ast('GET_TEXT', node.args)
        elif method_name == 'hover':
            return self._create_web_command_ast('HOVER', node.args)
        elif method_name == 'scroll_to':
            return self._create_web_command_ast('SCROLL', node.args)
        elif method_name == 'select_option':
            return self._create_web_command_ast('SELECT', node.args)
        elif method_name == 'submit_form':
            return self._create_web_command_ast('SUBMIT', node.args)
        elif method_name == 'screenshot':
            return self._create_web_command_ast('SCREENSHOT', node.args)
        elif method_name == 'is_visible':
            return self._create_web_command_ast('IS_VISIBLE', node.args)
        elif method_name == 'is_enabled':
            return self._create_web_command_ast('IS_ENABLED', node.args)
        
        # If method not recognized, return original node
        return node
    
    def _create_web_command_ast(self, action_type: str, args: list):
        """Create AST for WebCommand construction."""
        # Create WebCommand(action=WebActionType.ACTION, ...)
        keywords = [
            ast.keyword(
                arg='action',
                value=ast.Attribute(
                    value=ast.Name(id='WebActionType', ctx=ast.Load()),
                    attr=action_type,
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
        if len(args) > 1 and action_type in ['TYPE', 'SELECT']:
            keywords.append(
                ast.keyword(arg='value', value=args[1])
            )
        
        # Add timeout from keyword args or last positional arg
        # (This is simplified - real implementation would need to parse all args properly)
        
        return ast.Call(
            func=ast.Name(id='WebCommand', ctx=ast.Load()),
            args=[],
            keywords=keywords
        )
    
    def _create_lamia_call_function(self, node, processed_command: ast.AST, return_type: Optional[Dict], is_async: bool):
        """Create a function node that calls lamia.run() or lamia.run_async().
        
        RETURN TYPE HANDLING STRATEGY #1: Function Return Type Validation
        ================================================================
        
        This method handles `def func() -> Type:` functions. Python natively supports
        return type annotations, so we extract the Type from node.returns and pass it
        to lamia.run/lamia.run_async along with the WebCommand the function produces.
        
        The function's return statement produces the content to validate, so we pass
        the return_type directly to the lamia call for engine validation.
        """
        func_info = self.detector.llm_functions[node.name]
        parameters = func_info['parameters']
        
        # Build lamia call arguments
        args = [processed_command]
        keywords = []
        
        # Add models parameter from function signature if present
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
                
                keywords.append(
                    ast.keyword(
                        arg='models',
                        value=value_node
                    )
                )
                break  # Only one models parameter expected
        
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
            
            keywords.append(
                ast.keyword(
                    arg='return_type',
                    value=return_type_node
                )
            )
        
        # Choose method and create call based on sync/async
        if is_async:
            # async def -> return await lamia.run_async(...)
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
        else:
            # def -> return lamia.run(...)
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
        
        # Create f-string or format call for parameter substitution
        # For simplicity, we'll use string format method
        # command.format(param1=param1_serialized, param2=param2_serialized, ...)
        
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
            # Create: SmartTypeResolver.resolve_for_parameter(param_name, param_type).model_dump_json()
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


class HybridSyntaxParser:
    """Main interface for parsing and transforming hybrid syntax code."""
    
    def __init__(self, lamia_var_name: str = 'lamia'):
        self.lamia_var_name = lamia_var_name
        self.transformer = HybridSyntaxTransformer(lamia_var_name)
    
    def parse(self, source_code: str) -> Dict[str, Any]:
        """Parse hybrid syntax and return information about LLM commands."""
        # Preprocess with session return types
        preprocessor = WithReturnTypePreprocessor()
        processed_code, return_types = preprocessor.preprocess(source_code)
        
        detector = LLMCommandDetector()
        tree = ast.parse(processed_code)
        detector.visit(tree)
        
        return {
            'llm_functions': detector.llm_functions,
            'with_return_types': return_types
        }
    
    def transform(self, source_code: str) -> str:
        """Transform hybrid syntax code into executable Python."""
        # Preprocess with session return types
        preprocessor = WithReturnTypePreprocessor()
        processed_code, return_types = preprocessor.preprocess(source_code)
        
        # Apply the hybrid syntax transformer with return types
        transformed_code = self.transformer.transform_code(processed_code, return_types)
        
        return transformed_code