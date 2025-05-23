import re
from ..base import BaseValidator, ValidationResult

class RegexValidator(BaseValidator):
    """Validates if the response matches a regex pattern."""
    def __init__(self, pattern: str, strict: bool = True):
        super().__init__(strict=strict)
        self.pattern = re.compile(pattern)

    @property
    def initial_hint(self) -> str:
        return f"Please ensure the response matches the required pattern: {self.pattern.pattern}, with no explanation or extra text."

    @classmethod
    def name(cls) -> str:
        return "regex"

    async def validate(self, response: str, **kwargs) -> ValidationResult:
        if self.pattern.search(response):
            return ValidationResult(is_valid=True)
        return ValidationResult(
            is_valid=False,
            error_message=f"Response does not match pattern: {self.pattern.pattern}",
            hint=f"Please ensure the response matches the required pattern: {self.pattern.pattern}"
        )

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        if self.pattern.fullmatch(response.strip()):
            return ValidationResult(is_valid=True)
        return ValidationResult(
            is_valid=False,
            error_message=f"Response does not exactly match pattern: {self.pattern.pattern}",
            hint=self.initial_hint
        )

    async def validate_restrictive(self, response: str, **kwargs) -> ValidationResult:
        match = self.pattern.search(response)
        if match:
            return ValidationResult(is_valid=True, validated_text=match.group(0))
        return ValidationResult(
            is_valid=False,
            error_message=f"Response does not contain a match for pattern: {self.pattern.pattern}",
            hint=self.initial_hint
        ) 