"""Tests for return type preprocessor module."""

import pytest
from lamia.interpreter.preprocessors.return_type_preprocessor import WithReturnTypePreprocessor


class TestWithReturnTypePreprocessor:
    """Test WithReturnTypePreprocessor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.preprocessor = WithReturnTypePreprocessor()

    def test_session_statement_with_return_type_preprocessed(self):
        """Test session statement with return type is preprocessed correctly."""
        source = """
with session("test") -> HTML:
    pass
"""
        processed, return_types = self.preprocessor.preprocess(source)

        assert "with session(\"test\"):" in processed
        assert "# LAMIA_WITH_RETURN_TYPE_" in processed
        assert len(return_types) == 1
        assert list(return_types.values())[0] == "HTML"

    def test_web_expression_with_return_type_preprocessed(self):
        """Test web expression with return type is preprocessed correctly."""
        source = """
web.click("button") -> HTML
"""
        processed, return_types = self.preprocessor.preprocess(source)

        assert "__LAMIA_WEB_RT__" in processed
        assert "HTML" in processed
        assert "web.click" in processed

    def test_code_without_return_types_passes_through(self):
        """Test code without return types passes through unchanged."""
        source = """
def func():
    web.click("button")
    with session("test"):
        pass
"""
        processed, return_types = self.preprocessor.preprocess(source)

        assert processed == source
        assert len(return_types) == 0

    def test_multiple_session_statements(self):
        """Test multiple session statements."""
        source = """
with session("test1") -> HTML:
    pass

with session("test2") -> JSON:
    pass
"""
        processed, return_types = self.preprocessor.preprocess(source)

        assert "with session(\"test1\"):" in processed
        assert "with session(\"test2\"):" in processed
        assert "# LAMIA_WITH_RETURN_TYPE_" in processed
        assert len(return_types) == 2
        assert "HTML" in return_types.values()
        assert "JSON" in return_types.values()

    def test_return_types_dict_contains_correct_mappings(self):
        """Test return types dict contains correct mappings."""
        source = """
with session("test") -> HTML[UserModel]:
    pass
"""
        processed, return_types = self.preprocessor.preprocess(source)

        assert len(return_types) == 1
        return_type_value = list(return_types.values())[0]
        assert return_type_value == "HTML[UserModel]"

    def test_indentation_is_preserved(self):
        """Test indentation is preserved."""
        source = """
    with session("test") -> HTML:
        pass
"""
        processed, return_types = self.preprocessor.preprocess(source)

        assert processed.startswith("\n    ")
        assert "    with session(\"test\"):" in processed
        assert "        pass" in processed

    def test_web_expression_with_parametric_return_type(self):
        """Test web expression with parametric return type."""
        source = """
web.get_text(".content") -> HTML[PageModel]
"""
        processed, return_types = self.preprocessor.preprocess(source)

        assert "__LAMIA_WEB_RT__" in processed
        assert "HTML[PageModel]" in processed
        assert "web.get_text" in processed

    def test_session_with_complex_return_type(self):
        """Test session with complex return type."""
        source = """
with session("scraper") -> JSON[DataSchema]:
    pass
"""
        processed, return_types = self.preprocessor.preprocess(source)

        assert "with session(\"scraper\"):" in processed
        assert len(return_types) == 1
        assert list(return_types.values())[0] == "JSON[DataSchema]"

    def test_multiple_web_expressions(self):
        """Test multiple web expressions with return types."""
        source = """
web.click("button") -> HTML
web.type_text("#input", "text") -> None
"""
        processed, return_types = self.preprocessor.preprocess(source)

        assert "__LAMIA_WEB_RT__" in processed
        assert processed.count("__LAMIA_WEB_RT__") == 2
        assert "HTML" in processed
        assert "None" in processed

    def test_session_with_whitespace_in_return_type(self):
        """Test session with whitespace in return type is handled."""
        source = """
with session("test") ->  HTML  :
    pass
