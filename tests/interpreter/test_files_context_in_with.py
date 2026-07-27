"""Tests for LLM functions defined inside ``with files()`` blocks.

Covers every placement variant the Python scoping rules allow:

    DEFINE-INSIDE / CALL-OUTSIDE   — function captures context at definition
    DEFINE-INSIDE / CALL-INSIDE    — context active at both times
    DEFINE-OUTSIDE / CALL-INSIDE   — classic pattern (always worked)

Also covers: params, file refs, multiple funcs, nested with-blocks, async,
file-write return types, and all edge cases.
"""

import ast
import os
import tempfile
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from lamia.engine.managers.llm.files_context_manager import (
    CapturedFilesContext,
    FilesContext,
    _context_stack,
    capture_files_context,
    files,
    get_active_files_context,
)
from lamia.interpreter.hybrid_syntax_parser import HybridSyntaxParser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _transform(source: str) -> str:
    return HybridSyntaxParser().transform(source)


def _has_capture(transformed: str) -> bool:
    return 'capture_files_context' in transformed


def _has_enter_exit(transformed: str) -> bool:
    return '__enter__' in transformed and '__exit__' in transformed


# ---------------------------------------------------------------------------
# CapturedFilesContext unit tests
# ---------------------------------------------------------------------------

class TestCapturedFilesContext:

    def test_enter_pushes_context_onto_stack(self, tmp_path):
        (tmp_path / "a.txt").write_text("hello")
        snapshot = CapturedFilesContext([str(tmp_path / "a.txt")])
        assert get_active_files_context() is None
        ctx = snapshot.__enter__()
        try:
            assert get_active_files_context() is ctx
            assert str(tmp_path / "a.txt") in ctx.indexed_files
        finally:
            snapshot.__exit__(None, None, None)

    def test_exit_pops_context_from_stack(self, tmp_path):
        (tmp_path / "b.txt").write_text("world")
        snapshot = CapturedFilesContext([str(tmp_path / "b.txt")])
        snapshot.__enter__()
        snapshot.__exit__(None, None, None)
        assert get_active_files_context() is None

    def test_indexed_files_are_copied_not_shared(self, tmp_path):
        f = str(tmp_path / "f.txt")
        original = [f]
        snap = CapturedFilesContext(original)
        original.clear()
        ctx = snap.__enter__()
        try:
            assert f in ctx.indexed_files
        finally:
            snap.__exit__(None, None, None)

    def test_entered_flag_set_on_enter(self, tmp_path):
        (tmp_path / "c.txt").write_text("content")
        snap = CapturedFilesContext([str(tmp_path / "c.txt")])
        ctx = snap.__enter__()
        try:
            assert ctx._entered is True
        finally:
            snap.__exit__(None, None, None)

    def test_re_entered_creates_fresh_context(self, tmp_path):
        (tmp_path / "d.txt").write_text("data")
        snap = CapturedFilesContext([str(tmp_path / "d.txt")])

        ctx1 = snap.__enter__()
        snap.__exit__(None, None, None)

        ctx2 = snap.__enter__()
        snap.__exit__(None, None, None)

        assert ctx1 is not ctx2

    def test_multiple_sequential_calls_stack_balances(self, tmp_path):
        (tmp_path / "e.txt").write_text("e")
        snap = CapturedFilesContext([str(tmp_path / "e.txt")])
        for _ in range(3):
            snap.__enter__()
            snap.__exit__(None, None, None)
        assert get_active_files_context() is None


# ---------------------------------------------------------------------------
# capture_files_context() unit tests
# ---------------------------------------------------------------------------

class TestCaptureFilesContext:

    def test_returns_none_when_no_context_active(self):
        assert capture_files_context() is None

    def test_captures_indexed_files(self, tmp_path):
        (tmp_path / "resume.pdf").write_text("resume")
        with files(str(tmp_path)):
            snap = capture_files_context()
        assert snap is not None
        assert any("resume.pdf" in f for f in snap._indexed_files)

    def test_capture_after_exit_still_holds_files(self, tmp_path):
        (tmp_path / "cover.txt").write_text("cover")
        with files(str(tmp_path)):
            snap = capture_files_context()
        assert snap is not None
        assert any("cover.txt" in f for f in snap._indexed_files)

    def test_nested_capture_gets_top_context(self, tmp_path):
        inner = tmp_path / "inner"
        inner.mkdir()
        (inner / "inner.txt").write_text("i")
        outer = tmp_path / "outer"
        outer.mkdir()
        (outer / "outer.txt").write_text("o")

        with files(str(outer)):
            with files(str(inner)):
                snap = capture_files_context()

        assert snap is not None
        assert any("inner.txt" in f for f in snap._indexed_files)


