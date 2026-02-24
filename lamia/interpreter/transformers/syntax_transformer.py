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
from typing import Dict, Optional, List, Any, Union, Set

from ..detectors.llm_command_detector import (
    LLMCommandDetector,
    LLMFunctionInfo,
    FunctionParameter,
    ReturnType,
    SimpleReturnType,
    ParametricReturnType,
    FileWriteReturnType,
)
from lamia.internal_types import (
    WEB_METHOD_TO_ACTION,
    SELECTOR_BASED_ACTIONS,
    VALUE_SECOND_ARG_ACTIONS,
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

        # Support preprocessed "prompt" -> File(...) notation: __LAMIA_FILE_WRITE__(prompt, File(...))
        if self._is_file_write_expression(node):
            return self._transform_file_write_expression(node)

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

        # Process command for parameter substitution
        processed_command = self._create_parameter_substitution_logic(
            func_info.command, func_info.parameters,
        )
        
        # Generate lamia.run() call (works for both LLM and web commands)
        return self._create_lamia_call_function(
            node, processed_command, func_info.return_type, is_async,
        )

    
    def _is_web_return_type_expression(self, node) -> bool:
        """Check if expression is preprocessed web return type expression."""
        return (
            isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == '__LAMIA_WEB_RT__'
            and len(node.value.args) == 2
        )
    
    def _transform_web_return_type_expression(self, node):
        """Transform preprocessed web return type expression.

        Handles both simple types (-> HTML) and File write targets (-> File(HTML, "path")).
        For File targets, returns a list of statements (assign + write) that gets spliced
        in place of the original Expr node.
        """
        return_type_node = node.value.args[0]
        web_call = node.value.args[1]
        web_command = self._transform_web_call(web_call)

        # Check for -> File(...) target
        if self._is_file_call(return_type_node):
            inner_rt_node, path, append, encoding = self._extract_file_info_from_ast(return_type_node)
            return self._build_file_write_statements(
                web_command, inner_rt_node, path, append, encoding,
            )

        # Original behaviour – simple/parametric return type
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
    
    def _is_file_write_expression(self, node) -> bool:
        """Check if expression is a preprocessed __LAMIA_FILE_WRITE__(prompt, File(...))."""
        return (
            isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == '__LAMIA_FILE_WRITE__'
            and len(node.value.args) == 2
        )

    def _transform_file_write_expression(self, node):
        """Transform preprocessed __LAMIA_FILE_WRITE__(prompt, File(...)) expression.

        The prompt is an LLM string command. The File(...) describes the target.
        Generated code:
            __lamia_file_result__ = lamia.run(prompt [, return_type=Type])
            lamia.run(FileCommand(action=FileActionType.WRITE, path=..., content=...))
        """
        prompt_node = node.value.args[0]  # string literal
        file_node = node.value.args[1]    # File(...)

        inner_rt_node, path, append, encoding = self._extract_file_info_from_ast(file_node)

        # The command is the string literal itself
        command_ast = prompt_node

        return self._build_file_write_statements(
            command_ast, inner_rt_node, path, append, encoding,
        )

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

        # Check for -> File(...) return annotation
        if getattr(node, 'returns', None) is not None and self._is_file_call(node.returns):
            inner_rt_node, path, append, encoding = self._extract_file_info_from_ast(node.returns)
            # Build keywords for the main command call
            main_kw: List[ast.keyword] = []
            if inner_rt_node is not None:
                main_kw.append(ast.keyword(arg='return_type', value=inner_rt_node))
            body = self._build_file_write_body(
                [web_command_ast], main_kw,
                has_inner_type=inner_rt_node is not None,
                path=path, append=append, encoding=encoding,
                is_async=is_async,
            )
            if is_async:
                return ast.AsyncFunctionDef(
                    name=node.name, args=node.args, body=body,
                    decorator_list=node.decorator_list, returns=None,
                    type_comment=getattr(node, 'type_comment', None),
                    lineno=getattr(node, 'lineno', 1),
                    col_offset=getattr(node, 'col_offset', 0),
                )
            return ast.FunctionDef(
                name=node.name, args=node.args, body=body,
                decorator_list=node.decorator_list, returns=None,
                type_comment=getattr(node, 'type_comment', None),
                lineno=getattr(node, 'lineno', 1),
                col_offset=getattr(node, 'col_offset', 0),
            )

        # Build optional return_type argument from function annotation for engine validation
        return_type_kw = self._build_return_type_keyword_from_node(node)

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
    
    def _build_return_type_keyword_from_node(self, node) -> Optional[ast.keyword]:
        """Build return_type keyword from a function node's returns annotation.

        Note: File(...) return annotations are NOT handled here. They are
        intercepted earlier in the pipeline by _create_lamia_call_function
        (for LLM functions) or _transform_web_command_function.
        """
        if getattr(node, 'returns', None) is not None:
            rt = node.returns
            # File(...) targets are handled separately by the file write path
            if self._is_file_call(rt):
                return None
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
        
        # Add first argument: url for navigation, selector for everything else
        if len(args) > 0:
            if action_type_enum == BrowserActionType.NAVIGATE:
                keywords.append(
                    ast.keyword(arg='url', value=args[0])
                )
            else:
                keywords.append(
                    ast.keyword(arg='selector', value=args[0])
                )
        
        # Add second+ arguments based on action type
        if len(args) > 1:
            if action_type_enum in VALUE_SECOND_ARG_ACTIONS:
                # Second arg is a value (text to type, option to select, attribute name, file path)
                keywords.append(
                    ast.keyword(arg='value', value=args[1])
                )
                if len(args) > 2:
                    keywords.append(
                        ast.keyword(arg='fallback_selectors', value=ast.List(elts=args[2:], ctx=ast.Load()))
                    )
            elif action_type_enum in SELECTOR_BASED_ACTIONS:
                # Remaining args are fallback selectors
                keywords.append(
                    ast.keyword(arg='fallback_selectors', value=ast.List(elts=args[1:], ctx=ast.Load()))
                )
        
        return ast.Call(
            func=ast.Name(id='WebCommand', ctx=ast.Load()),
            args=[],
            keywords=keywords
        )
    
    def _create_lamia_call_function(
        self, node, processed_command: ast.AST, return_type: Optional[ReturnType], is_async: bool,
    ):
        """Create a function node that calls lamia.run() or lamia.run_async()."""
        func_info = self.detector.llm_functions[node.name]

        # Build lamia call arguments
        args = [processed_command]
        keywords: List[ast.keyword] = []

        # Add models parameter from function signature if present
        models_keyword = self._build_models_keyword(func_info.parameters)
        if models_keyword:
            keywords.append(models_keyword)

        # Check for File write return type -> File(Type, "path")
        if isinstance(return_type, FileWriteReturnType):
            return self._build_file_write_function(node, args, keywords, return_type, is_async)

        # Add return type parameter
        return_type_keyword = self._build_return_type_keyword(return_type)
        if return_type_keyword:
            keywords.append(return_type_keyword)
        
        # Choose method and create call based on sync/async
        if is_async:
            return self._build_async_lamia_function(node, args, keywords)
        else:
            return self._build_sync_lamia_function(node, args, keywords)
    
    def _build_models_keyword(self, parameters: List[FunctionParameter]) -> Optional[ast.keyword]:
        """Build models keyword argument from function parameters."""
        for param in parameters:
            if param.name == 'models' and param.default is not None:
                # Create models keyword argument with the actual default value
                if isinstance(param.default, list):
                    # Create list literal for multiple models
                    list_elements = [ast.Constant(value=model) for model in param.default]
                    value_node = ast.List(elts=list_elements, ctx=ast.Load())
                else:
                    # Single model string
                    value_node = ast.Constant(value=param.default)
                
                return ast.keyword(arg='models', value=value_node)
        return None

    def _build_return_type_keyword(
        self, return_type: Optional[Union[SimpleReturnType, ParametricReturnType]],
    ) -> Optional[ast.keyword]:
        """Build return type keyword from typed return type descriptor."""
        if return_type is None:
            return None
        if isinstance(return_type, SimpleReturnType):
            return_type_node = ast.Name(id=return_type.base_type, ctx=ast.Load())
        elif isinstance(return_type, ParametricReturnType):
            return_type_node = ast.Subscript(
                value=ast.Name(id=return_type.base_type, ctx=ast.Load()),
                slice=ast.Name(id=return_type.inner_type, ctx=ast.Load()),
                ctx=ast.Load(),
            )
        else:
            return None
        return ast.keyword(arg='return_type', value=return_type_node)
    
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

    # ── File write helpers (-> File(...) syntax) ──────────────────────────

    def _is_file_call(self, node) -> bool:
        """Check if AST node is a File(...) call."""
        return (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == 'File')

    def _extract_file_info_from_ast(self, file_node) -> tuple:
        """Extract inner type node, path, append flag, and encoding from File(...) AST.

        Returns:
            (inner_rt_node, path, append, encoding) where inner_rt_node is None
            for untyped writes.
        """
        args = file_node.args
        kwargs = {kw.arg: kw.value for kw in file_node.keywords}

        if len(args) == 1:
            inner_rt_node = None
            path_node = args[0]
        elif len(args) >= 2:
            inner_rt_node = args[0]
            path_node = args[1]
        else:
            return None, None, False, "utf-8"

        path = path_node.value if isinstance(path_node, ast.Constant) else None

        append = False
        if 'append' in kwargs and isinstance(kwargs['append'], ast.Constant):
            append = bool(kwargs['append'].value)
        encoding = "utf-8"
        if 'encoding' in kwargs and isinstance(kwargs['encoding'], ast.Constant):
            encoding = str(kwargs['encoding'].value)

        return inner_rt_node, path, append, encoding

    def _build_file_write_function(
        self, node, args: list, keywords: list, file_return_type: FileWriteReturnType, is_async: bool,
    ):
        """Build a function that executes a command, writes to file, and returns.

        Generated code pattern (sync, typed):
            def func():
                __lamia_file_result__ = lamia.run(cmd, return_type=Type)
                lamia.run(FileCommand(action=FileActionType.WRITE, path="...", content=__lamia_file_result__.result_text))
                return __lamia_file_result__
        """
        # Add inner return type keyword if present
        if file_return_type.inner_return_type is not None:
            rt_keyword = self._build_return_type_keyword(file_return_type.inner_return_type)
            if rt_keyword:
                keywords.append(rt_keyword)

        body = self._build_file_write_body(
            args, keywords,
            has_inner_type=file_return_type.inner_return_type is not None,
            path=file_return_type.path,
            append=file_return_type.append,
            encoding=file_return_type.encoding,
            is_async=is_async,
        )

        if is_async:
            return ast.AsyncFunctionDef(
                name=node.name,
                args=node.args,
                body=body,
                decorator_list=node.decorator_list,
                returns=None,
                type_comment=getattr(node, 'type_comment', None),
                lineno=getattr(node, 'lineno', 1),
                col_offset=getattr(node, 'col_offset', 0),
            )
        return ast.FunctionDef(
            name=node.name,
            args=node.args,
            body=body,
            decorator_list=node.decorator_list,
            returns=None,
            type_comment=getattr(node, 'type_comment', None),
            lineno=getattr(node, 'lineno', 1),
            col_offset=getattr(node, 'col_offset', 0),
        )

    def _build_file_write_body(
        self,
        args: list,
        keywords: list,
        has_inner_type: bool,
        path: str,
        append: bool,
        encoding: str,
        is_async: bool,
    ) -> List[ast.stmt]:
        """Build the multi-step body for a file write function.

        Steps:
            1. __lamia_file_result__ = lamia.run(command [, return_type=Type])
            2. lamia.run(FileCommand(action=WRITE|APPEND, path=..., content=...))
            3. return __lamia_file_result__
        """
        tmp_var = '__lamia_file_result__'
        method = 'run_async' if is_async else 'run'

        # Step 1 – execute the command
        lamia_call = ast.Call(
            func=ast.Attribute(
                value=ast.Name(id=self.lamia_var_name, ctx=ast.Load()),
                attr=method,
                ctx=ast.Load(),
            ),
            args=args,
            keywords=keywords,
        )
        if is_async:
            lamia_call = ast.Await(value=lamia_call)

        assign_stmt = ast.Assign(
            targets=[ast.Name(id=tmp_var, ctx=ast.Store())],
            value=lamia_call,
            lineno=1, col_offset=0,
        )

        # Step 2 – determine content expression
        if has_inner_type:
            # Typed: __lamia_file_result__.result_text
            content_expr = ast.Attribute(
                value=ast.Name(id=tmp_var, ctx=ast.Load()),
                attr='result_text',
                ctx=ast.Load(),
            )
        else:
            # Untyped: str(__lamia_file_result__)
            content_expr = ast.Call(
                func=ast.Name(id='str', ctx=ast.Load()),
                args=[ast.Name(id=tmp_var, ctx=ast.Load())],
                keywords=[],
            )

        # Step 3 – build FileCommand AST
        action_name = 'APPEND' if append else 'WRITE'
        file_command_ast = ast.Call(
            func=ast.Name(id='FileCommand', ctx=ast.Load()),
            args=[],
            keywords=[
                ast.keyword(
                    arg='action',
                    value=ast.Attribute(
                        value=ast.Name(id='FileActionType', ctx=ast.Load()),
                        attr=action_name,
                        ctx=ast.Load(),
                    ),
                ),
                ast.keyword(arg='path', value=ast.Constant(value=path)),
                ast.keyword(arg='content', value=content_expr),
                ast.keyword(arg='encoding', value=ast.Constant(value=encoding)),
            ],
        )

        # Step 4 – lamia.run(FileCommand(...))
        file_write_call = ast.Call(
            func=ast.Attribute(
                value=ast.Name(id=self.lamia_var_name, ctx=ast.Load()),
                attr=method,
                ctx=ast.Load(),
            ),
            args=[file_command_ast],
            keywords=[],
        )
        if is_async:
            file_write_call = ast.Await(value=file_write_call)

        write_stmt = ast.Expr(value=file_write_call)

        # Step 5 – return
        return_stmt = ast.Return(value=ast.Name(id=tmp_var, ctx=ast.Load()))

        return [assign_stmt, write_stmt, return_stmt]

    def _build_file_write_statements(
        self,
        command_ast,
        inner_rt_node,
        path: str,
        append: bool,
        encoding: str,
    ) -> List[ast.stmt]:
        """Build multi-step statements for expression-level -> File(...) (sync only).

        Used by visit_Expr for web.method() -> File(...) expressions.
        Returns a list of statement nodes to splice in place of the original Expr.
        """
        tmp_var = '__lamia_file_result__'
        method = 'run'

        # Keywords for the main command call
        keywords: List[ast.keyword] = []
        if inner_rt_node is not None:
            keywords.append(ast.keyword(arg='return_type', value=inner_rt_node))

        # Step 1 – __lamia_file_result__ = lamia.run(command, return_type=...)
        lamia_call = ast.Call(
            func=ast.Attribute(
                value=ast.Name(id=self.lamia_var_name, ctx=ast.Load()),
                attr=method,
                ctx=ast.Load(),
            ),
            args=[command_ast],
            keywords=keywords,
        )
        assign_stmt = ast.Assign(
            targets=[ast.Name(id=tmp_var, ctx=ast.Store())],
            value=lamia_call,
            lineno=1, col_offset=0,
        )

        # Step 2 – content expression
        if inner_rt_node is not None:
            content_expr = ast.Attribute(
                value=ast.Name(id=tmp_var, ctx=ast.Load()),
                attr='result_text',
                ctx=ast.Load(),
            )
        else:
            content_expr = ast.Call(
                func=ast.Name(id='str', ctx=ast.Load()),
                args=[ast.Name(id=tmp_var, ctx=ast.Load())],
                keywords=[],
            )

        # Step 3 – FileCommand
        action_name = 'APPEND' if append else 'WRITE'
        file_command_ast = ast.Call(
            func=ast.Name(id='FileCommand', ctx=ast.Load()),
            args=[],
            keywords=[
                ast.keyword(
                    arg='action',
                    value=ast.Attribute(
                        value=ast.Name(id='FileActionType', ctx=ast.Load()),
                        attr=action_name,
                        ctx=ast.Load(),
                    ),
                ),
                ast.keyword(arg='path', value=ast.Constant(value=path)),
                ast.keyword(arg='content', value=content_expr),
                ast.keyword(arg='encoding', value=ast.Constant(value=encoding)),
            ],
        )

        # Step 4 – lamia.run(FileCommand(...))
        file_write_call = ast.Call(
            func=ast.Attribute(
                value=ast.Name(id=self.lamia_var_name, ctx=ast.Load()),
                attr=method,
                ctx=ast.Load(),
            ),
            args=[file_command_ast],
            keywords=[],
        )
        write_stmt = ast.Expr(value=file_write_call)

        return [assign_stmt, write_stmt]

    # ── Parameter substitution ──────────────────────────────────────────

    def _create_parameter_substitution_logic(
        self, command: str, parameters: List[FunctionParameter],
    ) -> ast.AST:
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
            if param.name in param_placeholders:
                # Create serialization logic for this parameter
                serialized_param = self._create_param_serialization(param)
                format_kwargs.append(
                    ast.keyword(
                        arg=param.name,
                        value=serialized_param,
                    )
                )
        
        # Create command.format(...) call
        return ast.Call(
            func=ast.Attribute(
                value=ast.Constant(value=command),
                attr='format',
                ctx=ast.Load(),
            ),
            args=[],
            keywords=format_kwargs,
        )
    
    def _create_param_serialization(self, param: FunctionParameter) -> ast.AST:
        """Create AST for serializing a parameter based on its type."""
        if not param.type_annotation or param.type_annotation in ['str', 'int', 'float', 'bool']:
            # Simple types, use string representation
            return ast.Call(
                func=ast.Name(id='str', ctx=ast.Load()),
                args=[ast.Name(id=param.name, ctx=ast.Load())],
                keywords=[],
            )
        else:
            # Complex types - use SmartTypeResolver to handle LamiaResult -> Model conversion
            resolved_param = ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id='SmartTypeResolver', ctx=ast.Load()),
                    attr='resolve_for_parameter',
                    ctx=ast.Load(),
                ),
                args=[
                    ast.Name(id=param.name, ctx=ast.Load()),
                    ast.Constant(value=param.type_annotation),
                ],
                keywords=[],
            )
            
            # Then serialize the resolved object
            return ast.Call(
                func=ast.Attribute(
                    value=resolved_param,
                    attr='model_dump_json' if 'Model' in param.type_annotation else 'json',
                    ctx=ast.Load(),
                ),
                args=[],
                keywords=[],
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
