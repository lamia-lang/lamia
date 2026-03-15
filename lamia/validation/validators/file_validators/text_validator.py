"""Pass-through validator for raw text (str / TEXT / TXT).

Always succeeds — the LLM response is returned as-is with only
markdown code-fence stripping applied.
"""

from ...base import BaseValidator, ValidationResult


class TextValidator(BaseValidator):
    """No-op validator that accepts any text."""

    def __init__(self, strict: bool = True, generate_hints: bool = False):
        super().__init__(strict=strict, generate_hints=generate_hints)

    @property
    def name(self) -> str:
        return "text"

    @property
    def initial_hint(self) -> str:
        return "Return plain text."

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        text = self.strip_markdown_fences(response.strip())
        return ValidationResult(
            is_valid=True,
            validated_text=text,
            typed_result=text,
        )

    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        text = self.strip_markdown_fences(response.strip())
        return ValidationResult(
            is_valid=True,
            validated_text=text,
            typed_result=text,
        )