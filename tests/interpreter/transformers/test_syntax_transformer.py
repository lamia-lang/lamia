"""Tests for syntax transformer module."""

import pytest
import ast
from lamia.interpreter.transformers.syntax_transformer import HybridSyntaxTransformer


class TestHybridSyntaxTransformer:
    """Test HybridSyntaxTransformer AST transformer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.transformer = HybridSyntaxTransformer()

    def test_function_with_string_body_transformed_to_lamia_run(self):
        """Test function with string body transformed to lamia.run() call."""
        source = """
def get_page():
    "Click the login button"
"""
        result = self.transformer.transform_code(source)

        assert "lamia.run" in result
        assert "Click the login button" in result
        assert "def get_page" in result

    def test_web_click_transformed_to_webcommand_lamia_run(self):
        """Test web.click(\"selector\") transformed to WebCommand + lamia.run()."""
        source = """
def click_button():
    web.click("button")
"""
        result = self.transformer.transform_code(source)

        assert "lamia.run" in result
        assert "WebCommand" in result
        assert "WebActionType.CLICK" in result

    def test_async_function_transformation_uses_run_async(self):
        """Test async function transformation uses run_async."""
        source = """
async def fetch_data():
    "Get data asynchronously"
"""
        result = self.transformer.transform_code(source)

        assert "lamia.run_async" in result
        assert "async def fetch_data" in result
        assert "await" in result

    def test_parameter_substitution_with_param_in_command_string(self):
        """Test parameter substitution with {param} in command string."""
        source = """
def search(query: str):
    "Search for {query}"
"""
        result = self.transformer.transform_code(source)

        assert "lamia.run" in result
        assert ".format" in result or "{query}" in result
        assert "query" in result

    def test_return_type_annotation_passed_to_lamia_run(self):
        """Test return type annotation passed to lamia.run as return_type keyword."""
        source = """
def get_content() -> HTML:
    "Get page content"
"""
        result = self.transformer.transform_code(source)

        assert "lamia.run" in result
        assert "return_type" in result
        assert "HTML" in result

    def test_code_without_hybrid_syntax_passes_through(self):
        """Test code without hybrid syntax passes through."""
        source = """
def normal_function():
    x = 5
    return x + 1
"""
        result = self.transformer.transform_code(source)

        assert "def normal_function" in result
        assert "x = 5" in result
        assert "return x + 1" in result

    def test_multiple_web_method_calls_in_sequence(self):
        """Test multiple web method calls in sequence."""
        source = """
def navigate_and_click():
    web.navigate("https://example.com")
    web.click("button")
"""
        result = self.transformer.transform_code(source)

        assert result.count("lamia.run") == 2
        assert "WebActionType.NAVIGATE" in result
        assert "WebActionType.CLICK" in result

    def test_web_expression_with_return_type_preprocessed(self):
        """Test web expression with return type from preprocessing."""
        source = """
__LAMIA_WEB_RT__(HTML, web.click("button"))
"""
        result = self.transformer.transform_code(source)

        assert "lamia.run" in result
        assert "return_type" in result
        assert "HTML" in result
        assert "WebCommand" in result

    def test_function_with_parametric_return_type(self):
        """Test function with parametric return type."""
        source = """
def get_user_page() -> HTML[UserModel]:
    "Get user profile"
"""
        result = self.transformer.transform_code(source)

        assert "lamia.run" in result
        assert "return_type" in result
        assert "HTML" in result
        assert "UserModel" in result

    def test_web_method_with_multiple_arguments(self):
        """Test web method with multiple arguments."""
        source = """
def type_text():
    web.type_text("#input", "Hello World")
"""
        result = self.transformer.transform_code(source)

        assert "lamia.run" in result
        assert "WebCommand" in result
        assert "WebActionType.TYPE" in result
        assert "selector" in result
        assert "value" in result

    def test_function_returning_web_command(self):
        """Test function that returns web command."""
        source = """
def get_click_command():
    return web.click("button")
"""
        result = self.transformer.transform_code(source)

        assert "lamia.run" in result
        assert "WebCommand" in result
        assert "WebActionType.CLICK" in result

    def test_async_function_with_web_command(self):
        """Test async function with web command."""
        source = """
async def async_click():
    return web.click("button")
"""
        result = self.transformer.transform_code(source)

        assert "lamia.run_async" in result
        assert "await" in result
        assert "WebCommand" in result

    def test_web_expression_standalone(self):
        """Test standalone web expression statement."""
        source = """
web.click("button")
"""
        result = self.transformer.transform_code(source)

        assert "lamia.run" in result
        assert "WebCommand" in result

    def test_function_with_models_parameter(self):
        """Test function with models parameter."""
        source = """
def process(models: list = ['gpt-4']):
    "Process data"
"""
        result = self.transformer.transform_code(source)

        assert "lamia.run" in result
        assert "models" in result

    def test_web_method_with_fallback_selectors(self):
        """Test web method with fallback selectors."""
        source = """
def click_with_fallback():
    web.click("button", "backup-button", "another-button")
"""
        result = self.transformer.transform_code(source)

        assert "lamia.run" in result
        assert "fallback_selectors" in result
        assert "WebCommand" in result


class TestFileWriteSyntaxTransformer:
    """Test -> File(...) hybrid syntax transformation."""

    def setup_method(self):
        self.transformer = HybridSyntaxTransformer()

    def test_function_typed_file_write(self):
        """def func() -> File(HTML, 'path'): generates multi-step code."""
        source = '''
def generate_page() -> File(HTML, "output.html"):
    "Generate an HTML page about cats"
'''
        result = self.transformer.transform_code(source)

        assert "lamia.run" in result
        assert "FileCommand" in result
        assert "FileActionType.WRITE" in result
        assert "output.html" in result
        assert "return_type" in result
        assert "__lamia_file_result__" in result

    def test_function_untyped_file_write(self):
        """def func() -> File('path'): generates write without return_type."""
        source = '''
def generate_text() -> File("output.txt"):
    "Generate some text"
'''
        result = self.transformer.transform_code(source)

        assert "lamia.run" in result
        assert "FileCommand" in result
        assert "FileActionType.WRITE" in result
        assert "output.txt" in result
        # Untyped: no return_type keyword, content via str(...)
        assert "str(__lamia_file_result__)" in result

    def test_function_file_append(self):
        """def func() -> File(CSV, 'path', append=True): generates APPEND."""
        source = '''
def add_rows() -> File(CSV, "data.csv", append=True):
    "Generate CSV rows"
'''
        result = self.transformer.transform_code(source)

        assert "FileActionType.APPEND" in result
        assert "data.csv" in result

    def test_async_function_file_write(self):
        """Async function with File return type uses run_async + await."""
        source = '''
async def generate_async() -> File(HTML, "output.html"):
    "Generate HTML async"
'''
        result = self.transformer.transform_code(source)

        assert "await" in result
        assert "run_async" in result
        assert "FileCommand" in result
        assert "output.html" in result

    def test_web_expression_file_write(self):
        """__LAMIA_WEB_RT__(File(HTML, 'path'), web.call()) generates two-step code."""
        source = '''
__LAMIA_WEB_RT__(File(HTML, "page.html"), web.get_text(".content"))
'''
        result = self.transformer.transform_code(source)

        assert "FileCommand" in result
        assert "FileActionType.WRITE" in result
        assert "page.html" in result
        assert "return_type" in result
        assert "__lamia_file_result__" in result

    def test_web_expression_untyped_file_write(self):
        """__LAMIA_WEB_RT__(File('path'), web.call()) generates write without validation."""
        source = '''
__LAMIA_WEB_RT__(File("raw.txt"), web.get_text(".content"))
'''
        result = self.transformer.transform_code(source)

        assert "FileCommand" in result
        assert "raw.txt" in result
        # No return_type keyword for untyped file writes
        assert "str(__lamia_file_result__)" in result

    def test_file_write_expression(self):
        """__LAMIA_FILE_WRITE__('prompt', File(...)) generates file write code."""
        source = '''
__LAMIA_FILE_WRITE__("Generate HTML about cats", File(HTML, "output.html"))
'''
        result = self.transformer.transform_code(source)

        assert "FileCommand" in result
        assert "FileActionType.WRITE" in result
        assert "output.html" in result
        assert "__lamia_file_result__" in result

    def test_web_function_with_file_return_type(self):
        """def func() -> File(HTML, 'path'): return web.get_text(...) generates file write."""
        source = '''
def scrape_to_file() -> File(HTML, "scraped.html"):
    return web.get_text(".content")
'''
        result = self.transformer.transform_code(source)

        assert "FileCommand" in result
        assert "FileActionType.WRITE" in result
        assert "scraped.html" in result
        assert "WebCommand" in result
