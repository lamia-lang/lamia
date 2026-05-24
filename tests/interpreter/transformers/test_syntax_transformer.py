"""Tests for syntax transformer module."""

import pytest
import ast
from lamia.interpreter.transformers.syntax_transformer import HybridSyntaxTransformer
from lamia.internal_types import WEB_METHOD_TO_ACTION, BrowserActionType


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
def search(query):
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

    @staticmethod
    def _run_call_line(result: str) -> str:
        """Return the lamia.run(...) line from transformed code."""
        for line in result.splitlines():
            if "lamia.run(" in line:
                return line
        return ""

    def test_function_with_models_parameter(self):
        """Test function with models parameter uses variable reference, not constant."""
        source = """
def process(models: list = ['gpt-4']):
    "Process data"
"""
        result = self.transformer.transform_code(source)
        run_line = self._run_call_line(result)

        assert "lamia.run" in result
        assert "models=models" in run_line
        assert "models='gpt-4'" not in run_line
        assert 'models="gpt-4"' not in run_line

    def test_function_with_models_string_uses_variable_ref(self):
        """models='openai:gpt-4' should generate models=models in lamia.run(), not the constant."""
        source = """
def summarize(models="openai:gpt-4"):
    "Summarize the document"
"""
        result = self.transformer.transform_code(source)
        run_line = self._run_call_line(result)

        assert "lamia.run" in result
        assert "models=models" in run_line
        assert "models='openai:gpt-4'" not in run_line

    def test_function_with_models_list_uses_variable_ref(self):
        """models=['a', 'b'] should generate models=models in lamia.run()."""
        source = """
def compare(models=["openai:gpt-4", "anthropic:claude-3"]):
    "Compare documents"
"""
        result = self.transformer.transform_code(source)
        run_line = self._run_call_line(result)

        assert "models=models" in run_line
        assert "models=['openai:gpt-4'" not in run_line

    def test_function_with_models_none_default_uses_variable_ref(self):
        """models=None should still generate models=models in lamia.run()."""
        source = """
def run(models=None):
    "Run the task"
"""
        result = self.transformer.transform_code(source)
        run_line = self._run_call_line(result)

        assert "models=models" in run_line

    def test_function_without_models_param_no_models_keyword(self):
        """Function without models param should not inject models= into lamia.run()."""
        source = """
def extract(name):
    "Extract {name}"
"""
        result = self.transformer.transform_code(source)
        run_line = self._run_call_line(result)

        assert "lamia.run" in result
        assert "models=" not in run_line

    def test_typed_placeholder_params_raise_clear_error(self):
        """Typed params in inline templates should fail with clear guidance."""
        source = """
def generate_report(data: dict, style: str):
    "Create a {style} report based on: {data}"
"""
        with pytest.raises(
            ValueError,
            match=(
                r"generate_report\(\) uses typed parameters: data, style\. "
                r"Lamia inline functions currently require untyped params\."
            ),
        ):
            self.transformer.transform_code(source)

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

    def test_function_param_plus_file_ref_escapes_file_ref(self):
        """Function with {param} and {@file} in docstring: {@file} must be double-brace-escaped."""
        source = """
def answer_question(question="What are my main skills?"):
    \"\"\"
    Answer: {question}

    Use information from {@resume.pdf} and {@cover_letter.txt}
    \"\"\"
"""
        result = self.transformer.transform_code(source)

        assert ".format" in result
        assert "question" in result
        # {@...} refs must be escaped so str.format() doesn't raise KeyError
        assert "{{@resume.pdf}}" in result
        assert "{{@cover_letter.txt}}" in result

    def test_function_param_plus_file_ref_runtime_format_does_not_raise(self):
        """At runtime .format() must preserve {@...} refs after double-brace escaping."""
        escaped = "\n    Answer: {question}\n\n    Use information from {{@resume.pdf}} and {{@cover_letter.txt}}\n    "
        result = escaped.format(question="Python, Go")
        assert "{@resume.pdf}" in result
        assert "{@cover_letter.txt}" in result
        assert "Python, Go" in result


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
        # Typed: _full_result=True so lamia.run returns LamiaResult
        assert "_full_result=True" in result
        # File content comes from .result_text (raw content, not model repr)
        assert "__lamia_file_result__.result_text" in result
        assert "str(__lamia_file_result__)" not in result
        # Return value is the typed_result, not the LamiaResult wrapper
        assert "__lamia_file_result__.typed_result" in result

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
        assert "_full_result=True" in result
        assert "__lamia_file_result__.result_text" in result

    def test_web_expression_untyped_file_write(self):
        """__LAMIA_WEB_RT__(File('path'), web.call()) generates write without validation."""
        source = '''
__LAMIA_WEB_RT__(File("raw.txt"), web.get_text(".content"))
'''
        result = self.transformer.transform_code(source)

        assert "FileCommand" in result
        assert "raw.txt" in result
        # Untyped file writes still use result_text for raw content
        assert "__lamia_file_result__.result_text" in result

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
        assert "_full_result=True" in result
        assert "__lamia_file_result__.result_text" in result

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
        assert "_full_result=True" in result
        assert "__lamia_file_result__.result_text" in result
        assert "__lamia_file_result__.typed_result" in result


