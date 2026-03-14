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