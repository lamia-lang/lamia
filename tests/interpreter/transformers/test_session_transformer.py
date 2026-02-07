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

    def test_return_type_injects_validation_at_start_of_body(self):
        """Test return type injects validation at start of body."""
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
        assert isinstance(first_stmt, ast.Try)

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
        """Test parametric return types like HTML[Model]."""
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
        validation_try = with_node.body[0]
        assert isinstance(validation_try, ast.Try)
        assign = validation_try.body[0]
        assert isinstance(assign, ast.Assign)
        call = assign.value
        assert isinstance(call, ast.Call)
        keywords = call.keywords
        assert len(keywords) == 1
        assert keywords[0].arg == 'return_type'
        return_type_node = keywords[0].value
        assert isinstance(return_type_node, ast.Subscript)
        assert isinstance(return_type_node.value, ast.Name)
        assert return_type_node.value.id == 'HTML'

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
        """Test session with simple return type."""
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
        validation_try = with_node.body[0]
        assert isinstance(validation_try, ast.Try)
        assign = validation_try.body[0]
        assert isinstance(assign, ast.Assign)
        call = assign.value
        assert isinstance(call, ast.Call)
        return_type_node = call.keywords[0].value
        assert isinstance(return_type_node, ast.Name)
        assert return_type_node.id == 'HTML'