# ---------------------------------------------------------------------------
# AST transformation tests — structure checks
# ---------------------------------------------------------------------------

class TestTransformationStructure:

    def test_llm_func_inside_with_files_gets_capture(self):
        src = """
with files("~/Documents/"):
    def summarize():
        "Summarize {@doc.txt}"
"""
        t = _transform(src)
        assert _has_capture(t), "Expected capture_files_context() in transformed code"

    def test_llm_func_outside_with_files_no_capture(self):
        src = """
def summarize():
    "Summarize {@doc.txt}"
"""
        t = _transform(src)
        assert not _has_capture(t)

    def test_capture_variable_appears_before_function(self):
        src = """
with files("~/Documents/"):
    def answer(question: str):
        "Answer {question} using {@resume.pdf}"
"""
        t = _transform(src)
        cap_idx = t.find('capture_files_context')
        func_idx = t.find('def answer(')
        assert cap_idx < func_idx, "capture_files_context must appear before function def"

    def test_enter_exit_injected_into_function_body(self):
        src = """
with files("~/Documents/"):
    def extract_name():
        "Extract name from {@resume.pdf}"
"""
        t = _transform(src)
        assert _has_enter_exit(t)

    def test_multiple_llm_funcs_each_get_capture(self):
        src = """
with files("~/Documents/"):
    def func_a():
        "Do A with {@a.txt}"

    def func_b():
        "Do B with {@b.txt}"
"""
        t = _transform(src)
        assert t.count('capture_files_context') == 2
        assert '__lamia_files_ctx_0' in t
        assert '__lamia_files_ctx_1' in t

    def test_non_llm_func_inside_with_no_capture(self):
        src = """
with files("~/Documents/"):
    def helper():
        return 42
"""
        t = _transform(src)
        assert not _has_capture(t)

    def test_async_llm_func_inside_with_gets_capture(self):
        src = """
with files("~/Documents/"):
    async def async_summarize():
        "Summarize {@doc.txt}"
"""
        t = _transform(src)
        assert _has_capture(t)
        assert _has_enter_exit(t)

    def test_nested_with_files_each_captured(self):
        src = """
with files("~/outer/"):
    def outer_func():
        "Outer {@out.txt}"

    with files("~/inner/"):
        def inner_func():
            "Inner {@in.txt}"
"""
        t = _transform(src)
        assert t.count('capture_files_context') == 2

    def test_with_files_and_session_func_gets_capture(self):
        src = """
with files("~/docs/"):
    def qa(question: str):
        "Answer {question} using {@guide.txt}"
"""
        t = _transform(src)
        assert _has_capture(t)
        assert _has_enter_exit(t)

    def test_func_with_models_param_and_files_context(self):
        src = """
with files("~/docs/"):
    def extract(models="openai:gpt-4"):
        "Extract skills from {@resume.pdf}"
"""
        t = _transform(src)
        assert _has_capture(t)
        assert _has_enter_exit(t)

    def test_transformed_code_is_valid_python(self):
        src = """
with files("~/Documents/"):
    def summarize(topic: str):
        "Summarize {topic} from {@notes.txt}"
"""
        t = _transform(src)
        # Must parse without SyntaxError
        ast.parse(t)

    def test_capture_variable_used_in_enter_exit(self):
        src = """
with files("~/docs/"):
    def lookup():
        "Look up {@index.txt}"
"""
        t = _transform(src)
        assert '__lamia_files_ctx_0.__enter__' in t
        assert '__lamia_files_ctx_0.__exit__' in t

    def test_func_with_return_type_annotation_inside_with(self):
        src = """
with files("~/docs/"):
    def get_summary() -> str:
        "Summarize {@data.txt}"
"""
        t = _transform(src)
        assert _has_capture(t)

    def test_function_defined_outside_not_affected(self):
        src = """
def outside():
    "Summarize something"

with files("~/docs/"):
    x = outside()
"""
        t = _transform(src)
        # 'outside' should not have capture wrapping
        assert 'capture_files_context' not in t

    def test_with_as_clause_still_captures(self):
        src = """
with files("~/docs/") as ctx:
    def describe():
        "Describe {@doc.txt}"
"""
        t = _transform(src)
        assert _has_capture(t)


# ---------------------------------------------------------------------------
# Runtime behaviour tests — actual context activation
# ---------------------------------------------------------------------------

