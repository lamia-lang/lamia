"""Tests for the .hu file executor (HuCallable)."""

import pytest
from unittest.mock import patch, MagicMock

from lamia.interpreter.human.parser import HuFunction
from lamia.interpreter.human.executor import HuCallable


def _make_fn(name: str = "test", template: str = "", params: frozenset[str] = frozenset()) -> HuFunction:
    return HuFunction(name=name, template=template, params=params, source_path="/fake/test.hu")


class TestHuCallable:

    def test_no_params(self):
        fn = _make_fn(template="Hello world")
        c = HuCallable(fn)
        assert c() == "Hello world"

    def test_single_param(self):
        fn = _make_fn(template="Hello, {name}!", params=frozenset({"name"}))
        c = HuCallable(fn)
        assert c(name="Alice") == "Hello, Alice!"

    def test_multiple_params(self):
        fn = _make_fn(
            template="Write a {tone} email about {topic}.",
            params=frozenset({"tone", "topic"}),
        )
        c = HuCallable(fn)
        assert c(tone="formal", topic="Q3") == "Write a formal email about Q3."

    def test_missing_param_raises(self):
        fn = _make_fn(template="{a} and {b}", params=frozenset({"a", "b"}))
        c = HuCallable(fn)
        with pytest.raises(TypeError, match="missing required keyword arguments"):
            c(a="x")

    def test_missing_all_params_raises(self):
        fn = _make_fn(template="{x}", params=frozenset({"x"}))
        c = HuCallable(fn)
        with pytest.raises(TypeError, match="x"):
            c()

    def test_extra_kwargs_ignored(self):
        fn = _make_fn(template="Hi {name}", params=frozenset({"name"}))
        c = HuCallable(fn)
        assert c(name="Bob", extra="ignored") == "Hi Bob"

    @patch("lamia.interpreter.human.executor.get_active_files_context")
    def test_file_context_left_intact_when_files_context_active(self, mock_ctx):
        """When a FilesContext is active, {@...} is left for LLMManager to resolve."""
        mock_ctx.return_value = MagicMock()
        fn = _make_fn(template="Check {@main.py} for {issue}", params=frozenset({"issue"}))
        c = HuCallable(fn)
        result = c(issue="bugs")
        assert "{@main.py}" in result
        assert "bugs" in result

    def test_literal_braces(self):
        fn = _make_fn(template="Format: {{key: value}}, param: {x}", params=frozenset({"x"}))
        c = HuCallable(fn)
        assert c(x="42") == "Format: {{key: value}}, param: 42"

    def test_non_param_braces_preserved(self):
        """Curly braces that aren't declared params (e.g. CSS, JSON) survive intact."""
        fn = _make_fn(
            template="body { id } .cls { color: red } param={x}",
            params=frozenset({"x"}),
        )
        c = HuCallable(fn)
        assert c(x="ok") == "body { id } .cls { color: red } param=ok"

    def test_json_in_template(self):
        fn = _make_fn(
            template='Parse this JSON: {"name": "test", "id": 1} for {task}',
            params=frozenset({"task"}),
        )
        c = HuCallable(fn)
        result = c(task="validation")
        assert '{"name": "test", "id": 1}' in result
        assert "validation" in result

    def test_name_property(self):
        fn = _make_fn(name="summarize")
        c = HuCallable(fn)
        assert c.__name__ == "summarize"

    def test_repr(self):
        fn = _make_fn(name="greet", params=frozenset({"name"}))
        c = HuCallable(fn)
        r = repr(c)
        assert "greet" in r
        assert "name" in r

    def test_param_value_converted_to_str(self):
        fn = _make_fn(template="Count: {n}", params=frozenset({"n"}))
        c = HuCallable(fn)
        assert c(n=42) == "Count: 42"