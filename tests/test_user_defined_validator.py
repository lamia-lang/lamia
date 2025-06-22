import pytest
import asyncio
import sys
import os
from lamia.validation.validators import FunctionalValidator
from lamia.validation.base import BaseValidator, ValidationResult

# TODO: Modify this test

# Add the examples directory to the path so we can import CodeValidator
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'examples', 'custom_validators'))

try:
    from examples.custom_validators.code_validator import CodeValidator
except ImportError:
    pytest.skip("CodeValidator not available", allow_module_level=True)


class TestUserDefinedValidator:
    """Test suite for validating user-defined validators using FunctionalValidator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.code_validator = CodeValidator(language="python", strict=True)
    
    def test_validator_inheritance(self):
        """Test that user-defined validator properly inherits from BaseValidator."""
        assert isinstance(self.code_validator, BaseValidator)
        assert hasattr(self.code_validator, 'validate_strict')
        assert hasattr(self.code_validator, 'validate_permissive')
        assert hasattr(self.code_validator, 'name')
        assert hasattr(self.code_validator, 'initial_hint')
    
    @pytest.mark.asyncio
    async def test_validator_name_property_contract(self):
        """Test that validator name property returns expected value using FunctionalValidator."""
        
        # Test that the name property returns the expected string
        test_cases = [
            # CodeValidator with python language should return "code_python"
            ((self.code_validator,), "code_python"),
        ]
        
        validator = FunctionalValidator(test_cases=test_cases)
        
        # Function that extracts the name from the validator
        function_code = """
def get_validator_name(validator_instance):
    return validator_instance.name
"""
        
        result = await validator.validate_strict(function_code)
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_validator_initial_hint_contract(self):
        """Test that initial_hint property returns expected string using FunctionalValidator."""
        
        test_cases = [
            # CodeValidator should return its specific hint
            ((self.code_validator,), "Please return only valid Python code, with no explanation or extra text."),
        ]
        
        validator = FunctionalValidator(test_cases=test_cases)
        
        function_code = """
def get_validator_hint(validator_instance):
    return validator_instance.initial_hint
"""
        
        result = await validator.validate_strict(function_code)
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_code_validator_strict_with_valid_code(self):
        """Test CodeValidator.validate_strict with valid Python code using FunctionalValidator."""
        
        test_cases = [
            # Valid Python code should return ValidationResult with is_valid=True
            ((self.code_validator, "print('hello')"), True),
            ((self.code_validator, "x = 1\ny = 2\nprint(x + y)"), True),
        ]
        
        validator = FunctionalValidator(test_cases=test_cases)
        
        function_code = """
import asyncio
def test_valid_code(validator_instance, code):
    result = asyncio.run(validator_instance.validate_strict(code))
    return result.is_valid
"""
        
        result = await validator.validate_strict(function_code)
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_code_validator_strict_with_invalid_code(self):
        """Test CodeValidator.validate_strict with invalid Python code using FunctionalValidator."""
        
        test_cases = [
            # Invalid Python code should return ValidationResult with is_valid=False
            ((self.code_validator, "print('hello'"), False),  # Missing closing quote
            ((self.code_validator, "x = 1\nprint(x"), False),  # Missing closing paren
            ((self.code_validator, "invalid syntax here"), False),
        ]
        
        validator = FunctionalValidator(test_cases=test_cases)
        
        function_code = """
import asyncio
def test_invalid_code(validator_instance, code):
    result = asyncio.run(validator_instance.validate_strict(code))
    return result.is_valid
"""
        
        result = await validator.validate_strict(function_code)
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_code_validator_permissive_with_valid_code(self):
        """Test CodeValidator.validate_permissive with valid Python code using FunctionalValidator."""
        
        test_cases = [
            # Valid Python code should return ValidationResult with is_valid=True
            ((self.code_validator, "print('hello')"), True),
            ((self.code_validator, "def foo(): pass"), True),
        ]
        
        validator = FunctionalValidator(test_cases=test_cases)
        
        function_code = """
import asyncio
def test_permissive_valid_code(validator_instance, code):
    result = asyncio.run(validator_instance.validate_permissive(code))
    return result.is_valid
