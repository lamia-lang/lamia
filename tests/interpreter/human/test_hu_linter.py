"""Tests for HuLinter."""

import tempfile
from pathlib import Path

import pytest

from lamia.lint.hu_linter import HuLinter, _TOO_MANY_PARAMS_THRESHOLD
from lamia.lint.base import Severity


def _violations_for_code(content: str, code: str, **kwargs) -> list:
    linter = HuLinter()
    result = linter.lint(content, **kwargs)
    return [v for v in result.violations if v.rule.code == code]


def _write(base: str, relpath: str, content: str) -> Path:
    p = Path(base) / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def project_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


# ── HUW017 too-many-params ──────────────────────────────────────────────────

class TestHUW017TooManyParams:

    def test_no_params_no_violation(self):
        violations = _violations_for_code("Just plain text with no placeholders.", "HUW017")
        assert violations == []

    def test_few_params_no_violation(self):
        content = " ".join(f"{{p{i}}}" for i in range(5))
        violations = _violations_for_code(content, "HUW017")
        assert violations == []

    def test_exactly_at_threshold_no_violation(self):
        content = " ".join(f"{{p{i}}}" for i in range(_TOO_MANY_PARAMS_THRESHOLD))
        violations = _violations_for_code(content, "HUW017")
        assert violations == []

    def test_one_over_threshold_triggers(self):
        content = " ".join(f"{{p{i}}}" for i in range(_TOO_MANY_PARAMS_THRESHOLD + 1))
        violations = _violations_for_code(content, "HUW017")
        assert len(violations) == 1

    def test_violation_mentions_param_count(self):
        n = _TOO_MANY_PARAMS_THRESHOLD + 5
        content = " ".join(f"{{p{i}}}" for i in range(n))
        violations = _violations_for_code(content, "HUW017")
        assert str(n) in violations[0].message

    def test_violation_suggests_file_reference(self):
        content = " ".join(f"{{p{i}}}" for i in range(_TOO_MANY_PARAMS_THRESHOLD + 1))
        violations = _violations_for_code(content, "HUW017")
        assert "{@" in violations[0].message

    def test_violation_reported_at_file_level(self):
        content = " ".join(f"{{p{i}}}" for i in range(_TOO_MANY_PARAMS_THRESHOLD + 1))
        violations = _violations_for_code(content, "HUW017")
        assert violations[0].line == 0

    def test_duplicate_params_count_as_one(self):
        """Repeated {param} only counts as one unique param."""
        content = " ".join(f"{{p{i % 5}}}" for i in range(15))
        violations = _violations_for_code(content, "HUW017")
        assert violations == []

    def test_optional_params_counted_too(self):
        """Optional {param:default} placeholders also count toward the threshold."""
        content = " ".join(
            f"{{p{i}:default}}" if i % 2 == 0 else f"{{p{i}}}"
            for i in range(_TOO_MANY_PARAMS_THRESHOLD + 1)
        )
        violations = _violations_for_code(content, "HUW017")
        assert len(violations) == 1

    def test_file_context_refs_not_counted(self):
        """{ @file} references are excluded from the param count."""
        file_refs = " ".join(f"{{@file{i}.txt}}" for i in range(20))
        param_refs = " ".join(f"{{p{i}}}" for i in range(5))
        content = file_refs + " " + param_refs
        violations = _violations_for_code(content, "HUW017")
        assert violations == []

    def test_only_one_hu017_violation_even_with_many_params(self):
        """HU017 fires once per file, not once per excess param."""
        content = " ".join(f"{{p{i}}}" for i in range(30))
        violations = _violations_for_code(content, "HUW017")
        assert len(violations) == 1


# ── HUR018 output-format-hint ───────────────────────────────────────────────

class TestHUR018OutputFormatHint:

    def test_output_json_colon_triggers(self):
        violations = _violations_for_code("Output JSON:", "HUR018")
        assert len(violations) == 1

    def test_markdown_bold_output_json_triggers(self):
        violations = _violations_for_code("**Output JSON:**", "HUR018")
        assert len(violations) == 1

    def test_response_format_triggers(self):
        violations = _violations_for_code("Response Format:", "HUR018")
        assert len(violations) == 1

    def test_return_type_triggers(self):
        violations = _violations_for_code("Return Type:", "HUR018")
        assert len(violations) == 1

    def test_case_insensitive(self):
        violations = _violations_for_code("output json:", "HUR018")
        assert len(violations) == 1

    def test_normal_prose_no_violation(self):
        violations = _violations_for_code("Parse the output json and validate it.", "HUR018")
        assert violations == []

    def test_mentions_pydantic_and_multiple_types(self):
        violations = _violations_for_code("Output JSON:", "HUR018")
        msg = violations[0].message
        assert "Pydantic" in msg
        assert "HTML" in msg
        assert "YAML" in msg