"""
        processed, return_types = self.preprocessor.preprocess(source)

        assert "with session(\"test\"):" in processed
        assert len(return_types) == 1
        return_type_value = list(return_types.values())[0]
        assert return_type_value == "HTML"


class TestFileWritePreprocessor:
    """Test preprocessing of 'prompt' -> File(...) expressions."""

    def setup_method(self):
        self.preprocessor = WithReturnTypePreprocessor()

    def test_string_to_typed_file_write(self):
        """'prompt' -> File(HTML, 'path') rewritten to __LAMIA_FILE_WRITE__."""
        source = '''
"Generate HTML about cats" -> File(HTML, "output.html")
'''
        processed, _ = self.preprocessor.preprocess(source)

        assert "__LAMIA_FILE_WRITE__" in processed
        assert '"Generate HTML about cats"' in processed
        assert 'File(HTML, "output.html")' in processed

    def test_string_to_untyped_file_write(self):
        """'prompt' -> File('path') rewritten to __LAMIA_FILE_WRITE__."""
        source = '''
"Generate text" -> File("output.txt")
'''
        processed, _ = self.preprocessor.preprocess(source)

        assert "__LAMIA_FILE_WRITE__" in processed
        assert '"Generate text"' in processed
        assert 'File("output.txt")' in processed

    def test_string_to_file_write_with_append(self):
        """'prompt' -> File(CSV, 'path', append=True) rewritten correctly."""
        source = '''
"Generate rows" -> File(CSV, "data.csv", append=True)
'''
        processed, _ = self.preprocessor.preprocess(source)

        assert "__LAMIA_FILE_WRITE__" in processed
        assert "append=True" in processed

    def test_single_quoted_string_prompt(self):
        """Single-quoted prompt string is supported."""
        source = """
'Generate text' -> File("out.txt")
"""
        processed, _ = self.preprocessor.preprocess(source)

        assert "__LAMIA_FILE_WRITE__" in processed
        assert "'Generate text'" in processed

    def test_web_expression_to_file_write(self):
        """web.method() -> File(...) uses __LAMIA_WEB_RT__ (existing path)."""
        source = '''
web.get_text(".content") -> File(HTML, "page.html")
'''
        processed, _ = self.preprocessor.preprocess(source)

        # Web expressions go through __LAMIA_WEB_RT__, not __LAMIA_FILE_WRITE__
        assert "__LAMIA_WEB_RT__" in processed
        assert 'File(HTML, "page.html")' in processed

    def test_indented_file_write_expression(self):
        """Indented prompt -> File(...) preserves indentation."""
        source = '''
    "Generate text" -> File("output.txt")
'''
        processed, _ = self.preprocessor.preprocess(source)

        assert "__LAMIA_FILE_WRITE__" in processed


class TestStandaloneTypedPromptPreprocessor:
    """Test preprocessing of 'prompt' -> Type shorthand expressions."""

    def setup_method(self):
        self.preprocessor = WithReturnTypePreprocessor()

    def test_single_quoted_prompt_with_type(self):
        """'prompt' -> HTML becomes a synthetic function def."""
        source = "'return html' -> HTML"
        processed, _ = self.preprocessor.preprocess(source)

        assert "def __LAMIA_TYPED_PROMPT_0() -> HTML:" in processed
        assert "'return html'" in processed

    def test_double_quoted_prompt_with_type(self):
        """\"prompt\" -> JSON becomes a synthetic function def."""
        source = '"extract data" -> JSON'
        processed, _ = self.preprocessor.preprocess(source)

        assert "def __LAMIA_TYPED_PROMPT_0() -> JSON:" in processed
        assert '"extract data"' in processed

    def test_parametric_type(self):
        """'prompt' -> HTML[Model] preserves parametric type."""
        source = "'get page' -> HTML[PageModel]"
        processed, _ = self.preprocessor.preprocess(source)

        assert "-> HTML[PageModel]:" in processed

    def test_does_not_consume_file_write(self):
        """'prompt' -> File(...) is handled by file write, not standalone."""
        source = '"Generate text" -> File("output.txt")'
        processed, _ = self.preprocessor.preprocess(source)

        assert "__LAMIA_FILE_WRITE__" in processed
        assert "__LAMIA_TYPED_PROMPT" not in processed

    def test_multiple_standalone_prompts(self):
        """Multiple standalone prompts get unique function names."""
        source = "'prompt one' -> HTML\n'prompt two' -> JSON"
        processed, _ = self.preprocessor.preprocess(source)

        assert "__LAMIA_TYPED_PROMPT_0" in processed
        assert "__LAMIA_TYPED_PROMPT_1" in processed
        assert "-> HTML:" in processed
        assert "-> JSON:" in processed

    def test_indentation_preserved(self):
        """Indented prompt preserves indentation in the generated function."""
        source = "    'indented prompt' -> HTML"
        processed, _ = self.preprocessor.preprocess(source)

        assert "    def __LAMIA_TYPED_PROMPT_0() -> HTML:" in processed
        assert "        'indented prompt'" in processed

    def test_plain_string_without_type_not_affected(self):
        """A standalone string without -> Type is left unchanged."""
        source = "'just a string'"
        processed, _ = self.preprocessor.preprocess(source)

        assert processed == source
        assert "__LAMIA_TYPED_PROMPT" not in processed
