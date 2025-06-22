import pytest
import asyncio
import ast
import re
from lamia.validation.validators.functional_validator import FunctionalValidator
from lamia.validation.base import BaseValidator, ValidationResult


def test_empty_class_fails_instantiation():
    """Test: Empty class should fail during instantiation due to abstract methods"""
    
    # CodeValidator implementation: Empty class
    class CodeValidator(BaseValidator):
        """Validates if the response is valid code in the specified language."""
        
        def __init__(self, language: str = "python", strict: bool = True):
            super().__init__(strict=strict)
            self.language = language.lower()
        
        # Empty class - no methods implemented yet
    
    # Test: Should fail to instantiate due to missing abstract methods
    with pytest.raises(TypeError, match="abstract method"):
        CodeValidator(language="python", strict=True)


def test_add_name_property_still_fails():
    """Test: After adding name property, should still fail for initial_hint"""
    
    # CodeValidator implementation: Only name property added
    class CodeValidator(BaseValidator):
        """Validates if the response is valid code in the specified language."""
        
        def __init__(self, language: str = "python", strict: bool = True):
            super().__init__(strict=strict)
            self.language = language.lower()
        
        @property
        def name(self) -> str:
            return f"code_{self.language}"
    
    # Test: Should still fail because initial_hint is missing
    with pytest.raises(TypeError, match="abstract method"):
        CodeValidator(language="python", strict=True)


def test_both_properties_allow_instantiation():
    """Test: After adding both properties, instantiation should work if validation methods are provided"""
    
    # CodeValidator implementation: Both properties and validation methods added
    class CodeValidator(BaseValidator):
        """Validates if the response is valid code in the specified language."""
        
        def __init__(self, language: str = "python", strict: bool = True):
            super().__init__(strict=strict)
            self.language = language.lower()
        
        @property
        def name(self) -> str:
            return f"code_{self.language}"

        @property
        def initial_hint(self) -> str:
            return "Please return only valid Python code, with no explanation or extra text."
        
        async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
            return ValidationResult(is_valid=True)
            
        async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
            return ValidationResult(is_valid=True)
    
    # Test: Should now instantiate successfully
    validator = CodeValidator(language="python", strict=True) 
    assert validator.name == "code_python"
    
    validator_js = CodeValidator(language="javascript", strict=False)
    assert validator_js.name == "code_javascript"


def test_initial_hint_property_works():
    """Test: initial_hint property should return appropriate strings"""
    
    # CodeValidator implementation: Same as previous test
    class CodeValidator(BaseValidator):
        """Validates if the response is valid code in the specified language."""
        
        def __init__(self, language: str = "python", strict: bool = True):
            super().__init__(strict=strict)
            self.language = language.lower()
        
        @property
        def name(self) -> str:
            return f"code_{self.language}"

        @property
        def initial_hint(self) -> str:
            return "Please return only valid Python code, with no explanation or extra text."
        
        async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
            return ValidationResult(is_valid=True)
            
        async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
            return ValidationResult(is_valid=True)
    
    # Test initial_hint property
    validator = CodeValidator(language="python", strict=True)
    hint = validator.initial_hint
    assert isinstance(hint, str)
    assert len(hint) > 0
    
    validator_js = CodeValidator(language="javascript", strict=True)
    hint_js = validator_js.initial_hint
    assert isinstance(hint_js, str)
    assert len(hint_js) > 0


@pytest.mark.asyncio
async def test_validate_strict_not_implemented():
    """Test: validate_strict should raise NotImplementedError when not implemented"""
    
    # CodeValidator implementation: Properties but only one validation method
    class CodeValidator(BaseValidator):
        """Validates if the response is valid code in the specified language."""
        
        def __init__(self, language: str = "python", strict: bool = True):
            super().__init__(strict=strict)
            self.language = language.lower()
        
        @property
        def name(self) -> str:
            return f"code_{self.language}"

        @property
        def initial_hint(self) -> str:
            return "Please return only valid Python code, with no explanation or extra text."
        
        # Only implement validate_permissive to test that validate_strict raises NotImplementedError
        async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
            return ValidationResult(is_valid=True)
    
    # Test: Should fail to instantiate because we need both validate_strict and validate_permissive
    with pytest.raises(TypeError, match="Must implement either validate\\(\\) or both validate_strict and validate_permissive"):
        CodeValidator(language="python", strict=True)


