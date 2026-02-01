"""Tests for python_runner module."""

import pytest
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import patch, Mock
from lamia.interpreter.python_runner import run_python_code, run_python_file


class TestRunPythonCode:
    """Test run_python_code function."""
    
    def test_simple_expression_evaluation(self):
        """Test evaluating simple expressions."""
        # Simple arithmetic
        result = run_python_code("2 + 3")
        assert result == 5
        
        # String operations
        result = run_python_code("'hello' + ' world'")
        assert result == "hello world"
        
        # Boolean operations
        result = run_python_code("True and False")
        assert result is False
    
    def test_variable_assignment_and_return(self):
        """Test variable assignment and implicit return."""
        # Variable assignment with expression at end
        code = """
x = 10
y = 20
x + y
"""
        result = run_python_code(code)
        assert result == 30
    
    def test_function_definition_and_call(self):
        """Test function definition and execution."""
        code = """
def add_numbers(a, b):
    return a + b

add_numbers(5, 7)
"""
        result = run_python_code(code)
        assert result == 12
    
    def test_complex_computation(self):
        """Test complex computations."""
        code = """
import math
x = 16
math.sqrt(x)
"""
        result = run_python_code(code)
        assert result == 4.0
    
    def test_list_comprehension(self):
        """Test list comprehension execution."""
        code = "[x*2 for x in range(5)]"
        result = run_python_code(code)
        assert result == [0, 2, 4, 6, 8]
    
    def test_print_statement_no_return(self):
        """Test that print statements don't get returned in interactive mode."""
        code = """
x = 5
print(x)
"""
        result = run_python_code(code)
        assert result is None
    
    def test_multiple_statements_last_expression_returned(self):
        """Test that last expression is returned in interactive mode."""
        code = """
a = 1
b = 2
c = 3
a + b + c
"""
        result = run_python_code(code)
        assert result == 6
    
    def test_statement_only_code(self):
        """Test code with only statements (no expression at end)."""
        code = """
x = 42
y = x * 2
"""
        result = run_python_code(code)
        assert result is None
    
    def test_class_definition_and_instantiation(self):
        """Test class definition and object creation."""
        code = """
class TestClass:
    def __init__(self, value):
        self.value = value
    
    def get_value(self):
        return self.value * 2

obj = TestClass(10)
obj.get_value()
"""
        result = run_python_code(code)
        assert result == 20
    
    def test_exception_in_expression_mode(self):
        """Test that exceptions in expression mode are handled."""
        # This will first try expression mode and fail, then try exec mode
        code = "x = 5"  # This is a statement, not an expression
        result = run_python_code(code)
        assert result is None
    
    def test_syntax_error_raises_exception(self):
        """Test that syntax errors are properly raised."""
        with pytest.raises(SyntaxError):
            run_python_code("def invalid syntax:")
    
    def test_runtime_error_raises_exception(self):
        """Test that runtime errors are properly raised."""
        with pytest.raises(NameError):
            run_python_code("undefined_variable")
    
    def test_division_by_zero_error(self):
        """Test that runtime errors like division by zero are raised."""
        with pytest.raises(ZeroDivisionError):
            run_python_code("10 / 0")


class TestRunPythonCodeModes:
    """Test different execution modes."""
    
    def test_interactive_mode_default(self):
        """Test that interactive mode is the default."""
        code = """
x = 100
x * 2
"""
        result = run_python_code(code)
        assert result == 200
    
    def test_interactive_mode_explicit(self):
        """Test explicit interactive mode."""
        code = """
result = 7 * 8
result
"""
        result = run_python_code(code, mode='interactive')
        assert result == 56
    
    @patch('builtins.print')  # Mock print to avoid output during tests
    def test_ast_dump_is_called(self, mock_print):
        """Test that AST dump is printed during execution."""
        run_python_code("2 + 2")
        
        # Should have called print with AST dump
        assert mock_print.called
        # Check that the printed content contains AST-like structure
        call_args = mock_print.call_args_list
        assert len(call_args) >= 1


