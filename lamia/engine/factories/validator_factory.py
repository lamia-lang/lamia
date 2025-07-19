from typing import Type

from lamia.command_types import CommandType
from lamia.validation.base import BaseValidator
from lamia.types import BaseType
from lamia.type_converter import create_validator

class ValidatorFactory:
    """Provide validation strategies for each supported command type."""

    def get_validator(self, command_type: CommandType, return_type: Type[BaseType] = None) -> BaseValidator:
        """Return a validator for the given *command_type* and *return_type*."""      

        if command_type == CommandType.LLM:
            return create_validator(return_type, generate_hints=True)
        else:
            return create_validator(return_type)

