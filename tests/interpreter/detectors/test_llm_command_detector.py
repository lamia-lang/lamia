"""Tests for LLM command detector module."""

import pytest
import ast
from lamia.interpreter.detectors.llm_command_detector import (
    LLMCommandDetector,
    LLMFunctionInfo,
    FunctionParameter,
    SimpleReturnType,
    ParametricReturnType,
    FileWriteReturnType,
)


class TestLLMCommandDetector:
    """Test LLMCommandDetector AST visitor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.detector = LLMCommandDetector()

    def test_simple_function_with_single_string_body(self):
        """Test simple function with single string body detected as LLM command."""
        source = """
def get_page():
    "Click the login button"
"""
        result = self.detector.detect_commands(source)

        assert 'get_page' in result
        info = result['get_page']
        assert isinstance(info, LLMFunctionInfo)
        assert info.command == "Click the login button"
        assert info.is_async is False

    def test_function_with_docstring_and_string(self):
        """Test function with docstring + string: second string is the command."""
        source = """
def scrape_data():
    "This is a docstring"
    "Extract all product names from the page"
"""
        result = self.detector.detect_commands(source)

        assert 'scrape_data' in result
        info = result['scrape_data']
        assert isinstance(info, LLMFunctionInfo)
        assert info.command == "Extract all product names from the page"

    def test_function_with_actual_code_not_detected(self):
        """Test function with actual code (not just string) is NOT detected."""
        source = """
def process_data():
    x = 5
    return x
"""
        result = self.detector.detect_commands(source)

        assert len(result) == 0

    def test_return_type_extraction_simple_types(self):
        """Test return type extraction for simple types."""
        source = """
def get_content() -> HTML:
    "Get the page content"
"""
        result = self.detector.detect_commands(source)

        assert 'get_content' in result
        return_type = result['get_content'].return_type
        assert isinstance(return_type, SimpleReturnType)
        assert return_type.base_type == 'HTML'
        assert return_type.full_type == 'HTML'

    def test_return_type_extraction_parametric_types(self):
        """Test return type extraction for parametric types like HTML[Model]."""
        source = """
def get_user_page() -> HTML[UserModel]:
    "Get user profile page"
"""
        result = self.detector.detect_commands(source)

        assert 'get_user_page' in result
        return_type = result['get_user_page'].return_type
        assert isinstance(return_type, ParametricReturnType)
        assert return_type.base_type == 'HTML'
        assert return_type.inner_type == 'UserModel'
        assert return_type.full_type == 'HTML[UserModel]'

    def test_parameter_extraction_with_types_and_defaults(self):
        """Test parameter extraction with types and defaults."""
        source = """
def search(query: str, limit: int = 10, models: list = None):
    "Search for items"
"""
        result = self.detector.detect_commands(source)

        assert 'search' in result
        parameters = result['search'].parameters
        assert len(parameters) == 3

        assert isinstance(parameters[0], FunctionParameter)
        assert parameters[0].name == 'query'
        assert parameters[0].type_annotation == 'str'
        assert parameters[0].default is None

        assert parameters[1].name == 'limit'
        assert parameters[1].type_annotation == 'int'
        assert parameters[1].default == 10

        assert parameters[2].name == 'models'
        assert parameters[2].type_annotation == 'list'
        assert parameters[2].default is None

    def test_async_functions_detected_correctly(self):
        """Test async functions detected correctly."""
        source = """
async def fetch_data():
    "Fetch data asynchronously"
"""
        result = self.detector.detect_commands(source)

        assert 'fetch_data' in result
        assert result['fetch_data'].is_async is True
        assert result['fetch_data'].command == "Fetch data asynchronously"

    def test_empty_function_body_not_detected(self):
        """Test empty function body not detected."""
        source = """
def empty_func():
    pass
"""
        result = self.detector.detect_commands(source)

        assert len(result) == 0

    def test_multiple_functions_in_same_source(self):
        """Test multiple functions in same source."""
        source = """
def func1():
    "First command"

def func2():
    "Second command"

def func3():
    x = 5
    return x
"""
        result = self.detector.detect_commands(source)

        assert len(result) == 2
        assert 'func1' in result
        assert 'func2' in result
        assert 'func3' not in result
        assert result['func1'].command == "First command"
        assert result['func2'].command == "Second command"

    def test_function_with_no_return_type(self):
        """Test function with no return type annotation."""
        source = """
def simple_command():
    "Just a command"
"""
        result = self.detector.detect_commands(source)

        assert 'simple_command' in result
        assert result['simple_command'].return_type is None

    def test_function_with_complex_return_type(self):
        """Test function with complex return type like JSON[Schema]."""
        source = """
def get_json() -> JSON[DataSchema]:
    "Get JSON data"