class TestRunPythonCodeEdgeCases:
    """Test edge cases and special scenarios."""
    
    def test_empty_code(self):
        """Test execution of empty code."""
        result = run_python_code("")
        assert result is None
    
    def test_whitespace_only_code(self):
        """Test execution of whitespace-only code."""
        result = run_python_code("   \n  \t  ")
        assert result is None
    
    def test_comment_only_code(self):
        """Test execution of comment-only code."""
        result = run_python_code("# This is just a comment")
        assert result is None
    
    def test_multiline_string_expression(self):
        """Test multiline string as expression."""
        code = '''"""
This is a
multiline string
"""'''
        result = run_python_code(code)
        expected = "\nThis is a\nmultiline string\n"
        assert result == expected
    
    def test_nested_function_calls(self):
        """Test nested function calls."""
        code = """
def outer(x):
    def inner(y):
        return y * 2
    return inner(x) + 5

outer(10)
"""
        result = run_python_code(code)
        assert result == 25
    
    def test_lambda_expressions(self):
        """Test lambda expressions."""
        code = """
square = lambda x: x ** 2
square(8)
"""
        result = run_python_code(code)
        assert result == 64
    
    def test_generator_expression(self):
        """Test generator expressions."""
        code = "sum(x*2 for x in range(5))"
        result = run_python_code(code)
        assert result == 20  # (0+2+4+6+8)


class TestRunPythonFile:
    """Test run_python_file function."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_files = []
    
    def teardown_method(self):
        """Clean up test fixtures."""
        for file_path in self.temp_files:
            try:
                os.unlink(file_path)
            except FileNotFoundError:
                pass
        try:
            os.rmdir(self.temp_dir)
        except OSError:
            pass
    
    def create_temp_file(self, content: str, filename: str = "test.py") -> str:
        """Create a temporary Python file with given content."""
        file_path = os.path.join(self.temp_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        self.temp_files.append(file_path)
        return file_path
    
    def test_run_simple_python_file(self):
        """Test running a simple Python file."""
        content = """
x = 15
y = 25
x + y
"""
        file_path = self.create_temp_file(content)
        result = run_python_file(file_path)
        assert result == 40
    
    def test_run_file_with_function_definition(self):
        """Test running file with function definition."""
        content = """
def multiply(a, b):
    return a * b

def main():
    return multiply(6, 7)

main()
"""
        file_path = self.create_temp_file(content)
        result = run_python_file(file_path)
        assert result == 42
    
    def test_run_file_with_imports(self):
        """Test running file that imports standard library modules."""
        content = """
import math
import os

def calculate():
    return math.pi * 2

calculate()
"""
        file_path = self.create_temp_file(content)
        result = run_python_file(file_path)
        assert abs(result - (math.pi * 2)) < 1e-10
    
    def test_run_file_with_local_import(self):
        """Test running file that imports a sibling module."""
        # Create helper module
        helper_content = """
def helper_function():
    return "Hello from helper"
"""
        helper_path = self.create_temp_file(helper_content, "helper.py")
        
        # Create main module that imports helper
        main_content = """
import helper

result = helper.helper_function()
result
"""
        main_path = self.create_temp_file(main_content, "main.py")
        
        result = run_python_file(main_path)
        assert result == "Hello from helper"
    
    def test_file_not_found_raises_error(self):
        """Test that non-existent file raises FileNotFoundError."""
        non_existent_path = "/path/that/does/not/exist/file.py"
        
        with pytest.raises(FileNotFoundError, match="Python file not found"):
            run_python_file(non_existent_path)
    
    def test_file_path_expansion(self):
        """Test that file paths are properly expanded."""
        content = "42"
        file_path = self.create_temp_file(content)
        
        # Test with Path object
        result = run_python_file(Path(file_path))
        assert result == 42
    
    def test_syntax_error_in_file(self):
        """Test that syntax errors in file are properly raised."""
        content = "def invalid syntax:"
        file_path = self.create_temp_file(content)
        
        with pytest.raises(SyntaxError):
            run_python_file(file_path)
    
    def test_runtime_error_in_file(self):
        """Test that runtime errors in file are properly raised."""
        content = "undefined_variable + 10"
        file_path = self.create_temp_file(content)
        
        with pytest.raises(NameError):
            run_python_file(file_path)
    
    def test_file_with_encoding(self):
        """Test file with special characters (UTF-8 encoding)."""
        content = '''
message = "Hello, 世界! 🌍"
len(message)
'''
        file_path = self.create_temp_file(content)
        result = run_python_file(file_path)
        assert result == 12  # Length includes Unicode characters
    
    def test_mode_parameter_passed_through(self):
        """Test that mode parameter is passed to run_python_code."""
        content = """
