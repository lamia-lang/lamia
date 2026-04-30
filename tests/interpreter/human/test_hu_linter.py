"""Tests for HuLinter, including the HUW017 too-many-params rule."""

import pytest

from lamia.lint.hu_linter import HuLinter, TOO_MANY_PARAMS, _TOO_MANY_PARAMS_THRESHOLD


def _violations_for_code(content: str, code: str) -> list:
    linter = HuLinter()
    result = linter.lint(content)
    return [v for v in result.violations if v.rule.code == code]


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
        # 5 unique params, each repeated 3 times — should NOT trigger
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
