"""Tests for session transformer module."""

import pytest
import ast
from lamia.interpreter.transformers.session_transformer import SessionWithTransformer


class TestSessionWithTransformer:
    """Test SessionWithTransformer AST transformer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.transformer = SessionWithTransformer()

    def test_with_session_wrapped_in_try_except(self):
        """Test with session() wrapped in try/except."""
        source = """
with session("test"):
    web.click("button")
"""
        tree = ast.parse(source)
        transformed = self.transformer.transform_sessions(tree)

        assert isinstance(transformed, ast.Module)
        assert isinstance(transformed.body[0], ast.Try)
        assert len(transformed.body[0].handlers) == 1
        handler = transformed.body[0].handlers[0]
        assert isinstance(handler.type, ast.Name)
        assert handler.type.id == 'SessionSkipException'

    def test_non_session_with_statements_unchanged(self):
        """Test non-session with statements unchanged."""
        source = """
with open("file.txt") as f:
    content = f.read()
"""
        tree = ast.parse(source)
        transformed = self.transformer.transform_sessions(tree)

        assert isinstance(transformed, ast.Module)
        assert isinstance(transformed.body[0], ast.With)
        assert not isinstance(transformed.body[0], ast.Try)

    def test_return_type_injects_pre_validate_session_call(self):
        """Test return type injects pre_validate_session call at start of body."""
        return_types = {"test_key": "HTML"}
        transformer = SessionWithTransformer(return_types=return_types)
        source = """
with session("test"):
    web.click("button")
"""
        tree = ast.parse(source)
        transformed = transformer.transform_sessions(tree)

        assert isinstance(transformed, ast.Module)
        try_node = transformed.body[0]
        assert isinstance(try_node, ast.Try)
        with_node = try_node.body[0]
        assert isinstance(with_node, ast.With)
        assert len(with_node.body) > 0
        first_stmt = with_node.body[0]
        assert isinstance(first_stmt, ast.Expr)
        call = first_stmt.value
        assert isinstance(call, ast.Call)
        assert isinstance(call.func, ast.Name)
        assert call.func.id == 'pre_validate_session'

    def test_no_return_types_no_validation_injected(self):
        """Test no return types: no validation injected."""
        transformer = SessionWithTransformer(return_types=None)
        source = """
with session("test"):
    web.click("button")
"""
        tree = ast.parse(source)
        transformed = transformer.transform_sessions(tree)

        assert isinstance(transformed, ast.Module)
        try_node = transformed.body[0]
        assert isinstance(try_node, ast.Try)
        with_node = try_node.body[0]
        assert isinstance(with_node, ast.With)
        assert len(with_node.body) == 1
        assert isinstance(with_node.body[0], ast.Expr)

    def test_parametric_return_types(self):
        """Test parametric return types like HTML[Model] in pre_validate_session."""
        return_types = {"test_key": "HTML[UserModel]"}
        transformer = SessionWithTransformer(return_types=return_types)
        source = """
with session("test"):
    web.click("button")
"""
        tree = ast.parse(source)
        transformed = transformer.transform_sessions(tree)

        assert isinstance(transformed, ast.Module)
        try_node = transformed.body[0]
        assert isinstance(try_node, ast.Try)
        with_node = try_node.body[0]
        assert isinstance(with_node, ast.With)
        pre_call = with_node.body[0]
        assert isinstance(pre_call, ast.Expr)
        call = pre_call.value
        assert isinstance(call, ast.Call)
        assert call.func.id == 'pre_validate_session'
        rt_arg = call.args[2]
        assert isinstance(rt_arg, ast.Subscript)
        assert isinstance(rt_arg.value, ast.Name)
        assert rt_arg.value.id == 'HTML'

    def test_session_with_multiple_statements(self):
        """Test session with multiple statements in body."""
        source = """
with session("test"):
    web.click("button")
    web.type_text("#input", "text")
    result = web.get_text(".result")
"""
        tree = ast.parse(source)
        transformed = self.transformer.transform_sessions(tree)

        assert isinstance(transformed, ast.Module)
        try_node = transformed.body[0]
        assert isinstance(try_node, ast.Try)
        with_node = try_node.body[0]
        assert isinstance(with_node, ast.With)
        assert len(with_node.body) == 3

    def test_session_with_empty_body(self):
        """Test session with empty body."""
        source = """
with session("test"):
    pass
