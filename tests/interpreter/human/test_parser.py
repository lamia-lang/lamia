"""Tests for the .hu file parser."""

import os
import tempfile

import pytest

from lamia.interpreter.human.parser import HuFunction, parse_hu_file


class TestParseHuFile:

    def test_basic_template(self, tmp_path):
        hu = tmp_path / "greet.hu"
        hu.write_text("Hello, {name}!")
        fn = parse_hu_file(str(hu))

        assert fn.name == "greet"
        assert fn.template == "Hello, {name}!"
        assert fn.params == frozenset({"name"})
        assert fn.file_contexts == frozenset()

    def test_multiple_params(self, tmp_path):
        hu = tmp_path / "email.hu"
        hu.write_text("Write a {tone} email to {recipient} about {topic}.")
        fn = parse_hu_file(str(hu))

        assert fn.params == frozenset({"tone", "recipient", "topic"})

    def test_file_context_extraction(self, tmp_path):
        hu = tmp_path / "review.hu"
        hu.write_text("Review {@main.py} and compare with {@utils.py}.")
        fn = parse_hu_file(str(hu))

        assert fn.params == frozenset()
        assert fn.file_contexts == frozenset({"main.py", "utils.py"})

    def test_mixed_params_and_file_contexts(self, tmp_path):
        hu = tmp_path / "summarize.hu"
        hu.write_text("Summarize {@article.txt} focusing on {aspect}.")
        fn = parse_hu_file(str(hu))

        assert fn.params == frozenset({"aspect"})
        assert fn.file_contexts == frozenset({"article.txt"})

    def test_no_placeholders(self, tmp_path):
        hu = tmp_path / "hello.hu"
        hu.write_text("Just say hello to the world.")
        fn = parse_hu_file(str(hu))

        assert fn.params == frozenset()
        assert fn.file_contexts == frozenset()

    def test_empty_file(self, tmp_path):
        hu = tmp_path / "empty.hu"
        hu.write_text("")
        fn = parse_hu_file(str(hu))

        assert fn.name == "empty"
        assert fn.template == ""
        assert fn.params == frozenset()

    def test_multiline_template(self, tmp_path):
        hu = tmp_path / "report.hu"
        content = "Generate a report about {topic}.\n\nInclude data from {@data.csv}.\nKeep it under {max_words} words."
        hu.write_text(content)
        fn = parse_hu_file(str(hu))

        assert fn.template == content
        assert fn.params == frozenset({"topic", "max_words"})
        assert fn.file_contexts == frozenset({"data.csv"})

    def test_duplicate_param_deduplicated(self, tmp_path):
        hu = tmp_path / "repeat.hu"
        hu.write_text("{name} said hello to {name}.")
        fn = parse_hu_file(str(hu))

        assert fn.params == frozenset({"name"})

    def test_source_path_is_absolute(self, tmp_path):
        hu = tmp_path / "abs.hu"
        hu.write_text("test")
        fn = parse_hu_file(str(hu))

        assert os.path.isabs(fn.source_path)

    def test_hu_function_is_frozen(self, tmp_path):
        hu = tmp_path / "frozen.hu"
        hu.write_text("test {a}")
        fn = parse_hu_file(str(hu))

        with pytest.raises(AttributeError):
            fn.name = "other"


