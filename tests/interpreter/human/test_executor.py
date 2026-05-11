"""Tests for the .hu file executor (HuCallable)."""

import pytest
from unittest.mock import patch, MagicMock, Mock

from lamia.interpreter.human.parser import HuFunction
from lamia.interpreter.human.executor import HuCallable


def _make_fn(
    name: str = "test",
    template: str = "",
    params: frozenset[str] = frozenset(),
    defaults: dict | None = None,
    source_path: str = "/fake/test.hu",
    file_contexts: frozenset[str] = frozenset(),
) -> HuFunction:
    return HuFunction(
        name=name,
        template=template,
        params=params,
        defaults=defaults or {},
        file_contexts=file_contexts,
        source_path=source_path,
    )


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


class TestHuCallableOptionalParams:

    def test_optional_param_omitted_uses_empty_default(self):
        fn = _make_fn(
            template="Task: {raw_tasks}\nPRD: {prd_content:None}",
            params=frozenset({"raw_tasks", "prd_content"}),
            defaults={"prd_content": ""},
        )
        c = HuCallable(fn)
        result = c(raw_tasks="do stuff")
        assert "do stuff" in result
        assert "PRD: " in result

    def test_optional_param_supplied_overrides_default(self):
        fn = _make_fn(
            template="Role: {role:engineer}",
            params=frozenset({"role"}),
            defaults={"role": "engineer"},
        )
        c = HuCallable(fn)
        assert c(role="manager") == "Role: manager"

    def test_optional_param_omitted_uses_text_default(self):
        fn = _make_fn(
            template="Tone: {tone:neutral}",
            params=frozenset({"tone"}),
            defaults={"tone": "neutral"},
        )
        c = HuCallable(fn)
        assert c() == "Tone: neutral"

    def test_required_param_missing_still_raises(self):
        fn = _make_fn(
            template="{required} {optional:default}",
            params=frozenset({"required", "optional"}),
            defaults={"optional": "default"},
        )
        c = HuCallable(fn)
        with pytest.raises(TypeError, match="required"):
            c()

    def test_required_param_missing_excludes_optional_from_error(self):
        """Error message lists only the required missing params, not optional ones."""
        fn = _make_fn(
            template="{a} {b:opt}",
            params=frozenset({"a", "b"}),
            defaults={"b": "opt"},
        )
        c = HuCallable(fn)
        with pytest.raises(TypeError) as exc_info:
            c()
        assert "a" in str(exc_info.value)
        assert "b" not in str(exc_info.value)

    def test_all_optional_no_args(self):
        fn = _make_fn(
            template="{x:1} {y:2}",
            params=frozenset({"x", "y"}),
            defaults={"x": "1", "y": "2"},
        )
        c = HuCallable(fn)
        assert c() == "1 2"

    def test_optional_default_colon_syntax_in_template_escaped_correctly(self):
        """{param:default} in template is still resolved to the substituted value."""
        fn = _make_fn(
            template="Hello {name:World}!",
            params=frozenset({"name"}),
            defaults={"name": "World"},
        )
        c = HuCallable(fn)
        assert c() == "Hello World!"
        assert c(name="Alice") == "Hello Alice!"

    def test_optional_default_with_colon_in_value(self):
        """A default value that itself contains a colon works correctly."""
        fn = _make_fn(
            template="Time: {ts:12:00}",
            params=frozenset({"ts"}),
            defaults={"ts": "12:00"},
        )
        c = HuCallable(fn)
        assert c() == "Time: 12:00"
        assert c(ts="09:30") == "Time: 09:30"

    def test_mix_required_optional_all_provided(self):
        fn = _make_fn(
            template="{req} and {opt:fallback}",
            params=frozenset({"req", "opt"}),
            defaults={"opt": "fallback"},
        )
        c = HuCallable(fn)
        assert c(req="needed", opt="given") == "needed and given"

    def test_optional_param_with_none_default_omitted(self):
        """:None maps to empty string, resulting in empty substitution."""
        fn = _make_fn(
            template="Prefix{suffix:None}end",
            params=frozenset({"suffix"}),
            defaults={"suffix": ""},
        )
        c = HuCallable(fn)
        assert c() == "Prefixend"


class TestHuCallableAutoLLM:

    def test_without_lamia_returns_prompt(self):
        fn = _make_fn(template="Hello {name}", params=frozenset({"name"}))
        c = HuCallable(fn)
        assert c(name="Alice") == "Hello Alice"

    def test_with_lamia_calls_run(self):
        fn = _make_fn(template="Hello {name}", params=frozenset({"name"}))
        mock_lamia = Mock()
        mock_lamia.run.return_value = "LLM says hi"
        c = HuCallable(fn, lamia=mock_lamia)
        result = c(name="Alice")
        mock_lamia.run.assert_called_once_with("Hello Alice", return_type=None)
        assert result == "LLM says hi"

    def test_return_type_forwarded(self):
        fn = _make_fn(template="Hello {name}", params=frozenset({"name"}))
        mock_lamia = Mock()
        mock_lamia.run.return_value = "<html>hi</html>"
        sentinel = object()
        c = HuCallable(fn, lamia=mock_lamia)
        c(name="Alice", _return_type=sentinel)
        mock_lamia.run.assert_called_once_with("Hello Alice", return_type=sentinel)


class TestHuCallableVariableFileRefs:
    """Tests for {@variable} substitution (file resolution disabled via empty source_path)."""

    @staticmethod
    def _fn(**kw):
        kw.setdefault("source_path", "")
        return _make_fn(**kw)

    def test_variable_ref_substituted(self):
        fn = self._fn(template="Review {@code_file}", params=frozenset({"code_file"}))
        c = HuCallable(fn)
        result = c(code_file="src/main.py")
        assert "{@src/main.py}" in result

    def test_literal_ref_unchanged(self):
        fn = self._fn(template="Review {@config.yaml}", params=frozenset())
        c = HuCallable(fn)
        result = c()
        assert "{@config.yaml}" in result

    def test_omitted_file_ref_raises_missing_param(self):
        fn = self._fn(
            template="Review {@some_file}",
            params=frozenset({"some_file"}),
            file_contexts=frozenset({"some_file"}),
        )
        c = HuCallable(fn)
        with pytest.raises(TypeError, match="missing required keyword arguments"):
            c()

    def test_empty_string_file_ref_raises_error(self):
        fn = self._fn(
            template="Review {@code_file}",
            params=frozenset({"code_file"}),
            file_contexts=frozenset({"code_file"}),
        )
        c = HuCallable(fn)
        with pytest.raises(TypeError, match="received empty value for file reference"):
            c(code_file="")

    def test_whitespace_only_file_ref_raises_error(self):
        fn = self._fn(
            template="Review {@code_file}",
            params=frozenset({"code_file"}),
            file_contexts=frozenset({"code_file"}),
        )
        c = HuCallable(fn)
        with pytest.raises(TypeError, match="received empty value for file reference"):
            c(code_file="   ")

    def test_variable_ref_with_text_param(self):
        fn = self._fn(
            template="Review {@code_file} for {aspect}",
            params=frozenset({"code_file", "aspect"}),
        )
        c = HuCallable(fn)
        result = c(code_file="app.py", aspect="security")
        assert "{@app.py}" in result
        assert "security" in result

    def test_both_text_and_file_ref_same_name(self):
        fn = self._fn(
            template="File: {code_file}\nContent: {@code_file}",
            params=frozenset({"code_file"}),
        )
        c = HuCallable(fn)
        result = c(code_file="src/main.py")
        assert "File: src/main.py" in result
        assert "{@src/main.py}" in result