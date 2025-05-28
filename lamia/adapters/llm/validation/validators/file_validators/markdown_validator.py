from ...base import BaseValidator, ValidationResult
from .file_structure.markdown_structure_validator import MarkdownStructureValidator

class MarkdownValidator(BaseValidator):
    """Validates if the response is valid Markdown (well-formed, not structure-checked)."""
    def __init__(self, strict: bool = True):
        super().__init__(strict=strict)
        self._delegate = MarkdownStructureValidator(model=None, strict=strict)

    @classmethod
    def name(cls) -> str:
        return "markdown"

    @property
    def initial_hint(self) -> str:
        return self._delegate.initial_hint

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        return await self._delegate.validate_strict(response, **kwargs)

    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        return await self._delegate.validate_permissive(response, **kwargs) 