class TestParseHuFileOptionalParams:

    def test_optional_param_none_default(self, tmp_path):
        hu = tmp_path / "task.hu"
        hu.write_text("Task: {raw_tasks}\nPRD: {prd_content:None}")
        fn = parse_hu_file(str(hu))

        assert fn.params == frozenset({"raw_tasks", "prd_content"})
        assert fn.defaults == {"prd_content": ""}

    def test_optional_param_text_default(self, tmp_path):
        hu = tmp_path / "greet.hu"
        hu.write_text("Hello {name}, role: {role:engineer}")
        fn = parse_hu_file(str(hu))

        assert fn.params == frozenset({"name", "role"})
        assert fn.defaults == {"role": "engineer"}

    def test_optional_param_multiword_default(self, tmp_path):
        hu = tmp_path / "report.hu"
        hu.write_text("Write a report in {style:plain text} format.")
        fn = parse_hu_file(str(hu))

        assert fn.defaults == {"style": "plain text"}

    def test_required_param_not_in_defaults(self, tmp_path):
        hu = tmp_path / "req.hu"
        hu.write_text("{required_param} and {optional_param:default}")
        fn = parse_hu_file(str(hu))

        assert "required_param" not in fn.defaults
        assert "optional_param" in fn.defaults

    def test_all_required_params_no_defaults(self, tmp_path):
        hu = tmp_path / "all_req.hu"
        hu.write_text("{a} {b} {c}")
        fn = parse_hu_file(str(hu))

        assert fn.defaults == {}

    def test_all_optional_params(self, tmp_path):
        hu = tmp_path / "all_opt.hu"
        hu.write_text("{x:1} {y:2} {z:3}")
        fn = parse_hu_file(str(hu))

        assert fn.defaults == {"x": "1", "y": "2", "z": "3"}

    def test_duplicate_param_with_default_deduplicated(self, tmp_path):
        """First occurrence with :default wins; second occurrence is ignored."""
        hu = tmp_path / "dup.hu"
        hu.write_text("{param:first} then {param:second}")
        fn = parse_hu_file(str(hu))

        assert fn.params == frozenset({"param"})
        assert fn.defaults == {"param": "first"}

    def test_empty_string_default(self, tmp_path):
        """Empty string after : is a valid default (different from :None)."""
        hu = tmp_path / "empty_default.hu"
        hu.write_text("{suffix:}")
        fn = parse_hu_file(str(hu))

        assert fn.defaults == {"suffix": ""}

    def test_none_string_maps_to_empty_string(self, tmp_path):
        """:None is sugar for empty string default."""
        hu = tmp_path / "none_default.hu"
        hu.write_text("{optional:None}")
        fn = parse_hu_file(str(hu))

        assert fn.defaults["optional"] == ""

    def test_mixed_required_and_optional_with_file_context(self, tmp_path):
        hu = tmp_path / "mixed.hu"
        hu.write_text("Analyze {@data.csv} with focus={focus} and tone={tone:neutral}")
        fn = parse_hu_file(str(hu))

        assert fn.params == frozenset({"focus", "tone"})
        assert fn.defaults == {"tone": "neutral"}
        assert fn.file_contexts == frozenset({"data.csv"})


class TestParseHuFileVariableFileRefs:
    """Tests for {@variable} syntax where variable is an identifier."""

    def test_identifier_file_ref_becomes_required_param(self, tmp_path):
        hu = tmp_path / "review.hu"
        hu.write_text("Review this: {@code_file}")
        fn = parse_hu_file(str(hu))

        assert "code_file" in fn.params
        assert "code_file" in fn.file_contexts
        assert "code_file" not in fn.defaults

    def test_literal_path_not_param(self, tmp_path):
        hu = tmp_path / "review.hu"
        hu.write_text("Review: {@src/main.py}")
        fn = parse_hu_file(str(hu))

        assert fn.params == frozenset()
        assert "src/main.py" in fn.file_contexts

    def test_mixed_variable_and_literal_refs(self, tmp_path):
        hu = tmp_path / "review.hu"
        hu.write_text("Compare {@code_file} with {@../reference.py}")
        fn = parse_hu_file(str(hu))

        assert fn.params == frozenset({"code_file"})
        assert fn.file_contexts == frozenset({"code_file", "../reference.py"})

    def test_variable_ref_with_text_param(self, tmp_path):
        hu = tmp_path / "review.hu"
        hu.write_text("Review {@code_file} for {aspect}")
        fn = parse_hu_file(str(hu))

        assert fn.params == frozenset({"code_file", "aspect"})

    def test_same_name_as_text_param_and_file_ref(self, tmp_path):
        """When {code_file} (text) and {@code_file} (file) coexist,
        the text param is already in params so the file ref doesn't
        add a default — the param stays required."""
        hu = tmp_path / "review.hu"
        hu.write_text("File {code_file}: {@code_file}")
        fn = parse_hu_file(str(hu))

        assert fn.params == frozenset({"code_file"})
        assert "code_file" in fn.file_contexts
        assert "code_file" not in fn.defaults

    def test_dotted_filename_not_identifier(self, tmp_path):
        hu = tmp_path / "review.hu"
        hu.write_text("{@config.yaml}")
        fn = parse_hu_file(str(hu))

        assert fn.params == frozenset()
        assert fn.file_contexts == frozenset({"config.yaml"})