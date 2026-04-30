"""Tests for LmLinter rules (LMW001, LME002)."""

import os
import tempfile
from pathlib import Path

import pytest

from lamia.lint.lm_linter import LmLinter


@pytest.fixture
def project_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _write(base: str, relpath: str, content: str) -> Path:
    p = Path(base) / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _violations_for(content: str, code: str, original: str = None, cwd: str = None) -> list:
    linter = LmLinter()
    result = linter.lint(content, original, cwd=cwd)
    return [v for v in result.violations if v.rule.code == code]


class TestLMW001ExcessiveGrowth:

    def test_no_growth_no_violation(self):
        violations = _violations_for("abc", "LMW001", original="ab")
        assert violations == []

    def test_double_growth_triggers(self):
        original = "x" * 100
        content = "x" * 250
        violations = _violations_for(content, "LMW001", original=original)
        assert len(violations) == 1

    def test_no_original_no_violation(self):
        violations = _violations_for("x" * 1000, "LMW001", original=None)
        assert violations == []

    def test_empty_original_no_crash(self):
        violations = _violations_for("x" * 100, "LMW001", original="")
        assert violations == []


class TestLME002MissingRequiredParams:

    def test_no_hu_files_no_violations(self, project_dir):
        content = "result = some_func(a=1) -> JSON[X]"
        violations = _violations_for(content, "LME002", cwd=project_dir)
        assert violations == []

    def test_all_required_params_passed(self, project_dir):
        _write(project_dir, "team/developer.hu", "Implement {specs} for {prd_content}")
        content = 'impl = developer(specs=s, prd_content=p) -> JSON[Impl]'
        violations = _violations_for(content, "LME002", cwd=project_dir)
        assert violations == []

    def test_missing_required_param_triggers(self, project_dir):
        _write(project_dir, "team/developer.hu", "Implement {specs} for {prd_content}")
        content = 'impl = developer(specs=s) -> JSON[Impl]'
        violations = _violations_for(content, "LME002", cwd=project_dir)
        assert len(violations) == 1
        assert "prd_content" in violations[0].message

    def test_optional_params_not_required(self, project_dir):
        _write(project_dir, "team/pm.hu", "Do {task} with {extra:None}")
        content = 'result = pm(task=t) -> JSON[X]'
        violations = _violations_for(content, "LME002", cwd=project_dir)
        assert violations == []

    def test_multiple_missing_params(self, project_dir):
        _write(project_dir, "team/worker.hu", "{a} {b} {c}")
        content = 'result = worker(a=1) -> JSON[X]'
        violations = _violations_for(content, "LME002", cwd=project_dir)
        assert len(violations) == 1
        assert "b" in violations[0].message
        assert "c" in violations[0].message

    def test_non_hu_function_ignored(self, project_dir):
        content = 'result = print(x=1) -> JSON[X]'
        violations = _violations_for(content, "LME002", cwd=project_dir)
        assert violations == []

    def test_no_cwd_skips_check(self):
        content = 'impl = developer(specs=s) -> JSON[Impl]'
        violations = _violations_for(content, "LME002", cwd=None)
        assert violations == []

    def test_hu_in_subdirectory_found(self, project_dir):
        _write(project_dir, "deeply/nested/agent.hu", "{prompt} {context}")
        content = 'r = agent(prompt=p) -> JSON[X]'
        violations = _violations_for(content, "LME002", cwd=project_dir)
        assert len(violations) == 1
        assert "context" in violations[0].message