class TestRuntimeContextBehaviour:

    def test_captured_context_restored_when_called_outside(self, tmp_path):
        (tmp_path / "data.txt").write_text("hello world")

        with files(str(tmp_path)):
            snap = capture_files_context()

        assert get_active_files_context() is None
        ctx = snap.__enter__()
        try:
            assert get_active_files_context() is not None
            assert any("data.txt" in f for f in get_active_files_context().indexed_files)
        finally:
            snap.__exit__(None, None, None)
        assert get_active_files_context() is None

    def test_context_not_active_outside_without_capture(self, tmp_path):
        (tmp_path / "x.txt").write_text("x")
        with files(str(tmp_path)):
            pass
        assert get_active_files_context() is None

    def test_captured_context_can_resolve_file_reference(self, tmp_path):
        content = "Skills: Python, Go"
        (tmp_path / "resume.pdf").write_text(content)

        with files(str(tmp_path)):
            snap = capture_files_context()

        ctx = snap.__enter__()
        try:
            resolved = ctx.resolve_file_reference("resume.pdf")
            assert "resume.pdf" in resolved
        finally:
            snap.__exit__(None, None, None)

    def test_called_multiple_times_stack_always_balanced(self, tmp_path):
        (tmp_path / "f.txt").write_text("f")
        with files(str(tmp_path)):
            snap = capture_files_context()

        for _ in range(5):
            ctx = snap.__enter__()
            assert get_active_files_context() is ctx
            snap.__exit__(None, None, None)
            assert get_active_files_context() is None

    def test_called_inside_another_files_context(self, tmp_path):
        inner_dir = tmp_path / "inner"
        inner_dir.mkdir()
        outer_dir = tmp_path / "outer"
        outer_dir.mkdir()
        (outer_dir / "o.txt").write_text("outer")
        (inner_dir / "i.txt").write_text("inner")

        with files(str(inner_dir)):
            snap = capture_files_context()

        with files(str(outer_dir)):
            # Now inside outer context, activate inner via captured snap
            ctx = snap.__enter__()
            try:
                # Top of stack is the captured inner context
                assert get_active_files_context() is ctx
                assert any("i.txt" in f for f in ctx.indexed_files)
            finally:
                snap.__exit__(None, None, None)
            # After exit we should be back to outer context
            assert any("o.txt" in f for f in get_active_files_context().indexed_files)

    def test_empty_directory_capture(self, tmp_path):
        with files(str(tmp_path)):
            snap = capture_files_context()

        assert snap is not None
        ctx = snap.__enter__()
        try:
            assert ctx.indexed_files == []
        finally:
            snap.__exit__(None, None, None)

    def test_capture_outside_context_returns_none(self):
        snap = capture_files_context()
        assert snap is None



class TestDefineInsideCallOutside:

    def test_parser_transform_define_inside_call_outside(self):
        src = """
with files("~/Documents/"):
    def extract_name():
        "Extract full name from {@resume.pdf}"

result = extract_name()
"""
        t = _transform(src)
        assert _has_capture(t)
        assert _has_enter_exit(t)
        ast.parse(t)  # must be valid Python

    def test_parser_transform_define_outside_call_inside(self):
        src = """
def answer(question: str):
    "Answer {question}"

with files("~/Documents/"):
    result = answer(question="hello")
"""
        t = _transform(src)
        assert not _has_capture(t)
        ast.parse(t)

    def test_parser_transform_multiple_dirs_define_inside(self):
        src = """
with files("~/Documents/", "~/projects/"):
    def answer_question(question: str):
        \"\"\"
        Answer: {question}

        Use information from {@resume.pdf} and {@cover_letter.txt}
        \"\"\"

answer = answer_question(question="What are my main skills?")
"""
        t = _transform(src)
        assert _has_capture(t)
        assert _has_enter_exit(t)
        ast.parse(t)



