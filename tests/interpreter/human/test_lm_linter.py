"""Tests for LmLinter rules."""

import tempfile
from pathlib import Path

import pytest

from lamia.lint.lm_linter import LmLinter
from lamia.lint.base import Severity


@pytest.fixture
def project_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _write(base: str, relpath: str, content: str) -> Path:
    p = Path(base) / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _violations_for(content: str, code: str, original: str = None,
                     cwd: str = None, filepath: str = None) -> list:
    linter = LmLinter()
    result = linter.lint(content, original, cwd=cwd, filepath=filepath)
    return [v for v in result.violations if v.rule.code == code]


# ── LMW001 excessive-growth ────────────────────────────────────────────────

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


# ── LME002 missing-required-params ──────────────────────────────────────────

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


# ── LMR003 output-format-hint ──────────────────────────────────────────────

class TestLMR003OutputFormatHint:

    def test_output_json_in_comment_triggers(self):
        content = '# Output JSON:\n# {"field": "value"}\nresult = agent(x=1) -> str'
        violations = _violations_for(content, "LMR003")
        assert len(violations) == 1

    def test_response_format_triggers(self):
        violations = _violations_for("# Response Format:", "LMR003")
        assert len(violations) == 1

    def test_response_schema_triggers(self):
        violations = _violations_for("# Response Schema:", "LMR003")
        assert len(violations) == 1

    def test_normal_code_no_violation(self):
        content = 'result = agent(prompt=p) -> JSON[MyModel]'
        violations = _violations_for(content, "LMR003")
        assert violations == []

    def test_mentions_pydantic_and_multiple_types(self):
        violations = _violations_for("# Output JSON:", "LMR003")
        msg = violations[0].message
        assert "Pydantic" in msg
        assert "HTML" in msg
        assert "YAML" in msg


# ── LMW005 tab-indentation ─────────────────────────────────────────────────

class TestLMW005TabIndentation:

    def test_tabs_trigger(self):
        content = "def foo():\n\treturn 1"
        violations = _violations_for(content, "LMW005")
        assert len(violations) == 1

    def test_spaces_no_violation(self):
        content = "def foo():\n    return 1"
        violations = _violations_for(content, "LMW005")
        assert violations == []

    def test_reports_line_count(self):
        content = "\tx = 1\n\ty = 2\n\tz = 3"
        violations = _violations_for(content, "LMW005")
        assert "3" in violations[0].message


# ── LMW006 positional-hu-args ──────────────────────────────────────────────

class TestLMW006PositionalHuArgs:

    def test_positional_args_triggers(self, project_dir):
        _write(project_dir, "team/summarize.hu", "Summarize {aspect}")
        content = 'result = summarize("key findings") -> HTML'
        violations = _violations_for(content, "LMW006", cwd=project_dir)
        assert len(violations) == 1

    def test_keyword_args_no_violation(self, project_dir):
        _write(project_dir, "team/summarize.hu", "Summarize {aspect}")
        content = 'result = summarize(aspect="key findings") -> HTML'
        violations = _violations_for(content, "LMW006", cwd=project_dir)
        assert violations == []

    def test_non_hu_function_ignored(self, project_dir):
        content = 'print("hello")'
        violations = _violations_for(content, "LMW006", cwd=project_dir)
        assert violations == []


# ── LMW007 empty-file ──────────────────────────────────────────────────────

class TestLMW007EmptyFile:

    def test_empty_triggers(self):
        violations = _violations_for("", "LMW007")
        assert len(violations) == 1

    def test_whitespace_only_triggers(self):
        violations = _violations_for("   \n  ", "LMW007")
        assert len(violations) == 1

    def test_real_content_no_violation(self):
        violations = _violations_for("x = 1", "LMW007")
        assert violations == []


# ── LMW008 trailing-whitespace ──────────────────────────────────────────────

class TestLMW008TrailingWhitespace:

    def test_trailing_spaces_trigger(self):
        violations = _violations_for("x = 1   \ny = 2", "LMW008")
        assert len(violations) == 1

    def test_no_trailing_no_violation(self):
        violations = _violations_for("x = 1\ny = 2", "LMW008")
        assert violations == []


# ── LMC009 variable-naming ─────────────────────────────────────────────────

class TestLMC009VariableNaming:

    def test_snake_case_no_violation(self):
        violations = _violations_for("my_var = 1", "LMC009")
        assert violations == []

    def test_camel_case_triggers(self):
        violations = _violations_for("myVar = 1", "LMC009")
        assert len(violations) == 1

    def test_pascal_case_allowed_for_classes(self):
        """PascalCase is allowed (Pydantic models)."""
        violations = _violations_for("MyModel = 1", "LMC009")
        assert violations == []

    def test_private_var_ignored(self):
        violations = _violations_for("_myPrivateVar = 1", "LMC009")
        assert violations == []


