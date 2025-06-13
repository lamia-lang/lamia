from ...base import BaseValidator, ValidationResult
from .file_structure.json_structure_validator import JSONStructureValidator

class JSONValidator(BaseValidator):
    """Validates if the response is valid JSON (well-formed, not structure-checked)."""
    def __init__(self, strict: bool = True):
        super().__init__(strict=strict)
        self._delegate = JSONStructureValidator(model=None, strict=strict)

    @classmethod
    def name(cls) -> str:
        return "json"

    @property
    def initial_hint(self) -> str:
        return self._delegate.initial_hint

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        result = await self._delegate.validate_strict(response, **kwargs)
        result.raw_text = response
        return result

    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        result = await self._delegate.validate_permissive(response, **kwargs)
        result.raw_text = response
        return result 