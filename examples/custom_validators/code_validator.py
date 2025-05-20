from typing import Optional, Dict, Any
import ast

from lamia.adapters.llm.validation.base import BaseValidator, ValidationResult

class CodeValidator(BaseValidator):
    """Validates if the response is valid code in the specified language."""
    
    def __init__(self, language: str = "python", strict: bool = True):
        """Initialize the code validator.
        
        Args:
            language: Programming language to validate ("python" supported for now)
            strict: Whether to perform strict validation
        """
        self.language = language.lower()
        self.strict = strict
    
    @property
    def name(self) -> str:
        return f"code_{self.language}"

    async def validate(self, response: str, **kwargs) -> ValidationResult:
        """Validate if the response is valid code."""
        if self.language == "python":
            return await self._validate_python(response)
        else:
            return ValidationResult(
                is_valid=False,
                error_message=f"Unsupported language: {self.language}"
            )
    
    async def _validate_python(self, code: str) -> ValidationResult:
        """Validate Python code."""
        try:
            # Try parsing the code
            ast.parse(code)
            
            if self.strict:
                # Additional checks in strict mode
                if "import" not in code and "def" not in code:
                    return ValidationResult(
                        is_valid=False,
                        error_message="Strict mode: Code should contain functions or imports",
                        validation_data={"code": code}
                    )
            
            return ValidationResult(is_valid=True)
            
        except SyntaxError as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Python syntax error: {str(e)}",
                validation_data={
                    "error_type": "syntax",
                    "line": e.lineno,
                    "offset": e.offset,
                    "code": code
                }
            )
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Validation error: {str(e)}",
                validation_data={"code": code}
            ) 