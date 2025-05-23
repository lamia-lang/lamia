from typing import Optional
from ..base import BaseValidator, ValidationResult

class LengthValidator(BaseValidator):
    """Validates the response length."""
    def __init__(self, min_length: Optional[int] = None, max_length: Optional[int] = None, strict: bool = True):
        super().__init__(strict=strict)
        self.min_length = min_length
        self.max_length = max_length

    @property
    def initial_hint(self) -> str:
        parts = []
        if self.min_length:
            parts.append(f"at least {self.min_length} characters long")
        if self.max_length:
            parts.append(f"no more than {self.max_length} characters long")
        if parts:
            return f"Please ensure the response is {' and '.join(parts)}, with no explanation or extra text."
        return "Please ensure the response meets the required length constraints, with no explanation or extra text."

    @classmethod
    def name(cls) -> str:
        return "length"

    async def validate(self, response: str, **kwargs) -> ValidationResult:
        length = len(response)
        if self.min_length and length < self.min_length:
            return ValidationResult(
                is_valid=False,
                error_message=f"Response too short: {length} < {self.min_length}",
                hint=f"Please ensure the response is at least {self.min_length} characters long."
            )
        if self.max_length and length > self.max_length:
            return ValidationResult(
                is_valid=False,
                error_message=f"Response too long: {length} > {self.max_length}",
                hint=f"Please ensure the response is no more than {self.max_length} characters long."
            )
        return ValidationResult(is_valid=True)

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        length = len(response)
        if self.min_length and length < self.min_length:
            return ValidationResult(
                is_valid=False,
                error_message=f"Response too short: {length} < {self.min_length}",
                hint=self.initial_hint
            )
        if self.max_length and length > self.max_length:
            return ValidationResult(
                is_valid=False,
                error_message=f"Response too long: {length} > {self.max_length}",
                hint=self.initial_hint
            )
        return ValidationResult(is_valid=True)

    async def validate_restrictive(self, response: str, **kwargs) -> ValidationResult:
        length = len(response)
        if self.min_length and length < self.min_length:
            return ValidationResult(
                is_valid=False,
                error_message=f"Response too short: {length} < {self.min_length}",
                hint=self.initial_hint
            )
        if self.max_length and length > self.max_length:
            return ValidationResult(
                is_valid=False,
                error_message=f"Response too long: {length} > {self.max_length}",
                hint=self.initial_hint
            )
        return ValidationResult(is_valid=True, validated_text=response) 