x = 100
x / 4
"""
        file_path = self.create_temp_file(content)
        
        result = run_python_file(file_path, mode='interactive')
        assert result == 25.0


class TestRunPythonFileSysPathManagement:
    """Test sys.path management in run_python_file."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_files = []
        self.original_sys_path = sys.path.copy()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        # Restore original sys.path
        sys.path[:] = self.original_sys_path
        
        for file_path in self.temp_files:
            try:
                os.unlink(file_path)
            except FileNotFoundError:
                pass
        try:
            os.rmdir(self.temp_dir)
        except OSError:
            pass
    
    def create_temp_file(self, content: str, filename: str = "test.py") -> str:
        """Create a temporary Python file with given content."""
        file_path = os.path.join(self.temp_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        self.temp_files.append(file_path)
        return file_path
    
    def test_sys_path_added_and_removed(self):
        """Test that script directory is added to and removed from sys.path."""
        content = "42"
        file_path = self.create_temp_file(content)
        
        script_dir = str(Path(file_path).parent)
        
        # Script directory should not be in sys.path initially
        assert script_dir not in sys.path
        
        # Run file
        result = run_python_file(file_path)
        assert result == 42
        
        # Script directory should be removed from sys.path after execution
        assert script_dir not in sys.path
    
    def test_sys_path_not_duplicated(self):
        """Test that script directory is not added if already in sys.path."""
        content = "99"
        file_path = self.create_temp_file(content)
        
        script_dir = str(Path(file_path).parent)
        
        # Add script directory to sys.path before running
        sys.path.insert(0, script_dir)
        original_count = sys.path.count(script_dir)
        
        # Run file
        result = run_python_file(file_path)
        assert result == 99
        
        # Should not have added another copy
        assert sys.path.count(script_dir) == original_count
    
    def test_sys_path_cleanup_on_exception(self):
        """Test that sys.path is cleaned up even when execution raises exception."""
        content = "undefined_variable"
        file_path = self.create_temp_file(content)
        
        script_dir = str(Path(file_path).parent)
        
        # Script directory should not be in sys.path initially
        assert script_dir not in sys.path
        
        # Run file (will raise exception)
        with pytest.raises(NameError):
            run_python_file(file_path)
        
        # Script directory should still be removed from sys.path
        assert script_dir not in sys.path


class TestRunPythonCodeComplexScenarios:
    """Test complex scenarios and real-world use cases."""
    
    def test_data_analysis_scenario(self):
        """Test data analysis-like code execution."""
        code = """
data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
total = sum(data)
average = total / len(data)
filtered = [x for x in data if x > average]
len(filtered)
"""
        result = run_python_code(code)
        assert result == 4  # Numbers greater than 5.5: [6, 7, 8, 9, 10]
    
    def test_object_oriented_programming(self):
        """Test OOP concepts in execution."""
        code = """
class Calculator:
    def __init__(self):
        self.history = []
    
    def add(self, a, b):
        result = a + b
        self.history.append(f"{a} + {b} = {result}")
        return result
    
    def get_history_count(self):
        return len(self.history)

calc = Calculator()
calc.add(10, 15)
calc.add(20, 25)
calc.get_history_count()
"""
        result = run_python_code(code)
        assert result == 2
    
    def test_exception_handling_in_code(self):
        """Test exception handling within executed code."""
        code = """
def safe_divide(a, b):
    try:
        return a / b
    except ZeroDivisionError:
        return "Cannot divide by zero"

safe_divide(10, 0)
"""
        result = run_python_code(code)
        assert result == "Cannot divide by zero"
    
    def test_decorators_and_closures(self):
        """Test decorators and closure execution."""
        code = """
def multiplier(factor):
    def decorator(func):
        def wrapper(x):
            return func(x) * factor
        return wrapper
    return decorator

@multiplier(3)
def double(x):
    return x * 2

double(5)
"""
        result = run_python_code(code)
        assert result == 30  # 5 * 2 * 3
    
    def test_context_managers(self):
        """Test context manager execution."""
        code = """
class TestContext:
    def __enter__(self):
        return "entered"
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

result = None
with TestContext() as ctx:
    result = ctx

result
"""
        result = run_python_code(code)
        assert result == "entered"


class TestRunPythonIntegration:
    """Test integration between run_python_code and run_python_file."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_files = []
    
    def teardown_method(self):
        """Clean up test fixtures."""
        for file_path in self.temp_files:
            try:
                os.unlink(file_path)
            except FileNotFoundError:
                pass
        try:
            os.rmdir(self.temp_dir)
        except OSError:
            pass
    
    def create_temp_file(self, content: str, filename: str = "test.py") -> str:
        """Create a temporary Python file with given content."""
        file_path = os.path.join(self.temp_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        self.temp_files.append(file_path)
        return file_path
    
    def test_same_code_same_result(self):
        """Test that same code produces same result in both functions."""
        code = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

factorial(5)
"""
        
        # Test direct code execution
        direct_result = run_python_code(code)
        
        # Test file execution
        file_path = self.create_temp_file(code)
        file_result = run_python_file(file_path)
        
        assert direct_result == file_result == 120