"""Comprehensive tests for the eval CLI module."""

import pytest

from lamia.cli.eval_cli import (
    _extract_llm_prompts,
    _print_attempt_results,
    _print_prompt_header,
    _resolve_return_type,
    _resolve_type_name,
)
from lamia.eval.evaluator import EvaluationResult, ModelAttemptResult
from lamia.eval.model_cost import ModelCost
from lamia.interpreter.detectors.llm_command_detector import (
    FileWriteReturnType,
    ParametricReturnType,
    SimpleReturnType,
)
from lamia.types import CSV, HTML, JSON, Markdown, TEXT, TXT, XML, YAML


class TestExtractLLMPrompts:
    """Test hybrid-source parsing and LLM prompt extraction."""

    def test_single_llm_function(self):
        prompts = _extract_llm_prompts('def greet():\n    "Say hello"\n')
        assert len(prompts) == 1
        assert prompts[0] == ("Say hello", None)

    def test_multiple_llm_functions(self):
        source = """\
def first() -> HTML:
    "First prompt"

def second():
    "Second prompt"

def third() -> JSON:
    "Third prompt"
"""
        prompts = _extract_llm_prompts(source)
        assert len(prompts) == 3
        assert prompts[0] == ("First prompt", HTML)
        assert prompts[1] == ("Second prompt", None)
        assert prompts[2] == ("Third prompt", JSON)

    def test_no_llm_functions(self):
        assert _extract_llm_prompts("x = 1 + 2\n") == []

    def test_return_type_html(self):
        prompts = _extract_llm_prompts('def greet() -> HTML:\n    "Say hello"\n')
        assert prompts == [("Say hello", HTML)]

    @pytest.mark.parametrize(
        ("return_type", "expected"),
        [
            ("JSON", JSON),
            ("Markdown", Markdown),
            ("XML", XML),
            ("CSV", CSV),
            ("TEXT", TEXT),
        ],
    )
    def test_return_type_annotations(self, return_type, expected):
        source = f'def greet() -> {return_type}:\n    "Say hello"\n'
        prompts = _extract_llm_prompts(source)
        assert prompts == [("Say hello", expected)]

    def test_parametric_return_type(self):
        source = 'def greet() -> HTML[MyModel]:\n    "Say hello"\n'
        prompts = _extract_llm_prompts(source)
        assert prompts == [("Say hello", HTML)]

    def test_file_return_type(self):
        source = 'def greet() -> File(JSON, "out.json"):\n    "Say hello"\n'
        prompts = _extract_llm_prompts(source)
        assert prompts == [("Say hello", JSON)]

    def test_fstring_body_excluded(self):
        """F-string bodies have command_node but no static command string."""
        source = 'def render(title) -> HTML:\n    f"<h1>{title}</h1>"\n'
        assert _extract_llm_prompts(source) == []

    def test_empty_source(self):
        assert _extract_llm_prompts("") == []

    def test_syntax_error_raises(self):
        with pytest.raises(SyntaxError):
            _extract_llm_prompts("def broken(")

    def test_filters_web_commands(self):
        source = """\
def fetch() -> HTML:
    "https://example.com"

def summarize():
    "Summarize this article"
"""
        prompts = _extract_llm_prompts(source)
        assert len(prompts) == 1
        assert prompts[0] == ("Summarize this article", None)


class TestResolveTypeName:
    """Test type name string resolution."""

    @pytest.mark.parametrize(
        "name",
        ["HTML", "JSON", "XML", "CSV", "Markdown", "YAML", "TEXT", "TXT"],
    )
    def test_valid_names(self, name):
        resolved = _resolve_type_name(name)
        assert resolved is not None
        if name == "TXT":
            assert resolved is TEXT
        elif name == "HTML":
            assert resolved is HTML
        elif name == "JSON":
            assert resolved is JSON
        elif name == "XML":
            assert resolved is XML
        elif name == "CSV":
            assert resolved is CSV
        elif name == "Markdown":
            assert resolved is Markdown
        elif name == "YAML":
            assert resolved is YAML
        elif name == "TEXT":
            assert resolved is TEXT

    def test_none_input(self):
        assert _resolve_type_name(None) is None

    def test_empty_string(self):
        assert _resolve_type_name("") is None

    def test_invalid_name(self):
        assert _resolve_type_name("InvalidType") is None

    def test_non_base_type_attribute(self):
        assert _resolve_type_name("InputType") is None


