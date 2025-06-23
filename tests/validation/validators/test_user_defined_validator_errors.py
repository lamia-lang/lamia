import pytest
import asyncio
import ast
import re
from lamia.validation.validators.functional_validator import FunctionalValidator
from lamia.validation.base import BaseValidator, ValidationResult


def test_empty_class_fails():
    """Test: Empty class should fail during instantiation due to abstract methods"""
    
    # CodeValidator implementation: Empty class
    class CodeValidator(BaseValidator):
        """Validates if the response is valid code in the specified language."""
        
        def __init__(self, language: str = "python", strict: bool = True):
            super().__init__(strict=strict)
            self.language = language.lower()
        
        # Empty class - no methods implemented yet
    
    with pytest.raises(TypeError, match="abstract method"):
        CodeValidator(language="python", strict=True)

def test_class_without_name_property_fails():
    class CodeValidator(BaseValidator):
        """Validates if the response is valid code in the specified language."""
        
        def __init__(self, language: str = "python", strict: bool = True):
            super().__init__(strict=strict)
            self.language = language.lower()
        
        @property
        def initial_hint(self) -> str:
            return f"Please return only valid {self.language} code, with no explanation or extra text."
        
        async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
            return ValidationResult(is_valid=True)
            
        async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
            return ValidationResult(is_valid=True)
    
    with pytest.raises(TypeError, match="abstract method"):
        CodeValidator(language="python", strict=True)


def test_class_without_initial_hint_property_fails():
    class CodeValidator(BaseValidator):
        """Validates if the response is valid code in the specified language."""
        
        def __init__(self, language: str = "python", strict: bool = True):
            super().__init__(strict=strict)
            self.language = language.lower()
        
        @property
        def name(self) -> str:
            return f"code_{self.language}"
        
        async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
            return ValidationResult(is_valid=True)
            
        async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
            return ValidationResult(is_valid=True)
    
    with pytest.raises(TypeError, match="abstract method"):
        CodeValidator(language="python", strict=True)

def test_without_validate_strict_fails():
    """Test: After adding both properties, instantiation should work if validation methods are provided"""
    
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
            return f"Please return only valid {self.language} code, with no explanation or extra text."
            
        async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
            return ValidationResult(is_valid=True)
    
    with pytest.raises(TypeError, match="Must implement either validate\\(\\) or both validate_strict and validate_permissive\\."):
        CodeValidator(language="python", strict=True)

def test_without_validate_permissive_fails():
    """Test: After adding both properties, instantiation should work if validation methods are provided"""
    
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
            return f"Please return only valid {self.language} code, with no explanation or extra text."

        async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
            return ValidationResult(is_valid=True)

    with pytest.raises(TypeError, match="Must implement either validate\\(\\) or both validate_strict and validate_permissive\\."):
        CodeValidator(language="python", strict=True)

def test_with_validate_permissive_and_validate_strict_succeeds():
    """Test: After adding both properties, instantiation should work if validation methods are provided"""
    
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
            return f"Please return only valid {self.language} code, with no explanation or extra text."
        
        async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
            return ValidationResult(is_valid=True)
            
        async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
            return ValidationResult(is_valid=True)
        
        async def validate(self, response: str, **kwargs) -> ValidationResult:
            return ValidationResult(is_valid=True)
    
    with pytest.raises(TypeError, match="Implement either validate\\(\\) OR validate_strict/validate_permissive, not both\\."):
        CodeValidator(language="python", strict=True)

def test_must_have_either_validate_permissive_and_validate_strict_or_validate():
    """Test: After adding both properties, instantiation should work if validation methods are provided"""
    
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
            return f"Please return only valid {self.language} code, with no explanation or extra text."
        
        async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
            return ValidationResult(is_valid=True)
            
        async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
            return ValidationResult(is_valid=True)
        
        async def validate(self, response: str, **kwargs) -> ValidationResult:
            return ValidationResult(is_valid=True)
        
    with pytest.raises(TypeError, match="Implement either validate\\(\\) OR validate_strict/validate_permissive, not both\\."):
        CodeValidator(language="python", strict=True)

def test_with_overidden_validate_succeeds():
    """Test: After adding both properties, instantiation should work if validation methods are provided"""
    
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
            return f"Please return only valid {self.language} code, with no explanation or extra text."
        
        async def validate(self, response: str, **kwargs) -> ValidationResult:
            return ValidationResult(is_valid=True)
    
    # Test: Should now instantiate successfully
    validator = CodeValidator(language="python", strict=True) 
    assert validator.name == "code_python"

@pytest.mark.asyncio
async def test_correct_code_validator_impl_with_functional_validator():
    """Test: Unsupported languages should be handled gracefully"""
    
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

    assert code_validator.initial_hint == "Please return only valid Python code, with no explanation or extra text."

    functional_validator = FunctionalValidator([
        (("python", "print('hello world')"), True),
        (("python", "def greet(name):\n    return f'Hello {name}'"), True),
        (("python", "invalid syntax here!"), False),
        (("python", "x = 1 +"), False),
        (("python", "def func(\n    pass"), False),
    ], code_validator.validate_strict)

    await functional_validator.validate_strict(code_validator.validate_strict)