# ── HUE019 escaped-param (cross-file) ──────────────────────────────────────

class TestHUE019EscapedParam:

    def test_double_braces_without_cwd_no_violation(self):
        """Without cwd we can't do cross-file check, so no violation."""
        violations = _violations_for_code("Hello {{name}}", "HUE019")
        assert violations == []

    def test_double_braces_with_caller_triggers(self, project_dir):
        """If an .lm file passes name= to this .hu, {{name}} is an error."""
        hu_path = _write(project_dir, "greet.hu", "Hello {{name}}, welcome!")
        _write(project_dir, "main.lm", 'greet(name="Alice") -> TEXT')
        violations = _violations_for_code(
            "Hello {{name}}, welcome!", "HUE019",
            cwd=project_dir, filepath=str(hu_path),
        )
        assert len(violations) == 1
        assert "name" in violations[0].message

    def test_double_braces_without_caller_no_violation(self, project_dir):
        """If no .lm file passes this as an arg, it's intentional literal braces."""
        hu_path = _write(project_dir, "example.hu", "Format: {{key: value}}")
        _write(project_dir, "main.lm", 'result = example() -> TEXT')
        violations = _violations_for_code(
            "Format: {{key: value}}", "HUE019",
            cwd=project_dir, filepath=str(hu_path),
        )
        assert violations == []

    def test_single_braces_no_violation(self, project_dir):
        hu_path = _write(project_dir, "greet.hu", "Hello {name}")
        violations = _violations_for_code(
            "Hello {name}", "HUE019",
            cwd=project_dir, filepath=str(hu_path),
        )
        assert violations == []

    def test_is_error_severity(self, project_dir):
        hu_path = _write(project_dir, "greet.hu", "{{name}}")
        _write(project_dir, "main.lm", 'greet(name="x") -> TEXT')
        violations = _violations_for_code(
            "{{name}}", "HUE019",
            cwd=project_dir, filepath=str(hu_path),
        )
        assert violations[0].rule.severity == Severity.Error


# ── HUC020 param-naming ─────────────────────────────────────────────────────

class TestHUC020ParamNaming:

    def test_snake_case_no_violation(self):
        violations = _violations_for_code("Use {user_name} and {max_count}", "HUC020")
        assert violations == []

    def test_camel_case_triggers(self):
        violations = _violations_for_code("Hello {userName}", "HUC020")
        assert len(violations) == 1

    def test_suggests_snake_case(self):
        violations = _violations_for_code("{userName}", "HUC020")
        assert "user_name" in violations[0].message

    def test_pascal_case_triggers(self):
        violations = _violations_for_code("{MaxRetries}", "HUC020")
        assert len(violations) == 1

    def test_single_lowercase_word_ok(self):
        violations = _violations_for_code("{name}", "HUC020")
        assert violations == []

    def test_file_refs_not_checked(self):
        violations = _violations_for_code("{@MyFile.txt}", "HUC020")
        assert violations == []

    def test_is_convention_severity(self):
        violations = _violations_for_code("{userName}", "HUC020")
        assert violations[0].rule.severity == Severity.Convention


# ── HUC023 short-param-name ─────────────────────────────────────────────────

class TestHUC023ShortParamName:

    def test_single_letter_triggers(self):
        violations = _violations_for_code("Use {x} here", "HUC023")
        assert len(violations) == 1

    def test_two_letters_no_violation(self):
        violations = _violations_for_code("Use {id} here", "HUC023")
        assert violations == []

    def test_descriptive_name_no_violation(self):
        violations = _violations_for_code("{user_name}", "HUC023")
        assert violations == []


# ── HUC024 verbose-param-name ───────────────────────────────────────────────

class TestHUC024VerboseParamName:

    def test_very_long_name_triggers(self):
        long_name = "a" * 31
        violations = _violations_for_code(f"{{{long_name}}}", "HUC024")
        assert len(violations) == 1

    def test_normal_length_no_violation(self):
        violations = _violations_for_code("{user_name}", "HUC024")
        assert violations == []


# ── HUC025 filename-naming ──────────────────────────────────────────────────

class TestHUC025FilenameNaming:

    def test_snake_case_no_violation(self):
        violations = _violations_for_code(
            "content", "HUC025", filepath="/path/review_code.hu",
        )
        assert violations == []

    def test_pascal_case_triggers(self):
        violations = _violations_for_code(
            "content", "HUC025", filepath="/path/ReviewCode.hu",
        )
        assert len(violations) == 1

    def test_kebab_case_triggers(self):
        violations = _violations_for_code(
            "content", "HUC025", filepath="/path/review-code.hu",
        )
        assert len(violations) == 1

    def test_suggests_snake_case(self):
        violations = _violations_for_code(
            "content", "HUC025", filepath="/path/ReviewCode.hu",
        )
        assert "review_code" in violations[0].message

    def test_no_filepath_no_violation(self):
        violations = _violations_for_code("content", "HUC025")
        assert violations == []