"""
        tree = ast.parse(source)
        transformed = self.transformer.transform_sessions(tree)

        assert isinstance(transformed, ast.Module)
        try_node = transformed.body[0]
        assert isinstance(try_node, ast.Try)
        with_node = try_node.body[0]
        assert isinstance(with_node, ast.With)
        assert len(with_node.body) == 1
        assert isinstance(with_node.body[0], ast.Pass)

    def test_multiple_session_statements(self):
        """Test multiple session statements in same code."""
        source = """
with session("test1"):
    web.click("button1")

with session("test2"):
    web.click("button2")
"""
        tree = ast.parse(source)
        transformed = self.transformer.transform_sessions(tree)

        assert isinstance(transformed, ast.Module)
        assert len(transformed.body) == 2
        assert isinstance(transformed.body[0], ast.Try)
        assert isinstance(transformed.body[1], ast.Try)

    def test_session_with_nested_statements(self):
        """Test session with nested control flow."""
        source = """
with session("test"):
    if True:
        web.click("button")
    else:
        web.type_text("#input", "text")
"""
        tree = ast.parse(source)
        transformed = self.transformer.transform_sessions(tree)

        assert isinstance(transformed, ast.Module)
        try_node = transformed.body[0]
        assert isinstance(try_node, ast.Try)
        with_node = try_node.body[0]
        assert isinstance(with_node, ast.With)
        assert len(with_node.body) == 1
        assert isinstance(with_node.body[0], ast.If)

    def test_session_with_return_type_simple(self):
        """Test session with simple return type calls pre_validate_session."""
        return_types = {"key": "HTML"}
        transformer = SessionWithTransformer(return_types=return_types)
        source = """
with session("test"):
    pass
"""
        tree = ast.parse(source)
        transformed = transformer.transform_sessions(tree)

        assert isinstance(transformed, ast.Module)
        try_node = transformed.body[0]
        assert isinstance(try_node, ast.Try)
        with_node = try_node.body[0]
        assert isinstance(with_node, ast.With)
        pre_call = with_node.body[0]
        assert isinstance(pre_call, ast.Expr)
        call = pre_call.value
        assert isinstance(call, ast.Call)
        assert isinstance(call.func, ast.Name)
        assert call.func.id == 'pre_validate_session'
        rt_arg = call.args[2]
        assert isinstance(rt_arg, ast.Name)
        assert rt_arg.id == 'HTML'

    def test_post_validation_injected_at_end_of_body(self):
        """Test that post-validation call is injected at the end of session body when return type is specified."""
        return_types = {"key": "HTML[HomePageModel]"}
        transformer = SessionWithTransformer(return_types=return_types)
        source = """
with session("login", "https://example.com/feed"):
    web.click("button")
"""
        tree = ast.parse(source)
        transformed = transformer.transform_sessions(tree)

        with_node = transformed.body[0].body[0]  # Try -> With
        # body: [pre_validate_session Expr, user-body Try, validate_login_completion Expr]
        assert len(with_node.body) == 3
        last_stmt = with_node.body[-1]
        assert isinstance(last_stmt, ast.Expr)
        call = last_stmt.value
        assert isinstance(call, ast.Call)
        assert isinstance(call.func, ast.Name)
        assert call.func.id == 'validate_login_completion'

    def test_user_body_wrapped_in_try_except_when_return_type(self):
        """Test that user body is wrapped in try-except when return type is specified."""
        return_types = {"key": "HTML"}
        transformer = SessionWithTransformer(return_types=return_types)
        source = """
with session("login"):
    web.click("button")
    web.type_text("#input", "text")
"""
        tree = ast.parse(source)
        transformed = transformer.transform_sessions(tree)

        with_node = transformed.body[0].body[0]  # Try -> With
        # body: [pre_validate_session Expr, user-body Try, validate_login_completion Expr]
        assert len(with_node.body) == 3
        body_wrapper = with_node.body[1]
        assert isinstance(body_wrapper, ast.Try)
        # The user's original statements are inside the try body
        assert len(body_wrapper.body) == 2
        assert isinstance(body_wrapper.body[0], ast.Expr)
        assert isinstance(body_wrapper.body[1], ast.Expr)
        # The except handler catches Exception and logs a warning
        assert len(body_wrapper.handlers) == 1
        handler = body_wrapper.handlers[0]
        assert isinstance(handler.type, ast.Name)
        assert handler.type.id == 'Exception'
        assert handler.name == '_lamia_session_body_error'

    def test_user_body_not_wrapped_without_return_type(self):
        """Test that user body is NOT wrapped when no return type is specified."""
        transformer = SessionWithTransformer(return_types=None)
        source = """