"""
        result = self.detector.detect_commands(source)

        assert 'get_json' in result
        return_type = result['get_json'].return_type
        assert isinstance(return_type, ParametricReturnType)
        assert return_type.base_type == 'JSON'
        assert return_type.inner_type == 'DataSchema'

    def test_parameter_with_list_default(self):
        """Test parameter with list default value."""
        source = """
def process(models: list = ['gpt-4', 'claude']):
    "Process with models"
"""
        result = self.detector.detect_commands(source)

        assert 'process' in result
        parameters = result['process'].parameters
        assert parameters[0].name == 'models'
        assert parameters[0].default == ['gpt-4', 'claude']

class TestLLMCommandDetectorFileWrite:
    """Test File(...) return type detection in LLM command detector."""

    def setup_method(self):
        self.detector = LLMCommandDetector()

    def test_file_write_untyped(self):
        """File('path') return type detected as file_write without inner type."""
        source = '''
def generate_text() -> File("output.txt"):
    "Generate some text"
'''
        result = self.detector.detect_commands(source)

        assert 'generate_text' in result
        rt = result['generate_text'].return_type
        assert isinstance(rt, FileWriteReturnType)
        assert rt.inner_return_type is None
        assert rt.path == 'output.txt'
        assert rt.append is False
        assert rt.encoding == 'utf-8'

    def test_file_write_typed_simple(self):
        """File(HTML, 'path') return type detected with simple inner type."""
        source = '''
def generate_page() -> File(HTML, "output.html"):
    "Generate an HTML page about cats"
'''
        result = self.detector.detect_commands(source)

        assert 'generate_page' in result
        rt = result['generate_page'].return_type
        assert isinstance(rt, FileWriteReturnType)
        assert isinstance(rt.inner_return_type, SimpleReturnType)
        assert rt.inner_return_type.base_type == 'HTML'
        assert rt.path == 'output.html'

    def test_file_write_typed_parametric(self):
        """File(HTML[MyModel], 'path') detected with parametric inner type."""
        source = '''
def generate_page() -> File(HTML[MyModel], "output.html"):
    "Generate a typed page"
'''
        result = self.detector.detect_commands(source)

        rt = result['generate_page'].return_type
        assert isinstance(rt, FileWriteReturnType)
        assert isinstance(rt.inner_return_type, ParametricReturnType)
        assert rt.inner_return_type.base_type == 'HTML'
        assert rt.inner_return_type.inner_type == 'MyModel'

    def test_file_write_append_flag(self):
        """File(CSV, 'path', append=True) detected with append flag."""
        source = '''
def add_rows() -> File(CSV, "data.csv", append=True):
    "Generate CSV rows"
'''
        result = self.detector.detect_commands(source)

        rt = result['add_rows'].return_type
        assert isinstance(rt, FileWriteReturnType)
        assert rt.append is True
        assert rt.path == 'data.csv'

    def test_file_write_encoding_kwarg(self):
        """File('path', encoding='latin-1') detected with encoding flag."""
        source = '''
def generate() -> File("output.txt", encoding="latin-1"):
    "Generate text"
'''
        result = self.detector.detect_commands(source)

        rt = result['generate'].return_type
        assert isinstance(rt, FileWriteReturnType)
        assert rt.encoding == 'latin-1'

    def test_async_file_write(self):
        """Async function with File return type detected correctly."""
        source = '''
async def generate_async() -> File(HTML, "output.html"):
    "Generate async HTML"
'''
        result = self.detector.detect_commands(source)

        assert 'generate_async' in result
        assert result['generate_async'].is_async is True
        rt = result['generate_async'].return_type
        assert isinstance(rt, FileWriteReturnType)


class TestFStringLLMDetection:
    """Test bare f-string body detection in LLM mode."""

    def setup_method(self):
        self.detector = LLMCommandDetector()

    def test_fstring_body_detected(self):
        """Function with f-string body is detected."""
        source = '''
def log_result(job_id) -> CSV:
    f"{job_id},ok"
'''
        result = self.detector.detect_commands(source)
        assert 'log_result' in result
        info = result['log_result']
        assert info.command_node is not None
        assert info.command == ""

    def test_fstring_body_with_return_type(self):
        """f-string body preserves return type extraction."""
        source = '''
def render(name) -> HTML:
    f"<h1>Hello {name}</h1>"
'''
        result = self.detector.detect_commands(source)
        assert 'render' in result
        rt = result['render'].return_type
        assert isinstance(rt, SimpleReturnType)
        assert rt.base_type == 'HTML'

    def test_fstring_body_with_parametric_return_type(self):
        """f-string body with parametric return type like JSON[Model]."""
        source = '''
def build_json(data) -> JSON[MyModel]:
    f'{{"key": "{data}"}}'
'''
        result = self.detector.detect_commands(source)
        assert 'build_json' in result
        rt = result['build_json'].return_type
        assert isinstance(rt, ParametricReturnType)
        assert rt.base_type == 'JSON'
        assert rt.inner_type == 'MyModel'

    def test_fstring_body_with_file_write(self):
        """f-string body with File(..., append=True) return type."""
        source = '''
def log_run(ts, job_id) -> File(CSV, "log.csv", append=True):
    f"{ts},{job_id},ok"
'''
        result = self.detector.detect_commands(source)
        assert 'log_run' in result
        rt = result['log_run'].return_type
        assert isinstance(rt, FileWriteReturnType)
        assert rt.path == 'log.csv'
        assert rt.append is True

    def test_docstring_plus_fstring_body(self):
        """Function with docstring followed by f-string body."""
        source = '''
def greet(name) -> str:
    "Builds a greeting"
    f"Hello, {name}!"
'''
        result = self.detector.detect_commands(source)
        assert 'greet' in result
        assert result['greet'].command_node is not None

    def test_async_fstring_body(self):
        """Async function with f-string body."""
        source = '''
async def async_log(status) -> JSON:
    f'{{"status": "{status}"}}'
'''
        result = self.detector.detect_commands(source)
        assert 'async_log' in result
        assert result['async_log'].is_async is True
        assert result['async_log'].command_node is not None

    def test_fstring_parameters_extracted(self):
        """Parameters are extracted from f-string body functions."""
        source = '''
def build(name: str, count: int = 5) -> CSV:
    f"{name},{count}"
'''
        result = self.detector.detect_commands(source)
        assert 'build' in result
        params = result['build'].parameters
        assert len(params) == 2
        assert params[0].name == 'name'
        assert params[1].name == 'count'
        assert params[1].default == 5

    def test_regular_code_body_not_detected_as_fstring(self):
        """Code body with f-string in assignment is NOT detected."""
        source = '''
def compute(x):
    result = f"value: {x}"
    return result
'''
        result = self.detector.detect_commands(source)
        assert 'compute' not in result


class TestDeterministicReturnDetection:
    """Test return-based deterministic content detection."""

    def setup_method(self):
        self.detector = LLMCommandDetector()

    def test_return_fstring_detected_as_deterministic(self):
        """return f-string with return type is deterministic."""
        source = '''
def log(ts, job_id) -> CSV:
    return f"{ts},{job_id},ok"
'''
        result = self.detector.detect_commands(source)
        assert 'log' in result
        info = result['log']
        assert info.is_deterministic is True
        assert info.deterministic_node is not None

    def test_return_string_constant_detected(self):
        """return string constant with return type is deterministic."""
        source = '''
def header() -> CSV:
    return "name,status,timestamp"
'''
        result = self.detector.detect_commands(source)
        assert 'header' in result
        assert result['header'].is_deterministic is True

    def test_return_fstring_file_write(self):
        """return f-string with File() return type is deterministic."""
        source = '''
def log_run(ts) -> File(CSV, "log.csv", append=True):
    return f"{ts},ok"
'''
        result = self.detector.detect_commands(source)
        assert 'log_run' in result
        info = result['log_run']
        assert info.is_deterministic is True
        assert isinstance(info.return_type, FileWriteReturnType)
        assert info.return_type.append is True

    def test_return_call_not_deterministic(self):
        """return with a function call is NOT deterministic."""
        source = '''
def scrape() -> File(HTML, "out.html"):
    return web.get_text(".content")
'''
        result = self.detector.detect_commands(source)
        info = result.get('scrape')
        if info:
            assert info.is_deterministic is False

    def test_return_without_type_annotation_not_detected(self):
        """return f-string without -> Type is NOT detected."""
        source = '''
def plain(x):
    return f"hello {x}"
'''
        result = self.detector.detect_commands(source)
        assert 'plain' not in result

    def test_docstring_plus_return_fstring(self):
        """Docstring + return f-string is deterministic."""
        source = '''
def log(ts) -> YAML:
    "Logs a timestamp entry"
    return f"ts: {ts}"
'''
        result = self.detector.detect_commands(source)
        assert 'log' in result
        assert result['log'].is_deterministic is True

    def test_async_return_fstring(self):
        """Async function with return f-string is deterministic."""
        source = '''
async def log(ts) -> JSON:
    return f'{{"ts": "{ts}"}}'
'''
        result = self.detector.detect_commands(source)
        assert 'log' in result
        info = result['log']
        assert info.is_deterministic is True
        assert info.is_async is True

    def test_bare_fstring_not_deterministic(self):
        """Bare f-string (no return) is LLM, not deterministic."""
        source = '''
def ask(topic) -> str:
    f"Tell me about {topic}"
'''
        result = self.detector.detect_commands(source)
        assert 'ask' in result
        assert result['ask'].is_deterministic is False
        assert result['ask'].command_node is not None
