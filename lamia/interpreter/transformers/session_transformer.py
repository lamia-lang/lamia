"""
Session transformer for handling with session() blocks with return type validation.

Transforms with session() statements to handle SessionSkipException and return type validation.
"""

import ast
from typing import Dict, Optional


class SessionWithTransformer(ast.NodeTransformer):
    """Transforms with session() statements to handle SessionSkipException and return type validation."""
    
    def __init__(self, return_types: Optional[Dict[str, str]] = None):
        self.return_types = return_types or {}
    
    def transform_sessions(self, tree: ast.AST) -> ast.AST:
        """
        Transform session blocks in the AST.
        
        This is the main public interface method.
        
        Args:
            tree: AST tree to transform
            
        Returns:
            Transformed AST tree
        """
        return self.visit(tree)
    
    def visit_With(self, node):
        """Wrap with session() in try-catch to handle skipping and add validation if return type specified."""
        # Check if this is a with session() statement
        for item in node.items:
            if self._is_session_context(item):
                return self._transform_session_with(node)
        
        # Not a session with statement, continue normal processing
        return self.generic_visit(node)
    
    def _is_session_context(self, item) -> bool:
        """Check if context item is a session() call."""
        return (isinstance(item.context_expr, ast.Call) and
                isinstance(item.context_expr.func, ast.Name) and
                item.context_expr.func.id == 'session')
    
    def _transform_session_with(self, node):
        """Transform a with session() statement."""
        # Check if we have a return type for this session
        validation_call = None
        if self.return_types:
            # Use the single return type (simplified - only one return type supported)
            return_type = next(iter(self.return_types.values()))
            validation_call = self._create_web_validation_call(return_type)
        
        # Create the modified with statement body
        modified_body = []
        
        # Add validation call at the BEGINNING if return type is specified
        # This checks if we're already in the desired state and can skip the session
        if validation_call:
            modified_body.append(validation_call)
        
        # Add the original session body after validation
        modified_body.extend(node.body)
        
        # Create new with statement with modified body
        modified_with = self._create_modified_with_statement(node, modified_body)
        
        # Wrap the with statement in try-catch
        return self._wrap_in_try_catch(modified_with, node)
    
    def _create_modified_with_statement(self, original_node, modified_body):
        """Create a new with statement with modified body."""
        return ast.With(
            items=original_node.items,
            body=modified_body,
            lineno=getattr(original_node, 'lineno', 1),
            col_offset=getattr(original_node, 'col_offset', 0)
        )
    
    def _wrap_in_try_catch(self, with_statement, original_node):
        """Wrap with statement in try-catch for SessionSkipException."""
        return ast.Try(
            body=[with_statement],
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
                    lineno=getattr(original_node, 'lineno', 1),
                    col_offset=getattr(original_node, 'col_offset', 0)
                )
            ],
            orelse=[],
            finalbody=[],
            lineno=getattr(original_node, 'lineno', 1),
            col_offset=getattr(original_node, 'col_offset', 0)
        )

    def _create_web_validation_call(self, return_type: str) -> ast.stmt:
        """Create validation logic that raises SessionSkipException if page is already valid.

        RETURN TYPE HANDLING STRATEGY #3: Session Block Validation
        ========================================================
        
        This method handles the special case of `with session(...) -> Type:` blocks.
        Unlike functions or expressions, a session block doesn't itself produce content
        to validate. The arrow means "validate current page state as Type and skip 
        session if already valid". 
        
        We inject validation logic at the BEGINNING of the session block to check
        if we're already in the desired state. If validation succeeds, we raise
        SessionSkipException to skip the rest of the block.
        If validation fails, execution continues with the session actions.

        Generated code (checks typed_result which is None when validation fails):
        try:
            _lamia_session_probe_result = lamia.run(WebCommand(action=WebActionType.GET_TEXT, selector='body'), return_type=Type)
            # Check if validation succeeded (typed_result is not None when validation passes)
            if _lamia_session_probe_result.typed_result is not None:
                raise SessionSkipException(f"Session validation passed - already in desired state")
        except Exception as e:
            # Validation failed or raised an exception - continue with session actions
            if "SessionSkipException" not in str(type(e)):
                pass  # Continue execution
            else:
                raise  # Re-raise SessionSkipException
        """
        # Build return_type AST
        rt_node = self._build_return_type_ast(return_type)

        # Build WebCommand(action=WebActionType.GET_TEXT, selector='body')
        web_command_call = self._build_web_command_ast()

        # Build lamia.run(WebCommand(...), return_type=rt_node)
        lamia_run_call = self._build_lamia_run_ast(web_command_call, rt_node)

        # Create try-except block for validation
        try_block = ast.Try(
            body=[
                # Run validation probe and capture result
                ast.Assign(
                    targets=[ast.Name(id='_lamia_session_probe_result', ctx=ast.Store())],
                    value=lamia_run_call,
                    lineno=1,
                    col_offset=0,
                ),
                # If validation succeeded (typed_result is not None), skip the session
                ast.If(
                    test=ast.Compare(
                        left=ast.Attribute(
                            value=ast.Name(id='_lamia_session_probe_result', ctx=ast.Load()),
                            attr='typed_result',
                            ctx=ast.Load(),
                        ),
                        ops=[ast.IsNot()],
                        comparators=[ast.Constant(value=None)],
                    ),
                    body=[
                        ast.Raise(
                            exc=ast.Call(
                                func=ast.Name(id='SessionSkipException', ctx=ast.Load()),
                                args=[ast.Constant(value="Session validation passed - already in desired state")],
                                keywords=[],
                            ),
                            lineno=1,
                            col_offset=0,
                        )
                    ],
                    orelse=[ast.Pass()],
                    lineno=1,
                    col_offset=0,
                ),
            ],
            handlers=[
                # Catch any errors during the probe and continue, but re-raise SessionSkipException
                ast.ExceptHandler(
                    type=ast.Name(id='Exception', ctx=ast.Load()),
                    name='e',
                    body=[
                        ast.If(
                            test=ast.Compare(
                                left=ast.Constant(value="SessionSkipException"),
                                ops=[ast.In()],
                                comparators=[
                                    ast.Call(
                                        func=ast.Name(id='str', ctx=ast.Load()),
                                        args=[
                                            ast.Call(
                                                func=ast.Name(id='type', ctx=ast.Load()),
                                                args=[ast.Name(id='e', ctx=ast.Load())],
                                                keywords=[],
                                            )
                                        ],
                                        keywords=[],
                                    )
                                ],
                            ),
                            body=[ast.Raise()],
                            orelse=[ast.Pass()],
                            lineno=1,
                            col_offset=0,
                        )
                    ],
                    lineno=1,
                    col_offset=0,
                )
            ],
            orelse=[],
            finalbody=[],
            lineno=1,
            col_offset=0,
        )

        return try_block
    
    def _build_return_type_ast(self, return_type: str) -> ast.expr:
        """Build AST node for return type."""
        if '[' in return_type and return_type.endswith(']'):
            base = return_type.split('[', 1)[0]
            inner = return_type[len(base)+1:-1]
            return ast.Subscript(
                value=ast.Name(id=base, ctx=ast.Load()),
                slice=ast.Name(id=inner, ctx=ast.Load()),
                ctx=ast.Load(),
            )
        else:
            return ast.Name(id=return_type, ctx=ast.Load())
    
    def _build_web_command_ast(self) -> ast.Call:
        """Build WebCommand AST for GET_TEXT action."""
        return ast.Call(
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
                    value=ast.Constant(value='body')
                )
            ]
        )
    
    def _build_lamia_run_ast(self, web_command_call: ast.Call, return_type_node: ast.expr) -> ast.Call:
        """Build lamia.run() AST call."""
        return ast.Call(
            func=ast.Attribute(
                value=ast.Name(id='lamia', ctx=ast.Load()),
                attr='run',
                ctx=ast.Load()
            ),
            args=[web_command_call],
            keywords=[ast.keyword(arg='return_type', value=return_type_node)]
        )
