from typing import Type, Optional

from lamia.command_types import CommandType
from lamia.validation.base import BaseValidator
from lamia.types import BaseType
from lamia.type_converter import create_validator
from lamia.engine.validation_manager import ValidationManager

class ValidatorFactory:
    """Provide validation strategies for each supported command type."""

    def get_validator(self, command_type: CommandType, return_type: Type[BaseType] = None, validation_manager: Optional[ValidationManager] = None) -> BaseValidator:
        """Return a validator for the given *command_type* and *return_type*.
        
        Args:
            command_type: The type of command being validated
            return_type: The expected return type
            validation_manager: Optional validation manager for intermediate tracking
        """

        if command_type == CommandType.LLM:
            validator = create_validator(return_type, generate_hints=True)
        else:
            validator = create_validator(return_type)
        
        validator.validation_manager = validation_manager
        
        return validator

