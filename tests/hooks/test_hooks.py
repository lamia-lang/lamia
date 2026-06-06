"""Tests for the Lamia hooks infrastructure."""

import tempfile
import textwrap
from pathlib import Path

import pytest

from lamia.hooks import Hook, HookDefinition, POST_LLM
from lamia.hooks.discovery import discover_hooks, _extract_hooks_from_source
from lamia.hooks.runner import HookRunner


class TestHookType:
    """Tests for the Hook marker class."""

    def test_hook_basic(self):
        h = Hook(POST_LLM)
        assert h.event == "post_llm"
        assert h.return_type is None
        assert h.function is None

    def test_hook_with_return_type(self):
        h = Hook(POST_LLM, "TEXT")
        assert h.return_type == "TEXT"

    def test_hook_with_function_filter(self):
        h = Hook(POST_LLM, function="generate_*")
        assert h.function == "generate_*"

    def test_hook_repr(self):
        h = Hook(POST_LLM, "CSV", function="log_run")
        assert "post_llm" in repr(h)
        assert "CSV" in repr(h)
        assert "log_run" in repr(h)


class TestHookDiscovery:
    """Tests for discovering hooks from .lm files."""

    def test_discover_simple_hook(self):
        source = textwrap.dedent("""\
            def fix_dashes(content) -> Hook(post_llm):
                return content.replace('\\u2014', '-')
        """)
        hooks = _extract_hooks_from_source(source, "test.lm")
        assert len(hooks) == 1
        assert hooks[0].event == POST_LLM
        assert hooks[0].name == "fix_dashes"
        assert hooks[0].filter_return_type is None
        assert hooks[0].filter_function is None

    def test_discover_hook_with_return_type_filter(self):
        source = textwrap.dedent("""\
            def strip_headers(content) -> Hook(post_llm, TEXT):
                return content.lstrip('#')
        """)
        hooks = _extract_hooks_from_source(source, "test.lm")
        assert len(hooks) == 1
        assert hooks[0].filter_return_type == "TEXT"

    def test_discover_hook_with_function_filter(self):
        source = textwrap.dedent("""\
            def clean_desc(content) -> Hook(post_llm, function='generate_description'):
                return content.strip()
        """)
        hooks = _extract_hooks_from_source(source, "test.lm")
        assert len(hooks) == 1
        assert hooks[0].filter_function == "generate_description"

    def test_discover_hook_with_both_filters(self):
        source = textwrap.dedent("""\
            def clean(content) -> Hook(post_llm, Markdown, function='summarize_*'):
                return content
        """)
        hooks = _extract_hooks_from_source(source, "test.lm")
        assert len(hooks) == 1
        assert hooks[0].filter_return_type == "Markdown"
        assert hooks[0].filter_function == "summarize_*"

    def test_non_hook_functions_ignored(self):
        source = textwrap.dedent("""\
            def regular_func(x):
                return x + 1

            def llm_func(topic) -> str:
                f"Write about {topic}"

            def hook_func(content) -> Hook(post_llm):
                return content.upper()
        """)
        hooks = _extract_hooks_from_source(source, "test.lm")
        assert len(hooks) == 1
        assert hooks[0].name == "hook_func"

    def test_unknown_event_skipped(self):
        source = textwrap.dedent("""\
            def bad(content) -> Hook(unknown_event):
                return content
        """)
        hooks = _extract_hooks_from_source(source, "test.lm")
        assert len(hooks) == 0

    def test_discover_from_project_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            hook_file = p / "hooks.lm"
            hook_file.write_text(textwrap.dedent("""\
                def upper(content) -> Hook(post_llm):
                    return content.upper()
            """))
            regular_file = p / "main.lm"
            regular_file.write_text(textwrap.dedent("""\
                def greet(name) -> str:
                    f"Say hello to {name}"
            """))
            hooks = discover_hooks(p)
            assert len(hooks) == 1
            assert hooks[0].name == "upper"

    def test_hidden_dirs_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            hidden = p / ".hidden"
            hidden.mkdir()
            (hidden / "hooks.lm").write_text(
                'def secret(c) -> Hook(post_llm):\n    return c\n'
            )
            hooks = discover_hooks(p)
            assert len(hooks) == 0


