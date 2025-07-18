from ..managers import ValidationStrategy
from lamia.validation.base import BaseValidator
from typing import Type

class LLMValidationStrategy(ValidationStrategy):
    """Handles LLM validation logic."""

    def _create_validator(self, validator_type: Type[BaseValidator]) -> BaseValidator:
        """Create a validator instance with hints enabled."""
        return validator_type(generate_hints=True)

    def get_initial_hints(self) -> str:
        """Get combined initial hints from all validators."""
        hints = [v.initial_hint for v in self.validators if hasattr(v, 'initial_hint')]
        return "\n".join(hints) 