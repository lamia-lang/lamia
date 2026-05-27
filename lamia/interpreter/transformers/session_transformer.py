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
        target_url = self._extract_target_url(node)
        login_url = self._extract_first_navigate_url(node.body)

        return_type = None
        if self.return_types:
            return_type = next(iter(self.return_types.values()))

        pre_validation_call = self._create_pre_validation_call(
            login_url, target_url, return_type
        )

        modified_body = [pre_validation_call]

        if return_type:
            wrapped_body = self._wrap_user_body_in_try_except(node.body)
            modified_body.append(wrapped_body)

            post_validation_call = self._create_post_validation_call(target_url, return_type)
            modified_body.append(post_validation_call)
        else:
            modified_body.extend(node.body)

        modified_with = self._create_modified_with_statement(node, modified_body)
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

    def _create_pre_validation_call(
        self,
        login_url: Optional[str],
        target_url: Optional[str],
        return_type: Optional[str],
    ) -> ast.Expr:
        """Create a call to pre_validate_session() at the start of the session body.

        Generated code::

            pre_validate_session(lamia, "login_url", "target_url", HTML[Model])
        """
        login_url_node: ast.expr = ast.Constant(value=login_url)
        target_url_node: ast.expr = ast.Constant(value=target_url)

        if return_type is not None:
            rt_node: ast.expr = self._build_return_type_ast(return_type)
        else:
            rt_node = ast.Constant(value=None)

        return ast.Expr(
            value=ast.Call(
                func=ast.Name(id='pre_validate_session', ctx=ast.Load()),
                args=[
                    ast.Name(id='lamia', ctx=ast.Load()),
                    login_url_node,
                    target_url_node,
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
    
    def _extract_target_url(self, node) -> Optional[str]:
        """Extract target_url from session() call's second positional argument."""
        for item in node.items:
            if self._is_session_context(item):
                call = item.context_expr
                if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
                    return call.args[1].value
        return None

    def _extract_first_navigate_url(self, body: list) -> Optional[str]:
        """Extract the URL from the first web.navigate("...") call in the body."""
        for node in ast.walk(ast.Module(body=body, type_ignores=[])):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "web"
                and node.func.attr == "navigate"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                return node.args[0].value
        return None

    def _create_post_validation_call(self, target_url: Optional[str], return_type: str) -> ast.Expr:
        """Create a call to validate_login_completion() at the end of the session body.

        Generated code:
            validate_login_completion(lamia, "https://...", HTML[HomePageModel])
        """
        rt_node = self._build_return_type_ast(return_type)
        target_url_node: ast.expr = ast.Constant(value=target_url)

        return ast.Expr(
            value=ast.Call(
                func=ast.Name(id='validate_login_completion', ctx=ast.Load()),
                args=[
                    ast.Name(id='lamia', ctx=ast.Load()),
                    target_url_node,
                    rt_node,
                ],
                keywords=[],
            ),
            lineno=1,
            col_offset=0,
        )