@pytest.mark.asyncio
async def test_validate_strict_with_implementation():
    """Test: validate_strict with Python code validation implemented"""
    
    # CodeValidator implementation: validate_strict added
    class CodeValidator(BaseValidator):
        """Validates if the response is valid code in the specified language."""
        
        def __init__(self, language: str = "python", strict: bool = True):
            super().__init__(strict=strict)
            self.language = language.lower()
        
        @property
        def name(self) -> str:
            return f"code_{self.language}"

        @property
        def initial_hint(self) -> str:
            return "Please return only valid Python code, with no explanation or extra text."

        async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
            # Strict: only accept pure code
            if self.language == "python":
                try:
                    ast.parse(response)
                    return ValidationResult(is_valid=True)
                except Exception as e:
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"Code parsing failed: {str(e)}",
                        hint=self.initial_hint
                    )
            else:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Unsupported language: {self.language}",
                    hint=self.initial_hint
                )
        
        async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
            return ValidationResult(is_valid=True)
    
    # Test validate_strict implementation
    validator = CodeValidator(language="python", strict=True)
    
    # Test valid Python code
    valid_codes = ["print('hello')", "x = 1 + 2", "def func(): pass"]
    for code in valid_codes:
        result = await validator.validate_strict(code)
        assert isinstance(result, ValidationResult)
        assert result.is_valid, f"Valid code should pass: {code}"
    
    # Test invalid Python code
    invalid_codes = ["invalid syntax!", "print('unclosed"]
    for code in invalid_codes:
        result = await validator.validate_strict(code)
        assert isinstance(result, ValidationResult)
        assert not result.is_valid, f"Invalid code should fail: {code}"
        assert result.error_message is not None


@pytest.mark.asyncio
async def test_validate_permissive_not_implemented():
    """Test: validate_permissive should raise TypeError when not both methods are implemented"""
    
    # CodeValidator implementation: validate_strict but no validate_permissive
    class CodeValidator(BaseValidator):
        """Validates if the response is valid code in the specified language."""
        
        def __init__(self, language: str = "python", strict: bool = True):
            super().__init__(strict=strict)
            self.language = language.lower()
        
        @property
        def name(self) -> str:
            return f"code_{self.language}"

        @property
        def initial_hint(self) -> str:
            return "Please return only valid Python code, with no explanation or extra text."

        async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
            if self.language == "python":
                try:
                    ast.parse(response)
                    return ValidationResult(is_valid=True)
                except Exception as e:
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"Code parsing failed: {str(e)}",
                        hint=self.initial_hint
                    )
            else:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Unsupported language: {self.language}",
                    hint=self.initial_hint
                )
    
    # Test: Should fail to instantiate because we need both validate_strict and validate_permissive
    with pytest.raises(TypeError, match="Must implement either validate\\(\\) or both validate_strict and validate_permissive"):
        CodeValidator(language="python", strict=False)


@pytest.mark.asyncio
async def test_validate_permissive_with_implementation():
    """Test: validate_permissive with markdown extraction implemented"""
    
    # CodeValidator implementation: Both validation methods
    class CodeValidator(BaseValidator):
        """Validates if the response is valid code in the specified language."""
        
        def __init__(self, language: str = "python", strict: bool = True):
            super().__init__(strict=strict)
            self.language = language.lower()
        
        @property
        def name(self) -> str:
            return f"code_{self.language}"

        @property
        def initial_hint(self) -> str:
            return "Please return only valid Python code, with no explanation or extra text."

        async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
            if self.language == "python":
                try:
                    ast.parse(response)
                    return ValidationResult(is_valid=True)
                except Exception as e:
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"Code parsing failed: {str(e)}",
                        hint=self.initial_hint
                    )
            else:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Unsupported language: {self.language}",
                    hint=self.initial_hint
                )

        async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
            # Forgiving: extract first code block (e.g., from markdown) and validate
            if self.language == "python":
                match = re.search(r'```(?:python)?\n([\s\S]+?)```', response)
                code = match.group(1) if match else response
                try:
                    ast.parse(code)
                    return ValidationResult(is_valid=True)
                except Exception as e:
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"Code parsing failed: {str(e)}",
                        hint=self.initial_hint
                    )
            else:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Unsupported language: {self.language}",
                    hint=self.initial_hint
                )
    
    # Test validate_permissive implementation
    validator = CodeValidator(language="python", strict=False)
    
    # Test markdown with valid code
    result = await validator.validate_permissive("```python\nprint('hello')\n```")
    assert isinstance(result, ValidationResult)
    assert result.is_valid, "Markdown with valid code should pass"
    
    # Test markdown with invalid code
    result = await validator.validate_permissive("```python\ninvalid syntax!\n```")
    assert isinstance(result, ValidationResult)
    assert not result.is_valid, "Markdown with invalid code should fail"
    
    # Test raw valid code (no markdown)
    result = await validator.validate_permissive("print('hello')")
    assert isinstance(result, ValidationResult)
    assert result.is_valid, "Raw valid code should pass in permissive mode"
    
    # Test raw invalid code
    result = await validator.validate_permissive("invalid syntax")
    assert isinstance(result, ValidationResult)
    assert not result.is_valid, "Raw invalid code should fail"