# ── LMC010 filename-naming ─────────────────────────────────────────────────

class TestLMC010FilenameNaming:

    def test_snake_case_no_violation(self):
        violations = _violations_for("x = 1", "LMC010", filepath="/path/orchestrator.lm")
        assert violations == []

    def test_pascal_case_triggers(self):
        violations = _violations_for("x = 1", "LMC010", filepath="/path/MyPipeline.lm")
        assert len(violations) == 1

    def test_kebab_case_triggers(self):
        violations = _violations_for("x = 1", "LMC010", filepath="/path/my-pipeline.lm")
        assert len(violations) == 1

    def test_no_filepath_no_violation(self):
        violations = _violations_for("x = 1", "LMC010")
        assert violations == []


# ── LMC011 leading-blank-lines ──────────────────────────────────────────────

class TestLMC011LeadingBlankLines:

    def test_leading_blank_triggers(self):
        violations = _violations_for("\n\nx = 1", "LMC011")
        assert len(violations) == 1

    def test_no_leading_blank_no_violation(self):
        violations = _violations_for("x = 1", "LMC011")
        assert violations == []


# ── LMR012 inline-pydantic-model ────────────────────────────────────────────

class TestLMR012InlinePydanticModel:

    def test_few_models_no_violation(self):
        content = "class A(BaseModel):\n    x: int\n\nclass B(BaseModel):\n    y: str"
        violations = _violations_for(content, "LMR012")
        assert violations == []

    def test_many_models_triggers(self):
        content = "\n".join(
            f"class M{i}(BaseModel):\n    x: int" for i in range(4)
        )
        violations = _violations_for(content, "LMR012")
        assert len(violations) == 4


# ── LMR013 long-script ─────────────────────────────────────────────────────

class TestLMR013LongScript:

    def test_short_script_no_violation(self):
        violations = _violations_for("x = 1", "LMR013")
        assert violations == []

    def test_long_script_triggers(self):
        content = "x" * 5001
        violations = _violations_for(content, "LMR013")
        assert len(violations) == 1
        assert "5001" in violations[0].message


# ── LME014 unknown-hu-kwargs ───────────────────────────────────────────────

class TestLME014UnknownHuKwargs:

    def test_unknown_kwarg_triggers(self, project_dir):
        _write(project_dir, "team/greet.hu", "Hello {name}")
        content = 'greet(name="Alice", age=30) -> TEXT'
        violations = _violations_for(content, "LME014", cwd=project_dir)
        assert len(violations) == 1
        assert "age" in violations[0].message

    def test_valid_kwargs_no_violation(self, project_dir):
        _write(project_dir, "team/greet.hu", "Hello {name}, you are {age}")
        content = 'greet(name="Alice", age=30) -> TEXT'
        violations = _violations_for(content, "LME014", cwd=project_dir)
        assert violations == []

    def test_multiple_unknown_kwargs(self, project_dir):
        _write(project_dir, "team/greet.hu", "Hello {name}")
        content = 'greet(name="Alice", age=30, city="NYC") -> TEXT'
        violations = _violations_for(content, "LME014", cwd=project_dir)
        assert len(violations) == 1
        assert "age" in violations[0].message
        assert "city" in violations[0].message

    def test_is_error_severity(self, project_dir):
        _write(project_dir, "team/greet.hu", "Hello {name}")
        content = 'greet(name="Alice", typo=1) -> TEXT'
        violations = _violations_for(content, "LME014", cwd=project_dir)
        assert violations[0].rule.severity == Severity.Error


# ── LMC015 generic-filename ────────────────────────────────────────────────

class TestLMC015GenericFilename:

    def test_generic_name_triggers(self):
        violations = _violations_for("x = 1", "LMC015", filepath="/path/process.lm")
        assert len(violations) == 1

    def test_generic_agent_triggers(self):
        violations = _violations_for("x = 1", "LMC015", filepath="/path/agent.lm")
        assert len(violations) == 1

    def test_descriptive_name_no_violation(self):
        violations = _violations_for("x = 1", "LMC015", filepath="/path/review_code.lm")
        assert violations == []

    def test_orchestrator_no_violation(self):
        violations = _violations_for("x = 1", "LMC015", filepath="/path/orchestrator.lm")
        assert violations == []


# ── Existing rules still work ───────────────────────────────────────────────

class TestLmLinterExistingRulesUnaffected:

    def test_clean_code_no_violations(self):
        linter = LmLinter()
        result = linter.lint('result = agent(prompt=p) -> JSON[MyModel]')
        assert result.clean