class TestModelsParameterInFilesContext:
    """Ensure functions with models= default defined inside with files() work correctly."""

    def _lamia_run_call_contains(self, transformed: str, substring: str) -> bool:
        """Check if substring appears in a lamia.run(...) call line."""
        for line in transformed.splitlines():
            if "lamia.run(" in line and substring in line:
                return True
        return False

    def test_models_string_default_uses_variable_ref(self):
        """models='openai:gpt-4' default: lamia.run() must use models=models, not the constant."""
        src = """
with files("~/Documents/"):
    def compare(models="openai:gpt-4"):
        "Compare {@resume_v1.pdf} and {@resume_v2.pdf}"
result = compare()
"""
        t = _transform(src)
        assert self._lamia_run_call_contains(t, "models=models")
        assert not self._lamia_run_call_contains(t, "models='openai:gpt-4'")
        assert _has_capture(t)
        ast.parse(t)

    def test_compile_with_files_and_models_default(self):
        """with files() + models= default must compile without invalid column ranges."""
        src = """
with files("~/Documents"):
    def get_name(models="openai:gpt-4"):
        "Extract name from {@resume.txt}"

name = get_name()
"""
        code = HybridSyntaxParser().compile(src)
        assert code is not None

    def test_models_list_default_uses_variable_ref(self):
        """models=['a', 'b'] default: lamia.run() must reference the variable."""
        src = """
with files("~/Documents/"):
    def extract(models=["openai:gpt-4", "anthropic:claude-3"]):
        "Extract from {@data.txt}"
result = extract()
"""
        t = _transform(src)
        assert self._lamia_run_call_contains(t, "models=models")
        assert _has_capture(t)
        ast.parse(t)

    def test_models_none_default_uses_variable_ref(self):
        """models=None still injects models=models into lamia.run()."""
        src = """
with files("~/Documents/"):
    def run_task(models=None):
        "Run the task with {@context.txt}"
"""
        t = _transform(src)
        assert self._lamia_run_call_contains(t, "models=models")
        ast.parse(t)

    def test_models_outside_with_also_uses_variable_ref(self):
        """models= in a function defined OUTSIDE with files also uses variable ref."""
        src = """
def summarize(models="openai:gpt-4"):
    "Summarize this document"
"""
        t = _transform(src)
        assert self._lamia_run_call_contains(t, "models=models")
        assert not self._lamia_run_call_contains(t, "models='openai:gpt-4'")
        ast.parse(t)

    def test_define_inside_with_models_and_params(self):
        """Function with both models= and other params defined inside with files."""
        src = """
with files("~/Documents/"):
    def answer(question: str, models="openai:gpt-4"):
        "Answer {question} using {@resume.pdf}"
result = answer(question="What are my skills?")
"""
        t = _transform(src)
        assert self._lamia_run_call_contains(t, "models=models")
        assert _has_capture(t)
        assert _has_enter_exit(t)
        ast.parse(t)