class TestInlineVariableSubstitution:
    """Test {variable} substitution in inline arrow expressions."""

    def setup_method(self):
        self.transformer = HybridSyntaxTransformer()

    def test_inline_arrow_with_variable_produces_format_call(self):
        """'prompt {var}' -> Type produces .format(var=str(var))."""
        source = '__LAMIA_TYPED_EXPR__(HTML, "Write about {topic}")'
        result = self.transformer.transform_code(source)

        assert "lamia.run" in result
        assert ".format" in result
        assert "topic" in result

    def test_inline_arrow_without_placeholders_no_format(self):
        """'prompt' -> Type with no {var} does not produce .format()."""
        source = '__LAMIA_TYPED_EXPR__(HTML, "Write about cats")'
        result = self.transformer.transform_code(source)

        assert "lamia.run" in result
        assert ".format" not in result

    def test_inline_arrow_skips_file_context_placeholder(self):
        """{@filename} is left for runtime file-context injection, not .format()."""
        source = '__LAMIA_TYPED_EXPR__(HTML, "Summarize {@resume.pdf}")'
        result = self.transformer.transform_code(source)

        assert "lamia.run" in result
        assert ".format" not in result

    def test_inline_arrow_mixed_variable_and_file_context(self):
        """{var} is substituted, {@file} is left alone."""
        source = '__LAMIA_TYPED_EXPR__(HTML, "About {topic} using {@resume.pdf}")'
        result = self.transformer.transform_code(source)

        assert ".format" in result
        assert "topic" in result
        assert "resume" not in result.split(".format")[1] or "@resume" not in result.split(".format")[1]

    def test_inline_arrow_file_ref_escaped_so_format_does_not_raise(self):
        """{@file} must be double-brace-escaped in the format string so str.format() ignores it."""
        source = '__LAMIA_TYPED_EXPR__(HTML, "About {topic} using {@resume.pdf}")'
        result = self.transformer.transform_code(source)

        # The generated string literal must contain {{@resume.pdf}} so that
        # .format(topic=...) at runtime doesn't raise KeyError('@resume').
        assert "{{@resume.pdf}}" in result

    def test_inline_arrow_file_ref_runtime_format_does_not_raise(self):
        """At runtime .format() must not choke on {@resume.pdf} after escaping."""
        # Simulate what the generated code would do at runtime:
        # escaped_str.format(topic=str(topic)) must NOT raise KeyError
        escaped = "About {topic} using {{@resume.pdf}}"
        result = escaped.format(topic="Python")
        assert result == "About Python using {@resume.pdf}"

    def test_inline_arrow_multiple_file_refs_all_escaped(self):
        """Multiple {@...} refs in the same string are all escaped."""
        source = '__LAMIA_TYPED_EXPR__(HTML, "From {@resume.pdf} and {@cover_letter.txt} about {topic}")'
        result = self.transformer.transform_code(source)

        assert "{{@resume.pdf}}" in result
        assert "{{@cover_letter.txt}}" in result
        # The param placeholder is a regular kwarg, not escaped
        assert "topic=str(topic)" in result

    def test_inline_arrow_multiple_variables(self):
        source = '__LAMIA_TYPED_EXPR__(HTML, "Compare {stock_a} vs {stock_b}")'
        result = self.transformer.transform_code(source)

        assert ".format" in result
        assert "stock_a" in result
        assert "stock_b" in result

    def test_inline_arrow_duplicate_variable_only_one_kwarg(self):
        source = '__LAMIA_TYPED_EXPR__(HTML, "{x} and {x} again")'
        result = self.transformer.transform_code(source)

        assert ".format" in result
        format_part = result[result.index(".format"):]
        assert format_part.count("x=str(x)") == 1

    def test_file_write_expression_with_variable_produces_format_call(self):
        """__LAMIA_FILE_WRITE__("prompt {var}", File(...)) produces .format()."""
        source = '__LAMIA_FILE_WRITE__("Write about {topic}", File(HTML, "out.html"))'
        result = self.transformer.transform_code(source)

        assert "lamia.run" in result
        assert ".format" in result
        assert "topic" in result

    def test_file_write_expression_without_variable_no_format(self):
        source = '__LAMIA_FILE_WRITE__("Write about cats", File(HTML, "out.html"))'
        result = self.transformer.transform_code(source)

        assert "lamia.run" in result
        assert ".format" not in result


