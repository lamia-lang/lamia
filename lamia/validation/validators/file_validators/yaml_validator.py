from ...base import BaseValidator, ValidationResult
from .file_structure.yaml_structure_validator import YAMLStructureValidator

class YAMLValidator(BaseValidator):
    """Validates if the response is valid YAML (well-formed, not structure-checked)."""
    def __init__(self, strict: bool = True, generate_hints: bool = False):
        super().__init__(strict=strict, generate_hints=generate_hints)
        self._delegate = YAMLStructureValidator(model=None, strict=strict, generate_hints=generate_hints)

    @classmethod
    def name(cls) -> str:
        return "yaml"

    @property
    def initial_hint(self) -> str:
        return self._delegate.initial_hint

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        return await self._delegate.validate_strict(response, **kwargs)

    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        return await self._delegate.validate_permissive(response, **kwargs) 