with session("login"):
    web.click("button")
    web.type_text("#input", "text")
"""
        tree = ast.parse(source)
        transformed = transformer.transform_sessions(tree)

        with_node = transformed.body[0].body[0]
        # No wrapping: body has original 2 statements
        assert len(with_node.body) == 2
        assert isinstance(with_node.body[0], ast.Expr)
        assert isinstance(with_node.body[1], ast.Expr)

    def test_post_validation_includes_probe_url(self):
        """Test that post-validation passes probe_url from session() call."""
        return_types = {"key": "HTML"}
        transformer = SessionWithTransformer(return_types=return_types)
        source = """
with session("login", "https://example.com/feed"):
    pass
"""
        tree = ast.parse(source)
        transformed = transformer.transform_sessions(tree)

        with_node = transformed.body[0].body[0]
        post_call = with_node.body[-1].value
        # args: [lamia, probe_url, return_type]
        assert len(post_call.args) == 3
        probe_url_arg = post_call.args[1]
        assert isinstance(probe_url_arg, ast.Constant)
        assert probe_url_arg.value == "https://example.com/feed"

    def test_post_validation_none_probe_url_when_not_provided(self):
        """Test that post-validation passes None probe_url when session has no probe_url."""
        return_types = {"key": "HTML"}
        transformer = SessionWithTransformer(return_types=return_types)
        source = """
with session("login"):
    pass
"""
        tree = ast.parse(source)
        transformed = transformer.transform_sessions(tree)

        with_node = transformed.body[0].body[0]
        post_call = with_node.body[-1].value
        probe_url_arg = post_call.args[1]
        assert isinstance(probe_url_arg, ast.Constant)
        assert probe_url_arg.value is None

    def test_no_post_validation_without_return_type(self):
        """Test that no post-validation is injected when there is no return type."""
        transformer = SessionWithTransformer(return_types=None)
        source = """
with session("login", "https://example.com/feed"):
    web.click("button")
"""
        tree = ast.parse(source)
        transformed = transformer.transform_sessions(tree)

        with_node = transformed.body[0].body[0]
        # Only the original statement, no pre- or post-validation
        assert len(with_node.body) == 1
        assert isinstance(with_node.body[0], ast.Expr)

    def test_post_validation_return_type_passed_correctly(self):
        """Test that post-validation receives the correct parametric return type."""
        return_types = {"key": "HTML[UserModel]"}
        transformer = SessionWithTransformer(return_types=return_types)
        source = """
with session("test"):
    pass
"""
        tree = ast.parse(source)
        transformed = transformer.transform_sessions(tree)

        with_node = transformed.body[0].body[0]
        post_call = with_node.body[-1].value
        rt_arg = post_call.args[2]
        assert isinstance(rt_arg, ast.Subscript)
        assert isinstance(rt_arg.value, ast.Name)
        assert rt_arg.value.id == 'HTML'
        assert isinstance(rt_arg.slice, ast.Name)
        assert rt_arg.slice.id == 'UserModel'

    def test_pre_validate_session_includes_probe_url(self):
        """Test that pre_validate_session receives probe_url from session() call."""
        return_types = {"key": "HTML"}
        transformer = SessionWithTransformer(return_types=return_types)
        source = """
with session("login", "https://example.com/feed"):
    pass
"""
        tree = ast.parse(source)
        transformed = transformer.transform_sessions(tree)

        with_node = transformed.body[0].body[0]
        pre_call = with_node.body[0].value
        assert isinstance(pre_call, ast.Call)
        assert pre_call.func.id == 'pre_validate_session'
        # args: [lamia, probe_url, return_type]
        assert len(pre_call.args) == 3
        probe_url_arg = pre_call.args[1]
        assert isinstance(probe_url_arg, ast.Constant)
        assert probe_url_arg.value == "https://example.com/feed"

    def test_pre_validate_session_none_probe_url(self):
        """Test that pre_validate_session gets None probe_url when not provided."""
        return_types = {"key": "HTML"}
        transformer = SessionWithTransformer(return_types=return_types)
        source = """
with session("login"):
    pass
"""
        tree = ast.parse(source)
        transformed = transformer.transform_sessions(tree)

        with_node = transformed.body[0].body[0]
        pre_call = with_node.body[0].value
        probe_url_arg = pre_call.args[1]
        assert isinstance(probe_url_arg, ast.Constant)
        assert probe_url_arg.value is None
