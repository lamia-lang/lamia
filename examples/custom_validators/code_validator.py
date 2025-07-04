from typing import Optional, Dict, Any
import ast

from lamia.validation.base import BaseValidator, ValidationResult

class CodeValidator(BaseValidator):
    """Validates if the response is valid code in the specified language."""
    
    def __init__(self, language: str = "python", strict: bool = True, generate_hints: bool = False):
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
        # Forgiving: extract first code block (e.g., from markdown) and validate
        import re
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