"""
        
        result = await validator.validate_strict(function_code)
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_code_validator_permissive_with_markdown(self):
        """Test CodeValidator.validate_permissive extracts code from markdown using FunctionalValidator."""
        
        test_cases = [
            # Markdown-wrapped code should be extracted and validated as True in permissive mode
            ((self.code_validator, "```python\nprint('hello')\n```"), True),
            ((self.code_validator, "```\nx = 1\nprint(x)\n```"), True),
        ]
        
        validator = FunctionalValidator(test_cases=test_cases)
        
        function_code = """
import asyncio
def test_permissive_markdown(validator_instance, markdown_code):
    result = asyncio.run(validator_instance.validate_permissive(markdown_code))
    return result.is_valid
"""
        
        result = await validator.validate_strict(function_code)
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_code_validator_strict_rejects_markdown(self):
        """Test CodeValidator.validate_strict rejects markdown-wrapped code using FunctionalValidator."""
        
        test_cases = [
            # Strict mode should reject markdown-wrapped code (not pure Python)
            ((self.code_validator, "```python\nprint('hello')\n```"), False),
            ((self.code_validator, "Some text\n```python\nx = 1\n```"), False),
        ]
        
        validator = FunctionalValidator(test_cases=test_cases)
        
        function_code = """
import asyncio
def test_strict_rejects_markdown(validator_instance, markdown_code):
    result = asyncio.run(validator_instance.validate_strict(markdown_code))
    return result.is_valid
"""
        
        result = await validator.validate_strict(function_code)
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_code_validator_unsupported_language(self):
        """Test CodeValidator with unsupported language using FunctionalValidator."""
        
        # Create a CodeValidator with unsupported language
        js_validator = CodeValidator(language="javascript", strict=True)
        
        test_cases = [
            # JavaScript code should be rejected (unsupported language)
            ((js_validator, "console.log('hello');"), False),
            ((js_validator, "var x = 1;"), False),
        ]
        
        validator = FunctionalValidator(test_cases=test_cases)
        
        function_code = """
import asyncio
def test_unsupported_language(validator_instance, code):
    result = asyncio.run(validator_instance.validate_strict(code))
    return result.is_valid
"""
        
        result = await validator.validate_strict(function_code)
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_code_validator_error_message_contains_details(self):
        """Test that CodeValidator provides meaningful error messages using FunctionalValidator."""
        
        test_cases = [
            # Invalid code should produce error message containing "Code parsing failed"
            ((self.code_validator, "invalid syntax"), "Code parsing failed"),
        ]
        
        validator = FunctionalValidator(test_cases=test_cases)
        
        function_code = """
import asyncio
def get_error_message_prefix(validator_instance, code):
    result = asyncio.run(validator_instance.validate_strict(code))
    if result.error_message and "Code parsing failed" in result.error_message:
        return "Code parsing failed"
    return result.error_message or "No error message"
"""
        
        result = await validator.validate_strict(function_code)
        assert result.is_valid is True


class TestValidatorContractCompliance:
    """Test that CodeValidator implements BaseValidator contract correctly."""
    
    @pytest.mark.asyncio
    async def test_instantiation_with_different_languages(self):
        """Test CodeValidator instantiation with different language parameters using FunctionalValidator."""
        
        test_cases = [
            # Python language should work
            (("python", True), "code_python"),
            # JavaScript language should also create validator (but will fail validation)
            (("javascript", True), "code_javascript"),
        ]
        
        validator = FunctionalValidator(test_cases=test_cases)
        
        function_code = """
def create_validator_and_get_name(language, strict):
    validator = CodeValidator(language=language, strict=strict)
    return validator.name
"""
        
        result = await validator.validate_strict(function_code)
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_functional_validator_meta_test(self):
        """Meta-test: Use FunctionalValidator to test FunctionalValidator itself."""
        
        # Create a simple test case for FunctionalValidator
        simple_test_cases = [((1, 2), 3)]
        functional_validator = FunctionalValidator(test_cases=simple_test_cases)
        
        test_cases = [
            ((functional_validator, "def add(a, b): return a + b"), True),
        ]
        
        meta_validator = FunctionalValidator(test_cases=test_cases)
        
        function_code = """
import asyncio
def test_functional_validator(validator_instance, function_code):
    result = asyncio.run(validator_instance.validate_strict(function_code))
    return result.is_valid
"""
        
        result = await meta_validator.validate_strict(function_code)
        assert result.is_valid is True 