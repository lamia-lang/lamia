from typing import Dict, Optional, List, Type

from ..config_provider import ConfigProvider
from lamia.command_types import CommandType
from lamia.engine.validation_strategies.llm_validation_strategy import LLMValidationStrategy
from lamia.engine.validation_strategies.fs_validation_strategy import FSValidationStrategy
from lamia.engine.validation_strategies.validation_strategy import ValidationStrategy
from lamia.validation.base import BaseValidator
from lamia.types import BaseType
from lamia.type_converter import type_converter

class ValidationStrategyFactory:
    """Provide (and cache) validation strategies for each supported command type.
    """

    def __init__(self):
        # Cache of already constructed strategies (lazy singleton per CommandType)
        self._strategies: Dict[CommandType, ValidationStrategy] = {}

    async def get_strategy(self, command_type: CommandType, return_type: Type[BaseType] = None) -> ValidationStrategy:
        """Return a validation strategy for *command_type* (cached after first build)."""

        # Fast path: return cached instance if we have it
        if command_type in self._strategies:
            return self._strategies[command_type]

        # Otherwise build, cache and return
        strategy = await self._create_strategy(command_type, return_type)
        self._strategies[command_type] = strategy
        return strategy

    async def _create_strategy(self, command_type: CommandType, return_type: Type[BaseType] = None) -> ValidationStrategy:
        """Instantiate the appropriate validation strategy for *command_type*."""

        if return_type is None:
            validator_type = None

        validator_type = type_converter.get_validator_type(return_type)

        if command_type == CommandType.LLM:
            return LLMValidationStrategy(validator_type)
        elif command_type == CommandType.FILESYSTEM:
            return FSValidationStrategy(validator_type)
        elif command_type == CommandType.WEB:
            return ValidationStrategy(validator_type) 

        raise ValueError(f"No validation strategy implemented for command type: {command_type}")