# =============================================================================
# WEB METHOD MAPPING COMPLETENESS AND TRANSFORMATION TESTS
# =============================================================================

# Each entry: (method_name, source_expression, expected_action, expected_keywords)
# expected_keywords is a dict of keyword arg names to expected string values in the output
WEB_METHOD_TRANSFORM_CASES = [
    ("navigate", 'web.navigate("https://example.com")', "NAVIGATE", {"url": "https://example.com"}),
    ("click", 'web.click("#btn")', "CLICK", {"selector": "#btn"}),
    ("type_text", 'web.type_text("#input", "hello")', "TYPE", {"selector": "#input", "value": "hello"}),
    ("wait_for", 'web.wait_for("#el")', "WAIT", {"selector": "#el"}),
    ("get_text", 'web.get_text("#el")', "GET_TEXT", {"selector": "#el"}),
    ("get_page_source", 'web.get_page_source()', "GET_PAGE_SOURCE", {}),
    ("get_elements", 'web.get_elements(".items")', "GET_ELEMENTS", {"selector": ".items"}),
    ("get_input_type", 'web.get_input_type("#field")', "GET_INPUT_TYPE", {"selector": "#field"}),
    ("get_options", 'web.get_options("#select")', "GET_OPTIONS", {"selector": "#select"}),
    ("get_attribute", 'web.get_attribute("#link", "href")', "GET_ATTRIBUTE", {"selector": "#link", "value": "href"}),
    ("is_checked", 'web.is_checked("#cb")', "IS_CHECKED", {"selector": "#cb"}),
    ("hover", 'web.hover("#menu")', "HOVER", {"selector": "#menu"}),
    ("scroll_to", 'web.scroll_to("#section")', "SCROLL", {"selector": "#section"}),
    ("select_option", 'web.select_option("#dd", "opt1")', "SELECT", {"selector": "#dd", "value": "opt1"}),
    ("submit_form", 'web.submit_form("#form")', "SUBMIT", {"selector": "#form"}),
    ("screenshot", 'web.screenshot()', "SCREENSHOT", {}),
    ("is_visible", 'web.is_visible("#el")', "IS_VISIBLE", {"selector": "#el"}),
    ("is_enabled", 'web.is_enabled("#el")', "IS_ENABLED", {"selector": "#el"}),
    ("upload_file", 'web.upload_file("#file", "/path/to/file.txt")', "UPLOAD_FILE", {"selector": "#file", "value": "/path/to/file.txt"}),
]


