import re
from ..base import BaseValidator, ValidationResult

class AtomicTypeValidator(BaseValidator):
    """Validates if the response matches a specified atomic type (e.g., integer, float, bool, string)."""
    def __init__(self, atomic_type: str, strict: bool = True):
        super().__init__(strict=strict)
        self.atomic_type = atomic_type.lower()
        self._type_map = {
            'int': int,
            'integer': int,
            'float': float,
            'bool': lambda x: x.lower() in ['true', 'false', '1', '0'],
            'str': str,
            'string': str,
        }

    @property
    def initial_hint(self) -> str:
        return f"Please ensure the response is a valid {self.atomic_type}, with no explanation or extra text."

    def _validate_type(self, response: str):
        t = self._type_map.get(self.atomic_type)
        if t is None:
            raise ValueError(f"Unsupported type for AtomicTypeValidator: {self.atomic_type}")
        if self.atomic_type in ['bool']:
            return response.strip().lower() in ['true', 'false', '1', '0']
        if self.atomic_type in ['str', 'string']:
            return True  # Any string is valid
        try:
            t(response.strip())
            return True
        except Exception:
            return False

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        valid = self._validate_type(response)
        if valid:
            return ValidationResult(is_valid=True)
        return ValidationResult(
            is_valid=False,
            error_message=f"Response is not a valid {self.atomic_type}.",
            hint=self.initial_hint
        )

    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        t = self._type_map.get(self.atomic_type)
        if t is None:
            return ValidationResult(
                is_valid=False,
                error_message=f"Unsupported type: {self.atomic_type}",
                hint=self.initial_hint
            )
        if self.atomic_type in ['int', 'integer']:
            matches = re.findall(r'-?\d+', response)
            if len(matches) == 1:
                return ValidationResult(is_valid=True, validated_text=matches[0])
            elif len(matches) > 1:
                return ValidationResult(
                    is_valid=False,
                    error_message="Response contains more than one integer value.",
                    hint=self.initial_hint
                )
        elif self.atomic_type == 'float':
            matches = re.findall(r'-?\d+(\.\d+)?', response)
            float_matches = [m[0] if isinstance(m, tuple) else m for m in matches if '.' in (m[0] if isinstance(m, tuple) else m)]
            if len(matches) == 1:
                return ValidationResult(is_valid=True, validated_text=matches[0][0] if isinstance(matches[0], tuple) else matches[0])
            elif len(matches) > 1:
                return ValidationResult(
                    is_valid=False,
                    error_message="Response contains more than one float value.",
                    hint=self.initial_hint
                )
        elif self.atomic_type == 'bool':
            matches = re.findall(r'\b(true|false|1|0)\b', response, re.IGNORECASE)
            if len(matches) == 1:
                return ValidationResult(is_valid=True, validated_text=matches[0])
            elif len(matches) > 1:
                return ValidationResult(
                    is_valid=False,
                    error_message="Response contains more than one boolean value.",
                    hint=self.initial_hint
                )
        elif self.atomic_type in ['str', 'string']:
            if response.strip():
                return ValidationResult(is_valid=True, validated_text=response.strip())
        return ValidationResult(
            is_valid=False,
            error_message=f"Response does not contain a valid {self.atomic_type}.",
            hint=self.initial_hint
        )

    @classmethod
    def name(cls) -> str:
        return "atomic_type" 