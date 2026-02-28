from ...base import BaseValidator, ValidationResult
from .file_structure.html_structure_validator import HTMLStructureValidator

class HTMLValidator(BaseValidator):
    """Validates if the response is valid HTML (well-formed, not structure-checked)."""
    def __init__(self, strict: bool = True, generate_hints: bool = False):
        super().__init__(strict=strict, generate_hints=generate_hints)
        self._delegate = HTMLStructureValidator(model=None, strict=strict, generate_hints=generate_hints)

    @classmethod
    def name(cls) -> str:
        return "html"

    def prepare_content_for_write(self, existing_content: str, new_content: str) -> str:
        return self._delegate.prepare_content_for_write(existing_content, new_content)

    @property
    def initial_hint(self) -> str:
        return self._delegate.initial_hint

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        return await self._delegate.validate_strict(response, **kwargs)

    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        return await self._delegate.validate_permissive(response, **kwargs) 