class TestAllDefinitionCallPlacements:



    def test_define_inside_call_outside_no_params(self):
        """Canonical pattern: define inside with files, call outside."""
        src = """
with files("~/docs/"):
    def get_name():
        "Extract name from {@resume.pdf}"
result = get_name()
"""
        t = _transform(src)
        assert _has_capture(t)
        assert _has_enter_exit(t)
        ast.parse(t)

    def test_define_inside_call_outside_with_str_param(self):
        """Define inside, call outside with a string parameter."""
        src = """
with files("~/docs/"):
    def answer(question: str):
        "Answer {question} from {@resume.pdf}"
r = answer(question="What is my experience?")
"""
        t = _transform(src)
        assert _has_capture(t)
        ast.parse(t)

    def test_define_inside_call_outside_with_models_string(self):
        """Define inside with models='provider:model', call outside."""
        src = """
with files("~/docs/"):
    def extract(models="openai:gpt-4"):
        "Extract from {@resume.pdf}"
result = extract()
"""
        t = _transform(src)
        assert _has_capture(t)
        assert "models=models" in t
        ast.parse(t)

    def test_define_inside_call_outside_with_models_override(self):
        """Caller can override the model when calling outside the with block."""
        src = """
with files("~/docs/"):
    def compare(models="openai:gpt-4"):
        "Compare documents"
r1 = compare()
r2 = compare(models="anthropic:claude-3")
"""
        t = _transform(src)
        assert "models=models" in t
        assert _has_capture(t)
        ast.parse(t)

    def test_define_inside_call_outside_captured_variable_default(self):
        """Python-like capture: variable default evaluated at definition time."""
        src = """
default_model = "openai:gpt-4"
with files("~/docs/"):
    def run(models=default_model):
        "Run with {@context.txt}"
result = run()
"""
        t = _transform(src)
        assert _has_capture(t)
        ast.parse(t)

    def test_define_outside_call_inside_no_files_ctx_var(self):
        """Classic pattern: define outside, call inside; no capture injection needed."""
        src = """
def answer(question: str):
    "Answer {question}"

with files("~/docs/"):
    result = answer(question="hello")
"""
        t = _transform(src)
        assert not _has_capture(t)
        ast.parse(t)

    def test_define_outside_call_inside_with_models(self):
        """Define outside with models=, call inside; context active at call time."""
        src = """
def summarize(models="openai:gpt-4"):
    "Summarize the document"

with files("~/docs/"):
    result = summarize()
"""
        t = _transform(src)
        assert not _has_capture(t)
        assert "models=models" in t
        ast.parse(t)

    def test_define_inside_call_inside(self):
        """Both define and call inside the with block; capture still injected."""
        src = """
with files("~/docs/"):
    def extract():
        "Extract from {@resume.pdf}"
    result = extract()
"""
        t = _transform(src)
        assert _has_capture(t)
        ast.parse(t)

    def test_define_inside_call_inside_with_models(self):
        """Both define and call inside; models= uses variable ref."""
        src = """
with files("~/docs/"):
    def compare(models="openai:gpt-4"):
        "Compare docs"
    result = compare()
"""
        t = _transform(src)
        assert "models=models" in t
        assert _has_capture(t)
        ast.parse(t)

    def test_multiple_funcs_define_inside_call_outside(self):
        """Multiple functions defined inside with files(), all called outside."""
        src = """
with files("~/docs/"):
    def func_a():
        "Do A with {@a.txt}"
    def func_b(models="openai:gpt-4"):
        "Do B with {@b.txt}"
    def func_c(q: str):
        "Do C: {q}"

ra = func_a()
rb = func_b()
rc = func_c(q="hello")
"""
        t = _transform(src)
        assert t.count("capture_files_context") == 3
        assert t.count("models=models") == 1
        assert _has_enter_exit(t)
        ast.parse(t)

    def test_mixed_define_inside_and_outside(self):
        """Some functions inside with files, some outside; each handled correctly."""
        src = """
def helper():
    "General helper"

with files("~/docs/"):
    def contextual():
        "Contextual {@doc.txt}"

r1 = helper()
r2 = contextual()
"""
        t = _transform(src)
        assert t.count("capture_files_context") == 1
        ast.parse(t)

    def test_async_define_inside_call_outside(self):
        """Async function defined inside with files(), called outside."""
        src = """
with files("~/docs/"):
    async def async_extract():
        "Extract from {@resume.pdf}"

import asyncio
result = asyncio.run(async_extract())
"""
        t = _transform(src)
        assert _has_capture(t)
        assert "async def async_extract" in t
        ast.parse(t)

    def test_async_define_inside_with_models_call_outside(self):
        """Async function with models= defined inside, called outside."""
        src = """
with files("~/docs/"):
    async def async_compare(models="openai:gpt-4"):
        "Compare {@doc1.txt} and {@doc2.txt}"

import asyncio
result = asyncio.run(async_compare())
"""
        t = _transform(src)
        assert _has_capture(t)
        assert "models=models" in t
        ast.parse(t)

    def test_nested_with_define_in_inner_call_outside(self):
        """Function defined in the inner with files() block, called outside both."""
        src = """
with files("~/outer/"):
    with files("~/inner/"):
        def inner_func():
            "Use {@inner_doc.txt}"

result = inner_func()
"""
        t = _transform(src)
        assert _has_capture(t)
        ast.parse(t)

    def test_nested_with_define_in_outer_call_outside(self):
        """Function defined in the outer with files() block, inner is unrelated."""
        src = """
with files("~/outer/"):
    def outer_func():
        "Use {@outer_doc.txt}"
    with files("~/inner/"):
        x = 1

result = outer_func()
"""
        t = _transform(src)
        assert _has_capture(t)
        ast.parse(t)

    def test_function_with_return_type_annotation_define_inside(self):
        """Function with -> str annotation defined inside with files()."""
        src = """
with files("~/docs/"):
    def get_name() -> str:
        "Extract name from {@resume.pdf}"
result = get_name()
"""
        t = _transform(src)
        assert _has_capture(t)
        ast.parse(t)

    def test_function_with_many_params_define_inside(self):
        """Function with many parameters defined inside with files()."""
        src = """
with files("~/docs/"):
    def analyze(question: str, context: str, models="openai:gpt-4"):
        "Analyze {question} in context of {context} from {@report.pdf}"
result = analyze(question="Q", context="C")
"""
        t = _transform(src)
        assert _has_capture(t)
        assert "models=models" in t
        ast.parse(t)

    def test_docstring_only_function_not_captured(self):
        """Non-LLM helper function inside with files() is NOT wrapped."""
        src = """
with files("~/docs/"):
    def helper():
        return "hello"
result = helper()
"""
        t = _transform(src)
        assert not _has_capture(t)
        ast.parse(t)