class TestWebMethodMappingCompleteness:
    """Ensure every BrowserActionType has a corresponding WEB_METHOD_TO_ACTION entry."""

    def test_all_browser_action_types_have_mapping(self):
        """Every BrowserActionType must be reachable via WEB_METHOD_TO_ACTION."""
        mapped_actions = set(WEB_METHOD_TO_ACTION.values())
        unmapped = [
            action.name for action in BrowserActionType
            if action not in mapped_actions
        ]
        assert unmapped == [], (
            f"BrowserActionType values missing from WEB_METHOD_TO_ACTION: {unmapped}. "
            "Add the corresponding web.method_name → BrowserActionType mapping."
        )

    def test_all_mapped_methods_have_transform_test_case(self):
        """Every method in WEB_METHOD_TO_ACTION has a transform test case above."""
        tested_methods = {case[0] for case in WEB_METHOD_TRANSFORM_CASES}
        untested = [
            method for method in WEB_METHOD_TO_ACTION
            if method not in tested_methods
        ]
        assert untested == [], (
            f"WEB_METHOD_TO_ACTION methods missing from WEB_METHOD_TRANSFORM_CASES: {untested}. "
            "Add a test case for each new method."
        )


class TestWebMethodTransformation:
    """Verify each web.method() call transforms to the correct WebCommand."""

    def setup_method(self):
        self.transformer = HybridSyntaxTransformer()

    @pytest.mark.parametrize(
        "method_name, source_expr, expected_action, expected_kw",
        WEB_METHOD_TRANSFORM_CASES,
        ids=[case[0] for case in WEB_METHOD_TRANSFORM_CASES],
    )
    def test_web_method_transforms_to_web_command(self, method_name, source_expr, expected_action, expected_kw):
        """web.method() must produce lamia.run(WebCommand(action=WebActionType.ACTION, ...))."""
        result = self.transformer.transform_code(source_expr)

        assert "lamia.run" in result, f"web.{method_name}() was not wrapped in lamia.run()"
        assert "WebCommand" in result, f"web.{method_name}() was not converted to WebCommand"
        assert f"WebActionType.{expected_action}" in result, (
            f"web.{method_name}() should produce WebActionType.{expected_action}, got: {result}"
        )
        for kw_name, kw_value in expected_kw.items():
            assert f"{kw_name}=" in result, (
                f"web.{method_name}() missing keyword '{kw_name}' in output: {result}"
            )
            assert kw_value in result, (
                f"web.{method_name}() missing value '{kw_value}' for keyword '{kw_name}' in output: {result}"
            )


class TestFileNamespaceTransformer:
    """Test file.method() and http.method() namespace transformation."""

    def setup_method(self):
        self.transformer = HybridSyntaxTransformer()

    def test_file_read_wrapped_in_lamia_run(self):
        result = self.transformer.transform_code('file.read("data.csv")')
        assert "lamia.run(file.read(" in result

    def test_file_read_with_encoding(self):
        result = self.transformer.transform_code('file.read("data.csv", encoding="latin-1")')
        assert "lamia.run(file.read(" in result
        assert "encoding=" in result

    def test_file_write_wrapped_in_lamia_run(self):
        result = self.transformer.transform_code('file.write("out.txt", "hello")')
        assert "lamia.run(file.write(" in result

    def test_file_append_wrapped_in_lamia_run(self):
        result = self.transformer.transform_code('file.append("log.txt", "entry")')
        assert "lamia.run(file.append(" in result

    def test_file_read_in_assignment(self):
        result = self.transformer.transform_code('content = file.read("/path/to/file.txt")')
        assert "content = lamia.run(file.read(" in result

    def test_file_read_in_print(self):
        result = self.transformer.transform_code('print(file.read("data.csv"))')
        assert "lamia.run(file.read(" in result

    def test_http_get_wrapped_in_lamia_run(self):
        result = self.transformer.transform_code('http.get("https://api.example.com")')
        assert "lamia.run(http.get(" in result

    def test_http_post_wrapped_in_lamia_run(self):
        result = self.transformer.transform_code('http.post("https://api.example.com", data={"k": "v"})')
        assert "lamia.run(http.post(" in result

    def test_web_not_affected_by_runnable_namespace(self):
        """web.method() should still use WebCommand, not generic wrapping."""
        result = self.transformer.transform_code('web.click("#btn")')
        assert "WebCommand" in result