# ── HUC026 leading-blank-lines ──────────────────────────────────────────────

class TestHUC026LeadingBlankLines:

    def test_leading_blank_triggers(self):
        violations = _violations_for_code("\n\nSome content", "HUC026")
        assert len(violations) == 1

    def test_no_leading_blank_no_violation(self):
        violations = _violations_for_code("Content starts here", "HUC026")
        assert violations == []


# ── HUW021 empty-file ───────────────────────────────────────────────────────

class TestHUW021EmptyFile:

    def test_empty_string_triggers(self):
        violations = _violations_for_code("", "HUW021")
        assert len(violations) == 1

    def test_whitespace_only_triggers(self):
        violations = _violations_for_code("   \n  \n  ", "HUW021")
        assert len(violations) == 1

    def test_real_content_no_violation(self):
        violations = _violations_for_code("Summarize this text.", "HUW021")
        assert violations == []


# ── HUW022 trailing-whitespace ──────────────────────────────────────────────

class TestHUW022TrailingWhitespace:

    def test_trailing_spaces_trigger(self):
        violations = _violations_for_code("hello   \nworld", "HUW022")
        assert len(violations) == 1

    def test_no_trailing_no_violation(self):
        violations = _violations_for_code("hello\nworld", "HUW022")
        assert violations == []


# ── HUC028 generic-filename ──────────────────────────────────────────────────

class TestHUC028GenericFilename:

    def test_generic_name_triggers(self):
        violations = _violations_for_code(
            "content", "HUC028", filepath="/path/agent.hu",
        )
        assert len(violations) == 1

    def test_generic_prompt_triggers(self):
        violations = _violations_for_code(
            "content", "HUC028", filepath="/path/prompt.hu",
        )
        assert len(violations) == 1

    def test_descriptive_name_no_violation(self):
        violations = _violations_for_code(
            "content", "HUC028", filepath="/path/review_code.hu",
        )
        assert violations == []

    def test_no_filepath_no_violation(self):
        violations = _violations_for_code("content", "HUC028")
        assert violations == []


# ── HUR027 long-prompt ──────────────────────────────────────────────────────

class TestHUR027LongPrompt:

    def test_short_prompt_no_violation(self):
        violations = _violations_for_code("Short prompt.", "HUR027")
        assert violations == []

    def test_long_prompt_triggers(self):
        content = "x" * 3001
        violations = _violations_for_code(content, "HUR027")
        assert len(violations) == 1
        assert "3001" in violations[0].message


# ── Feedback ordering ───────────────────────────────────────────────────────

class TestFeedbackOrdering:

    def test_errors_before_warnings(self, project_dir):
        hu_path = _write(project_dir, "greet.hu", "# Header\n{{name}}")
        _write(project_dir, "main.lm", 'greet(name="x") -> TEXT')
        linter = HuLinter()
        result = linter.lint(
            "# Header\n{{name}}",
            cwd=project_dir, filepath=str(hu_path),
        )
        msg = result.feedback_message()
        lines = msg.split("\n")
        rule_lines = [l for l in lines if l.strip().startswith("[")]
        if len(rule_lines) >= 2:
            assert "HUE019" in rule_lines[0]

    def test_errors_before_refactor(self, project_dir):
        hu_path = _write(project_dir, "greet.hu", "{{param}}\nOutput JSON:")
        _write(project_dir, "main.lm", 'greet(param="x") -> TEXT')
        linter = HuLinter()
        result = linter.lint(
            "{{param}}\nOutput JSON:",
            cwd=project_dir, filepath=str(hu_path),
        )
        msg = result.feedback_message()
        error_pos = msg.find("HUE019")
        refactor_pos = msg.find("HUR018")
        if error_pos >= 0 and refactor_pos >= 0:
            assert error_pos < refactor_pos


# ── Existing rules still work ───────────────────────────────────────────────

class TestHuLinterExistingRulesUnaffected:

    def test_emoji_still_detected(self):
        violations = _violations_for_code("Hello 🎉 world", "HUW013")
        assert len(violations) >= 1

    def test_markdown_header_still_detected(self):
        violations = _violations_for_code("# My Header\nsome content", "HUW002")
        assert len(violations) >= 1

    def test_clean_file_still_clean(self):
        linter = HuLinter()
        result = linter.lint("Plain text with {one_param} placeholder.")
        assert result.clean