@pytest.mark.asyncio
async def test_unsupported_language_handling():
    """Test: Unsupported languages should be handled gracefully"""
    
    # CodeValidator implementation: Complete implementation
    class CodeValidator(BaseValidator):
        """Validates if the response is valid code in the specified language."""
        
        def __init__(self, language: str = "python", strict: bool = True):
            super().__init__(strict=strict)
            self.language = language.lower()
        
        @property
        def name(self) -> str:
            return f"code_{self.language}"

        @property
        def initial_hint(self) -> str:
            return "Please return only valid Python code, with no explanation or extra text."

        async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
            if self.language == "python":
                try:
                    ast.parse(response)
                    return ValidationResult(is_valid=True)
                except Exception as e:
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"Code parsing failed: {str(e)}",
                        hint=self.initial_hint
                    )
            else:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Unsupported language: {self.language}",
                    hint=self.initial_hint
                )

        async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
            if self.language == "python":
                match = re.search(r'```(?:python)?\n([\s\S]+?)```', response)
                code = match.group(1) if match else response
                try:
                    ast.parse(code)
                    return ValidationResult(is_valid=True)
                except Exception as e:
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"Code parsing failed: {str(e)}",
                        hint=self.initial_hint
                    )
            else:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Unsupported language: {self.language}",
                    hint=self.initial_hint
                )
    
    # Test unsupported language handling
    validator = CodeValidator(language="unsupported_lang", strict=True)
    
    result = await validator.validate_strict("some code")
    assert isinstance(result, ValidationResult)
    assert not result.is_valid, "Unsupported language should fail validation"
    assert result.error_message is not None
    assert "unsupported" in result.error_message.lower()
    
    # Test with permissive mode too
    validator_perm = CodeValidator(language="unsupported_lang", strict=False)
    result = await validator_perm.validate_permissive("some code")
    assert isinstance(result, ValidationResult)
    assert not result.is_valid, "Unsupported language should fail in permissive mode too"


@pytest.mark.asyncio
async def test_comprehensive_functionality_with_functional_validator2():
    """Test: Unsupported languages should be handled gracefully"""
    
    # CodeValidator implementation: Complete implementation
    class CodeValidator(BaseValidator):
        """Validates if the response is valid code in the specified language."""
        
        def __init__(self, language: str = "python", strict: bool = True):
            super().__init__(strict=strict)
            self.language = language.lower()
        
        @property
        def name(self) -> str:
            return f"code_{self.language}"

        @property
        def initial_hint(self) -> str:
            return "Please return only valid Python code, with no explanation or extra text."

        async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
            if self.language == "python":
                try:
                    ast.parse(response)
                    return ValidationResult(is_valid=True)
                except Exception as e:
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"Code parsing failed: {str(e)}",
                        hint=self.initial_hint
                    )
            else:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Unsupported language: {self.language}",
                    hint=self.initial_hint
                )

        async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
            if self.language == "python":
                match = re.search(r'```(?:python)?\n([\s\S]+?)```', response)
                code = match.group(1) if match else response
                try:
                    ast.parse(code)
                    return ValidationResult(is_valid=True)
                except Exception as e:
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"Code parsing failed: {str(e)}",
                        hint=self.initial_hint
                    )
            else:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Unsupported language: {self.language}",
                    hint=self.initial_hint
                )
    
    # Test unsupported language handling
    code_validator = CodeValidator(language="python", strict=True)
    
    # Test cases showing various input/output scenarios as they would come from an LLM

    functional_validator1 = FunctionalValidator([
        ((1, 3), 4),
        ((-1, 3), 2),
    ])

    def my_sum(a, b):
        return a + b

    functional_validator1.validate(my_sum)

    functional_validator = FunctionalValidator([
        (("python", "print('hello world')"), True),
        (("python", "x = 1\ny = 2\nprint(x + y)"), True),
        (("python", "def greet(name):\n    return f'Hello {name}'"), True),
        (("python", "import os\nprint(os.getcwd())"), True),
        (("python", "print('unclosed string"), False),
        (("python", "invalid syntax here!"), False),
        (("python", "x = 1 +"), False),
        (("python", "def func(\n    pass"), False),
    ], code_validator.validate_strict)

    functional_validator.validate_strict(code_validator.validate_strict)

