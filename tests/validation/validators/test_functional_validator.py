import pytest
import asyncio
from lamia.validation.validators import FunctionalValidator
from lamia.validation.base import ValidationResult


class TestFunctionalValidator:
    """Test suite for FunctionalValidator."""
    
    def test_init_basic(self):
        """Test basic initialization of FunctionalValidator."""
        test_cases = [((1, 2), 3)]
        validator = FunctionalValidator(test_cases=test_cases)
        assert validator.test_cases == test_cases
        assert validator.strict is True
        
    def test_init_with_strict_false(self):
        """Test initialization with strict=False."""
        test_cases = [((1, 2), 3)]
        validator = FunctionalValidator(test_cases=test_cases, strict=False)
        assert validator.strict is False
        
    def test_name(self):
        """Test validator name."""
        test_cases = [((1, 2), 3)]
        validator = FunctionalValidator(test_cases=test_cases)
        assert validator.name() == "functional"
        
    def test_initial_hint(self):
        """Test initial hint property."""
        test_cases = [((1, 2), 3)]
        validator = FunctionalValidator(test_cases=test_cases)
        expected_hint = """Please provide a function that satisfies all the given test cases:
  - func(1, 2) should return 3

Provide only the function definition, no explanation or extra text."""
        assert validator.initial_hint == expected_hint
        
    def test_initial_hint_with_exceptions(self):
        """Test initial hint with complex test cases including exceptions."""
        test_cases = [
            ((1, 2), 3),
            ((0,), ValueError), 
            ((0, 0), 0)
        ]
        validator = FunctionalValidator(test_cases=test_cases)
        expected_hint = """Please provide a function that satisfies all the given test cases:
  - func(1, 2) should return 3
  - func(0) should raise ValueError
  - func(0, 0) should return 0

Provide only the function definition, no explanation or extra text."""
        assert validator.initial_hint == expected_hint
    
    @pytest.mark.asyncio
    async def test_simple_addition_function_valid(self):
        """Test validation of a simple addition function that passes."""
        test_cases = [
            ((1, 2), 3),
            ((0, 0), 0),
            ((5, -3), 2)
        ]
        validator = FunctionalValidator(test_cases=test_cases)
        
        function_code = """
def add_numbers(a, b):
    return a + b
"""
        
        result = await validator.validate_strict(function_code)
        assert result.is_valid is True
        assert result.error_message is None
        
    @pytest.mark.asyncio
    async def test_simple_addition_function_invalid(self):
        """Test validation of a simple addition function that fails."""
        test_cases = [
            ((1, 2), 3),
            ((0, 0), 1),  # This should fail - expecting 1 but function returns 0
        ]
        validator = FunctionalValidator(test_cases=test_cases)
        
        function_code = """
def add_numbers(a, b):
    return a + b
"""
        
        result = await validator.validate_strict(function_code)
        assert result.is_valid is False
        assert "Test case 2" in result.error_message
        assert "Expected 1 but got 0" in result.error_message
        
    @pytest.mark.asyncio
    async def test_function_with_exception_valid(self):
        """Test validation of function that correctly raises expected exception."""
        test_cases = [
            ((1, 2), 3),
            ((0,), ValueError),  # Should raise ValueError
            ((0, 0), 0)
        ]
        validator = FunctionalValidator(test_cases=test_cases)
        
        function_code = """
def smart_add(a, b=None):
    if a == 0 and b is None:
        raise ValueError("Cannot process zero with no second argument")
    if b is None:
        return a
    return a + b
"""
        
        result = await validator.validate_strict(function_code)
        assert result.is_valid is True
        
    @pytest.mark.asyncio
    async def test_function_with_wrong_exception(self):
        """Test validation when function raises wrong exception type."""
        test_cases = [
            ((0,), ValueError),  # Expecting ValueError
        ]
        validator = FunctionalValidator(test_cases=test_cases)
        
        function_code = """
def bad_function(a):
    if a == 0:
        raise TypeError("Wrong exception type")
    return a
"""
        
        result = await validator.validate_strict(function_code)
        assert result.is_valid is False
        assert "Expected ValueError but got TypeError" in result.error_message
        
    @pytest.mark.asyncio
    async def test_function_should_raise_but_returns_value(self):
        """Test validation when function should raise exception but returns value instead."""
        test_cases = [
            ((0,), ValueError),  # Should raise ValueError
        ]
        validator = FunctionalValidator(test_cases=test_cases)
        
        function_code = """
def bad_function(a):
    return a * 2  # Should raise but doesn't
"""
        
        result = await validator.validate_strict(function_code)
        assert result.is_valid is False
        assert "Expected ValueError but got result: 0" in result.error_message
        
    @pytest.mark.asyncio
    async def test_function_raises_unexpected_exception(self):
        """Test validation when function raises unexpected exception."""
        test_cases = [
            ((1, 2), 3),  # Should return 3
        ]
        validator = FunctionalValidator(test_cases=test_cases)
        
        function_code = """
def bad_function(a, b):
    raise RuntimeError("Unexpected error")
"""
        
        result = await validator.validate_strict(function_code)
        assert result.is_valid is False
        assert "Unexpected exception RuntimeError" in result.error_message
        
    @pytest.mark.asyncio
    async def test_invalid_function_syntax(self):
        """Test validation with syntactically invalid function."""
        test_cases = [((1, 2), 3)]
        validator = FunctionalValidator(test_cases=test_cases)
        
        invalid_code = """
def bad_function(a, b
    return a + b  # Missing closing parenthesis
"""
        
        result = await validator.validate_strict(invalid_code)
        assert result.is_valid is False
        assert "Failed to parse or execute function" in result.error_message
        
    @pytest.mark.asyncio
    async def test_no_function_in_response(self):
        """Test validation when no function is found in response."""
        test_cases = [((1, 2), 3)]
        validator = FunctionalValidator(test_cases=test_cases)
        
        no_function_code = "This is just some text with no function definition."
        
        result = await validator.validate_strict(no_function_code)
        assert result.is_valid is False
        # When no function is found, it tries to execute the text, causing a syntax error
        assert "Failed to parse or execute function" in result.error_message
        
    @pytest.mark.asyncio
    async def test_multiple_functions_in_response(self):
        """Test validation when multiple functions are found in response."""
        test_cases = [((1, 2), 3)]
        validator = FunctionalValidator(test_cases=test_cases)
        
        multiple_functions = """
def function1(a, b):
    return a + b

def function2(x, y):
    return x * y
"""
        
        result = await validator.validate_strict(multiple_functions)
        assert result.is_valid is False
        assert "Multiple functions found" in result.error_message
        
    @pytest.mark.asyncio
    async def test_complex_test_cases(self):
        """Test with more complex test cases including various data types."""
        test_cases = [
            (("hello", "world"), "helloworld"),
            (([1, 2, 3],), 6),
            ((42,), ValueError),
        ]
        validator = FunctionalValidator(test_cases=test_cases)
        
        function_code = """
def process_input(data, suffix=None):
    if isinstance(data, str) and suffix:
        return data + suffix
    elif isinstance(data, list):
        return sum(data)
    elif data == 42:
        raise ValueError("Special number not allowed")
    return data
"""
        
        result = await validator.validate_strict(function_code)
        assert result.is_valid is True
        
    @pytest.mark.asyncio
    async def test_function_with_comments_and_docstring(self):
        """Test validation with function that has comments and docstring."""
        test_cases = [((5, 3), 8)]
        validator = FunctionalValidator(test_cases=test_cases)
        
        function_with_docs = '''
def add_numbers(a, b):
    """
    Add two numbers together.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Sum of a and b
    """
    # Simple addition
    result = a + b
    return result
'''
        
        result = await validator.validate_strict(function_with_docs)
        assert result.is_valid is True
        
    @pytest.mark.asyncio
    async def test_permissive_validation(self):
        """Test permissive validation mode."""
        test_cases = [((1, 2), 3)]
        validator = FunctionalValidator(test_cases=test_cases, strict=False)
        
        function_code = """
def add_numbers(a, b):
    return a + b
"""
        
        result = await validator.validate_permissive(function_code)
        assert result.is_valid is True
        
    @pytest.mark.asyncio
    async def test_edge_case_empty_args(self):
        """Test with functions that take no arguments."""
        test_cases = [
            ((), 42),  # No arguments, should return 42
        ]
        validator = FunctionalValidator(test_cases=test_cases)
        
        function_code = """
def get_answer():
    return 42
"""
        
        result = await validator.validate_strict(function_code)
        assert result.is_valid is True
        
    @pytest.mark.asyncio
    async def test_edge_case_single_argument(self):
        """Test with functions that take single argument."""
        test_cases = [
            ((5,), 25),  # Single argument, should return square
        ]
        validator = FunctionalValidator(test_cases=test_cases)
        
        function_code = """
def square(x):
    return x * x
"""
        
        result = await validator.validate_strict(function_code)
        assert result.is_valid is True
        
    @pytest.mark.asyncio
    async def test_validation_result_properties(self):
        """Test that ValidationResult has correct properties set."""
        test_cases = [((1, 2), 3)]
        validator = FunctionalValidator(test_cases=test_cases)
        
        function_code = """
def add_numbers(a, b):
    return a + b
"""
        
        result = await validator.validate_strict(function_code)
        assert result.is_valid is True
        assert result.validated_text == "add_numbers"
        assert result.error_message is None
        
    @pytest.mark.asyncio
    async def test_multiple_exception_types(self):
        """Test with multiple different exception types in test cases."""
        test_cases = [
            ((0,), ValueError),
            ((-1,), TypeError),
            ((1, 2), 3),
        ]
        validator = FunctionalValidator(test_cases=test_cases)
        
        function_code = """
def special_function(a, b=None):
    if a == 0:
        raise ValueError("Zero not allowed")
    elif a < 0:
        raise TypeError("Negative not allowed")
    elif b is None:
        return a
    else:
        return a + b
"""
        
        result = await validator.validate_strict(function_code)
        assert result.is_valid is True 