import pytest
import asyncio
import subprocess
from lamia.validation.validators.functional_validator import FunctionalValidator
from lamia.validation.base import ValidationResult


def test_functional_validator_initializes_with_basic_parameters():
    """Test that FunctionalValidator can be initialized with test cases and default parameters."""
    test_cases = [((1, 2), 3), ((5, 3), 8)]
    validator = FunctionalValidator(test_cases)
    
    assert validator.test_cases == test_cases
    assert validator.execution_timeout == 5
    assert validator.use_docker == False
    assert validator.name == "functional"


def test_functional_validator_initializes_with_docker_explicitly_disabled():
    """Test that FunctionalValidator can be initialized with Docker explicitly disabled."""
    test_cases = [((1, 2), 3)]
    validator = FunctionalValidator(test_cases, use_docker=False)
    
    assert validator.use_docker == False


def test_functional_validator_generates_initial_hint_with_test_cases():
    """Test that FunctionalValidator generates proper initial hints including test case examples."""
    test_cases = [
        ((1, 2), 3),
        ((0,), ValueError),
        (("hello",), "HELLO")
    ]
    validator = FunctionalValidator(test_cases)
    hint = validator.initial_hint
    
    assert "Please provide a Python function" in hint
    assert "```python" in hint
    assert "func(1, 2) should return 3" in hint
    assert "func(0) should raise ValueError" in hint
    assert "func('hello') should return 'HELLO'" in hint
    assert "Do NOT include any explanations" in hint


@pytest.mark.asyncio
async def test_functional_validator_blocks_dangerous_os_imports():
    """Test that FunctionalValidator blocks code containing dangerous os module imports."""
    test_cases = [((1, 2), 3)]
    validator = FunctionalValidator(test_cases)
    
    dangerous_code = """
import os
def bad_function(a, b):
    os.system("rm -rf /")
    return a + b
"""
    
    result = await validator.validate(dangerous_code)
    assert not result.is_valid
    assert "dangerous import detected" in result.error_message.lower()


@pytest.mark.asyncio
async def test_functional_validator_blocks_dangerous_exec_operations():
    """Test that FunctionalValidator blocks code containing dangerous exec operations."""
    test_cases = [((1, 2), 3)]
    validator = FunctionalValidator(test_cases)
    
    dangerous_code = """
def bad_function(a, b):
    exec("print('hacked')")
    return a + b
"""
    
    result = await validator.validate(dangerous_code)
    assert not result.is_valid
    assert "dangerous operation detected" in result.error_message.lower()


@pytest.mark.asyncio
async def test_functional_validator_stops_infinite_loops_with_timeout():
    """Test that FunctionalValidator stops infinite loops using execution timeout protection."""
    test_cases = [((1,), 1)]
    validator = FunctionalValidator(test_cases, execution_timeout=2)
    
    infinite_loop_code = """
def infinite_function(x):
    while True:
        pass
    return x
"""
    
    result = await validator.validate(infinite_loop_code)
    assert not result.is_valid
    assert "timed out" in result.error_message.lower()


@pytest.mark.asyncio
async def test_functional_validator_validates_direct_function_objects():
    """Test that FunctionalValidator can validate direct function objects passed as parameters."""
    test_cases = [((1, 2), 3), ((-1, 5), 4), ((0, 0), 0)]
    validator = FunctionalValidator(test_cases)
    
    def sum(a, b):
        return a + b
    
    result = await validator.validate(sum)
    assert result.is_valid


@pytest.mark.asyncio
async def test_functional_validator_validates_clean_function_code_strings():
    """Test that FunctionalValidator can validate clean Python function code provided as strings."""
    test_cases = [((2, 3), 6), ((4, 5), 20)]
    validator = FunctionalValidator(test_cases)
    
    clean_code = """def multiply(a, b):
    return a * b"""
    
    result = await validator.validate(clean_code)
    assert result.is_valid


@pytest.mark.asyncio
async def test_functional_validator_extracts_code_from_markdown_blocks():
    """Test that FunctionalValidator can extract and validate Python code from markdown code blocks."""
    test_cases = [((2, 3), 5), ((10, 5), 15)]
    validator = FunctionalValidator(test_cases, strict=False)
    
    chatty_response = """
Here's a function that adds two numbers:

```python
def add_numbers(x, y):
    return x + y
```

This function should work correctly.
"""

    chatty_response_without_language_tag = """
Here's a function that adds two numbers:

```
def add_numbers(x, y):
    return x + y
```

This function should work correctly.
"""
    
    result = await validator.validate(chatty_response)
    assert result.is_valid
    
    result = await validator.validate(chatty_response_without_language_tag)
    assert result.is_valid

@pytest.mark.asyncio
async def test_functional_validator_handles_functions_that_raise_expected_exceptions():
    """Test that FunctionalValidator correctly validates functions expected to raise specific exceptions."""
    test_cases = [
        ((1, 2), 3),
        ((0,), ValueError),
        ((1, 0), ZeroDivisionError)
    ]
    validator = FunctionalValidator(test_cases)
    
    exception_code = """
def test_function(a, b=None):
    if b is None:
        raise ValueError("Second argument required")
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return a + b
"""
    
    result = await validator.validate(exception_code)
    assert result.is_valid


@pytest.mark.asyncio
async def test_functional_validator_fails_validation_for_incorrect_function_logic():
    """Test that FunctionalValidator fails validation when function produces wrong results."""
    test_cases = [((1, 2), 3), ((5, 3), 8)]
    validator = FunctionalValidator(test_cases)
    
    wrong_code = """def multiply(a, b):
    return a * b"""  # Should add, not multiply
    
    result = await validator.validate(wrong_code)
    assert not result.is_valid
    assert "Expected 3 but got 2" in result.error_message


