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
        # Extract probe_url from session() call if provided
        probe_url = self._extract_probe_url(node)

        # Check if we have a return type for this session
        return_type = None
        pre_validation_call = None
        if self.return_types:
            # Use the single return type (simplified - only one return type supported)
            return_type = next(iter(self.return_types.values()))
            pre_validation_call = self._create_pre_validation_call(probe_url, return_type)

        # Create the modified with statement body
        modified_body = []

        # Add validation call at the BEGINNING if return type is specified
        # This checks if we're already in the desired state and can skip the session
        if pre_validation_call:
            modified_body.append(pre_validation_call)

        if return_type:
            # Wrap user body in try-except so post-validation always runs even
            # when an action fails (e.g. element not found because login form changed).
            # The user can then complete login manually during the polling window.
            wrapped_body = self._wrap_user_body_in_try_except(node.body)
            modified_body.append(wrapped_body)

            post_validation_call = self._create_post_validation_call(probe_url, return_type)
            modified_body.append(post_validation_call)
        else:
            # No return type: keep original body as-is, no wrapping
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

    def _wrap_user_body_in_try_except(self, body: list) -> ast.Try:
        """Wrap the user's session body statements in try-except.

        When a web action fails (e.g. element not found because the login form
        changed, or because the user is already logged in and the page
        redirected), the exception is caught and logged as a warning.  This
        ensures that ``validate_login_completion`` (appended after the body)
        always executes, giving the user a chance to complete login manually.

        Generated code::

            try:
                <user body statements>
            except Exception as _lamia_session_body_error:
                logger.warning(
                    f"Session action failed: {_lamia_session_body_error}. "
                    "Waiting for manual login completion..."
                )
        """
        return ast.Try(
            body=list(body),
            handlers=[
                ast.ExceptHandler(
                    type=ast.Name(id='Exception', ctx=ast.Load()),
                    name='_lamia_session_body_error',
                    body=[
                        ast.Expr(
                            value=ast.Call(
                                func=ast.Attribute(
                                    value=ast.Name(id='logger', ctx=ast.Load()),
                                    attr='warning',
                                    ctx=ast.Load(),
                                ),
                                args=[
                                    ast.JoinedStr(
                                        values=[
                                            ast.Constant(value="Session action failed: "),
                                            ast.FormattedValue(
                                                value=ast.Name(id='_lamia_session_body_error', ctx=ast.Load()),
                                                conversion=-1,
                                                format_spec=None,
                                            ),
                                            ast.Constant(value=". Waiting for manual login completion..."),
                                        ],
                                    )
                                ],
                                keywords=[],
                            )
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

    def _create_pre_validation_call(self, probe_url: Optional[str], return_type: str) -> ast.Expr:
        """Create a call to pre_validate_session() at the start of the session body.

        This replaces the previous inline AST validation block.  The function
        checks both URL match (are we already on probe_url?) and model
        validation, raising SessionSkipException if either confirms we are
        already in the desired state.

        Generated code::

            pre_validate_session(lamia, "https://...", HTML[Model])
        """
        rt_node = self._build_return_type_ast(return_type)

        probe_url_node: ast.expr
        if probe_url is not None:
            probe_url_node = ast.Constant(value=probe_url)
        else:
            probe_url_node = ast.Constant(value=None)

        return ast.Expr(
            value=ast.Call(
                func=ast.Name(id='pre_validate_session', ctx=ast.Load()),
                args=[
                    ast.Name(id='lamia', ctx=ast.Load()),
                    probe_url_node,
                    rt_node,
                ],
                keywords=[],
            ),
            lineno=1,
            col_offset=0,
        )
    
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
    
    def _extract_probe_url(self, node) -> Optional[str]:
        """Extract probe_url from session() call's second positional argument."""
        for item in node.items:
            if self._is_session_context(item):
                call = item.context_expr
                if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
                    return call.args[1].value
        return None

    def _create_post_validation_call(self, probe_url: Optional[str], return_type: str) -> ast.Expr:
        """Create a call to validate_login_completion() at the end of the session body.

        Generated code:
            validate_login_completion(lamia, "https://...", HTML[HomePageModel])
        """
        rt_node = self._build_return_type_ast(return_type)

        probe_url_node: ast.expr
        if probe_url is not None:
            probe_url_node = ast.Constant(value=probe_url)
        else:
            probe_url_node = ast.Constant(value=None)

        return ast.Expr(
            value=ast.Call(
                func=ast.Name(id='validate_login_completion', ctx=ast.Load()),
                args=[
                    ast.Name(id='lamia', ctx=ast.Load()),
                    probe_url_node,
                    rt_node,
                ],
                keywords=[],
            ),
            lineno=1,
            col_offset=0,
        )