class TestResolveReturnType:
    """Test return type resolution from parsed AST types."""

    def test_none(self):
        assert _resolve_return_type(None) is None

    def test_simple_return_type_valid(self):
        rt = SimpleReturnType(base_type="HTML", full_type="HTML")
        assert _resolve_return_type(rt) is HTML

    def test_simple_return_type_invalid(self):
        rt = SimpleReturnType(base_type="Unknown", full_type="Unknown")
        assert _resolve_return_type(rt) is None

    def test_parametric_return_type(self):
        rt = ParametricReturnType(
            base_type="JSON",
            inner_type="MyModel",
            full_type="JSON[MyModel]",
        )
        assert _resolve_return_type(rt) is JSON

    def test_file_write_with_inner(self):
        inner = SimpleReturnType(base_type="JSON", full_type="JSON")
        rt = FileWriteReturnType(path="out.json", inner_return_type=inner)
        assert _resolve_return_type(rt) is JSON

    def test_file_write_without_inner(self):
        rt = FileWriteReturnType(path="out.txt", inner_return_type=None)
        assert _resolve_return_type(rt) is None


class TestPrintPromptHeader:
    """Test prompt header formatting."""

    def test_short_prompt(self, capsys):
        _print_prompt_header(1, 3, "Hello world")
        out = capsys.readouterr().out
        assert "[1/3]" in out
        assert "Hello world" in out
        assert "..." not in out

    def test_long_prompt_truncated(self, capsys):
        long_prompt = "A" * 200
        _print_prompt_header(2, 5, long_prompt)
        out = capsys.readouterr().out
        assert "[2/5]" in out
        assert "..." in out
        assert "A" * 80 in out
        assert "A" * 81 not in out

    def test_newlines_replaced_with_spaces(self, capsys):
        _print_prompt_header(1, 1, "line1\nline2\nline3")
        out = capsys.readouterr().out
        assert "line1 line2 line3" in out
        assert "\nline2" not in out


class TestPrintAttemptResults:
    """Test coloured attempt results formatting."""

    def test_all_passes(self, capsys):
        result = EvaluationResult(
            minimum_working_model="openai:gpt-4o-mini",
            success=True,
            validation_pass_rate=100.0,
            attempts=[
                ModelAttemptResult(model="openai:gpt-4o-mini", success=True),
                ModelAttemptResult(model="openai:gpt-4o", success=True),
            ],
        )
        _print_attempt_results(result)
        out = capsys.readouterr().out
        assert out.count("PASS") == 2
        assert "FAIL" not in out
        assert "cheapest" in out
        assert "openai:gpt-4o-mini" in out

    def test_all_failures_with_errors(self, capsys):
        result = EvaluationResult(
            minimum_working_model=None,
            success=False,
            validation_pass_rate=0.0,
            attempts=[
                ModelAttemptResult(
                    model="openai:gpt-4o-mini",
                    success=False,
                    error="validation failed",
                ),
                ModelAttemptResult(
                    model="openai:gpt-4o",
                    success=False,
                    error="timeout",
                ),
            ],
        )
        _print_attempt_results(result)
        out = capsys.readouterr().out
        assert out.count("FAIL") == 2
        assert "validation failed" in out
        assert "timeout" in out
        assert "cheapest" not in out

    def test_mixed_results(self, capsys):
        result = EvaluationResult(
            minimum_working_model="openai:gpt-4o-mini",
            success=True,
            validation_pass_rate=50.0,
            attempts=[
                ModelAttemptResult(
                    model="openai:gpt-4o",
                    success=False,
                    error="bad output",
                ),
                ModelAttemptResult(model="openai:gpt-4o-mini", success=True),
            ],
        )
        _print_attempt_results(result)
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "PASS" in out
        assert "bad output" in out
        assert "cheapest" in out
        assert "openai:gpt-4o-mini" in out

    def test_with_cost_info(self, capsys):
        cost = ModelCost(input_tokens=100, output_tokens=50, total_cost_usd=0.003)
        result = EvaluationResult(
            minimum_working_model="openai:gpt-4o-mini",
            success=True,
            validation_pass_rate=100.0,
            attempts=[
                ModelAttemptResult(
                    model="openai:gpt-4o-mini",
                    success=True,
                    cost=cost,
                ),
            ],
        )
        _print_attempt_results(result)
        out = capsys.readouterr().out
        assert "$0.003000" in out
        assert "100 input" in out

    def test_without_cost_info(self, capsys):
        result = EvaluationResult(
            minimum_working_model=None,
            success=False,
            validation_pass_rate=0.0,
            attempts=[
                ModelAttemptResult(model="openai:gpt-4o-mini", success=False),
            ],
        )
        _print_attempt_results(result)
        out = capsys.readouterr().out
        assert "input tokens" not in out
        assert "openai:gpt-4o-mini" in out

    def test_minimum_working_model_only_when_success(self, capsys):
        result = EvaluationResult(
            minimum_working_model="openai:gpt-4o",
            success=False,
            validation_pass_rate=0.0,
            attempts=[
                ModelAttemptResult(model="openai:gpt-4o", success=False, error="err"),
            ],
        )
        _print_attempt_results(result)
        out = capsys.readouterr().out
        assert "cheapest" not in out