class TestHookRunner:
    """Tests for the HookRunner matching and execution."""

    def _make_hook(self, name, event=POST_LLM, fn=None, return_type=None, function=None):
        if fn is None:
            fn = lambda content: content
        return HookDefinition(
            event=event,
            function=fn,
            name=name,
            source_file="test.lm",
            filter_return_type=return_type,
            filter_function=function,
        )

    def test_apply_transform_no_hooks(self):
        runner = HookRunner([])
        assert runner.apply_transform(POST_LLM, "hello") == "hello"

    def test_apply_transform_single_hook(self):
        hook = self._make_hook("upper", fn=lambda c: c.upper())
        runner = HookRunner([hook])
        assert runner.apply_transform(POST_LLM, "hello") == "HELLO"

    def test_apply_transform_chain(self):
        h1 = self._make_hook("strip", fn=lambda c: c.strip())
        h2 = self._make_hook("upper", fn=lambda c: c.upper())
        runner = HookRunner([h1, h2])
        assert runner.apply_transform(POST_LLM, "  hello  ") == "HELLO"

    def test_transform_filter_by_return_type_match(self):
        hook = self._make_hook("csv_fix", fn=lambda c: c + "\n", return_type="CSV")
        runner = HookRunner([hook])
        runner.set_context(return_type="CSV")
        result = runner.apply_transform(POST_LLM, "a,b")
        assert result == "a,b\n"

    def test_transform_filter_by_return_type_no_match(self):
        hook = self._make_hook("csv_fix", fn=lambda c: c + "\n", return_type="CSV")
        runner = HookRunner([hook])
        runner.set_context(return_type="TEXT")
        result = runner.apply_transform(POST_LLM, "hello")
        assert result == "hello"

    def test_transform_filter_by_function_match(self):
        hook = self._make_hook("desc_fix", fn=lambda c: c.lower(), function="generate_*")
        runner = HookRunner([hook])
        runner.set_context(function_name="generate_description")
        result = runner.apply_transform(POST_LLM, "HELLO")
        assert result == "hello"

    def test_transform_filter_by_function_no_match(self):
        hook = self._make_hook("desc_fix", fn=lambda c: c.lower(), function="generate_*")
        runner = HookRunner([hook])
        runner.set_context(function_name="summarize_text")
        result = runner.apply_transform(POST_LLM, "HELLO")
        assert result == "HELLO"

    def test_transform_hook_error_does_not_break(self):
        def bad_hook(c):
            raise ValueError("broken")
        hook = self._make_hook("broken", fn=bad_hook)
        runner = HookRunner([hook])
        result = runner.apply_transform(POST_LLM, "hello")
        assert result == "hello"

    def test_transform_non_string_return_ignored(self):
        hook = self._make_hook("bad_return", fn=lambda c: 42)
        runner = HookRunner([hook])
        result = runner.apply_transform(POST_LLM, "hello")
        assert result == "hello"

    def test_has_hooks_property(self):
        assert not HookRunner([]).has_hooks
        hook = self._make_hook("x")
        assert HookRunner([hook]).has_hooks


class TestHookEventExtensibility:
    """Test that new hook events can be registered dynamically."""

    def test_register_custom_event(self):
        from lamia.hooks import HookEvent
        custom = HookEvent.register("on_deploy")
        assert custom == "on_deploy"
        assert HookEvent.is_valid("on_deploy")

    def test_unknown_event_invalid(self):
        from lamia.hooks import HookEvent
        assert not HookEvent.is_valid("totally_unknown_xyz")

    def test_builtin_events_valid(self):
        from lamia.hooks import HookEvent
        assert HookEvent.is_valid("post_llm")


class TestHookTransformerSkip:
    """Test that the transformer skips Hook() functions (doesn't wrap in lamia.run)."""

    def test_hook_function_not_detected_as_llm(self):
        from lamia.interpreter.detectors.llm_command_detector import LLMCommandDetector
        source = textwrap.dedent("""\
            def fix_chars(content) -> Hook(post_llm):
                return content.replace('\\u2014', '-')

            def generate_text(topic) -> str:
                f"Write about {topic}"
        """)
        detector = LLMCommandDetector()
        functions = detector.detect_commands(source)
        assert "fix_chars" not in functions
        assert "generate_text" in functions

    def test_hook_with_fstring_return_not_transformed(self):
        """Hook with return f"..." should NOT be wrapped in lamia.run()."""
        from lamia.interpreter.transformers.syntax_transformer import HybridSyntaxTransformer
        source = textwrap.dedent("""\
            def hook_fstring(content) -> Hook(post_llm):
                return f"fixed: {content}"
        """)
        transformer = HybridSyntaxTransformer()
        result = transformer.transform_code(source)
        assert "lamia.run" not in result
        assert "fixed: {content}" in result

    def test_hook_body_with_lamia_syntax_preserved(self):
        """Hooks can contain lamia syntax (like file.read) inside their body."""
        from lamia.interpreter.detectors.llm_command_detector import LLMCommandDetector
        source = textwrap.dedent("""\
            def log_to_file(content) -> Hook(post_llm):
                print(f"Hook processing: {content[:50]}")
                return content.lower()
        """)
        detector = LLMCommandDetector()
        functions = detector.detect_commands(source)
        assert "log_to_file" not in functions