@pytest.mark.asyncio
async def test_functional_validator_handles_syntax_errors_in_code():
    """Test that FunctionalValidator properly handles and reports syntax errors in provided code."""
    test_cases = [((1, 2), 3)]
    validator = FunctionalValidator(test_cases)
    
    bad_syntax = """def bad_function(a, b
    return a + b"""  # Missing closing parenthesis
    
    result = await validator.validate(bad_syntax)
    assert not result.is_valid
    assert "syntax error" in result.error_message.lower()


@pytest.mark.asyncio
async def test_functional_validator_reports_when_no_function_found_in_code():
    """Test that FunctionalValidator reports error when no function definition is found in code."""
    test_cases = [((1, 2), 3)]
    validator = FunctionalValidator(test_cases)
    
    no_function = """x = 1 + 2
print("No function here")"""
    
    result = await validator.validate(no_function)
    assert not result.is_valid
    assert "no function" in result.error_message.lower()


@pytest.mark.asyncio
async def test_functional_validator_rejects_invalid_input_types():
    """Test that FunctionalValidator rejects invalid input types (neither function nor string)."""
    test_cases = [((1, 2), 3)]
    validator = FunctionalValidator(test_cases)
    
    result = await validator.validate(123)  # Integer instead of string/function
    assert not result.is_valid
    assert "Expected function or string" in result.error_message


@pytest.mark.asyncio
async def test_functional_validator_rejects_multiple_function_definitions():
    """Test that FunctionalValidator rejects code containing multiple function definitions."""
    test_cases = [((1, 2), 3)]
    validator = FunctionalValidator(test_cases)
    
    multiple_functions = """
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b
"""
    
    result = await validator.validate(multiple_functions)
    assert not result.is_valid
    assert "multiple functions" in result.error_message.lower()


@pytest.mark.asyncio
async def test_functional_validator_extracts_indented_functions_from_responses():
    """Test that FunctionalValidator can extract and validate indented function definitions."""
    test_cases = [((3, 2), 5)]
    validator = FunctionalValidator(test_cases, strict=False)
    
    indented_response = """
    Here is the solution:

        def add_function(a, b):
            return a + b

    This should work.
"""
    
    result = await validator.validate(indented_response)
    assert result.is_valid


def test_functional_validator_accepts_custom_timeout_configuration():
    """Test that FunctionalValidator accepts and stores custom execution timeout values."""
    test_cases = [((1, 2), 3)]
    validator = FunctionalValidator(test_cases, execution_timeout=10)
    
    assert validator.execution_timeout == 10


def test_functional_validator_detects_function_definitions_in_content():
    """Test that FunctionalValidator can detect function definitions in various code formats."""
    # Should detect function definitions
    function_code = """
def add_numbers(a, b):
    return a + b
"""
    assert FunctionalValidator.can_handle_content(function_code) == True
    
    # Should detect markdown code blocks
    markdown_code = """
Here's a function:

```python
def multiply(x, y):
    return x * y
```
"""
    assert FunctionalValidator.can_handle_content(markdown_code) == True
    
    # Should detect lambda expressions
    lambda_code = "lambda x, y: x + y"
    assert FunctionalValidator.can_handle_content(lambda_code) == True


def test_functional_validator_rejects_non_function_content():
    """Test that FunctionalValidator correctly rejects content that doesn't contain functions."""
    # Regular text
    regular_text = "This is just some regular text without any code."
    assert FunctionalValidator.can_handle_content(regular_text) == False
    
    # JSON data
    json_data = '{"name": "John", "age": 30}'
    assert FunctionalValidator.can_handle_content(json_data) == False
    
    # Empty content
    assert FunctionalValidator.can_handle_content("") == False
    assert FunctionalValidator.can_handle_content(None) == False


def test_functional_validator_extracts_test_cases_from_code_comments():
    """Test that FunctionalValidator can suggest test cases from examples in code comments."""
    code_with_examples = """
def add_numbers(a, b):
    # add_numbers(1, 2) should return 3
    # add_numbers(0, 0) = 0
    return a + b
"""
    test_cases = FunctionalValidator.suggest_test_cases_from_content(code_with_examples)
    # Should extract test cases from comments
    assert len(test_cases) >= 1


def test_functional_validator_suggests_test_cases_from_function_signature():
    """Test that FunctionalValidator can suggest basic test cases from function signature analysis."""
    simple_function = """
def calculate(x, y):
    return x + y
"""
    test_cases = FunctionalValidator.suggest_test_cases_from_content(simple_function)
    # Should suggest basic test cases for 2-parameter function
    assert len(test_cases) >= 1
    assert len(test_cases[0][0]) == 2  # Two parameters


def test_functional_validator_auto_creates_validator_from_content():
    """Test that FunctionalValidator can automatically create a validator instance from code content."""
    function_code = """
def add_function(a, b):
    return a + b
"""
    validator = FunctionalValidator.auto_create_for_content(function_code)
    
    assert isinstance(validator, FunctionalValidator)
    assert len(validator.test_cases) > 0
    assert validator.strict == False  # Should use permissive mode


def test_functional_validator_recommends_docker_for_risky_code():
    """Test that FunctionalValidator recommends Docker execution for code containing risky imports."""
    risky_code = """
import os
def dangerous_function():
    os.system("ls")
"""
    should_use_docker = FunctionalValidator._should_use_docker_for_content(risky_code)
    assert should_use_docker == True


def test_functional_validator_does_not_recommend_docker_for_safe_code():
    """Test that FunctionalValidator does not recommend Docker for safe, simple function code."""
    safe_code = """
def safe_function(a, b):
    return a + b
"""
    should_use_docker = FunctionalValidator._should_use_docker_for_content(safe_code)
    assert should_use_docker == False
