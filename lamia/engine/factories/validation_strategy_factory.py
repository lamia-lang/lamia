from typing import Dict, Optional, List

from ..config_provider import ConfigProvider
from lamia.command_types import CommandType
from lamia.engine.validation_strategies.llm_validation_strategy import LLMValidationStrategy
from lamia.engine.validation_strategies.fs_validation_strategy import FSValidationStrategy
from lamia.engine.validation_strategies.validation_strategy import ValidationStrategy
from lamia.validation.base import BaseValidator

class ValidationStrategyFactory:
    """Provide (and cache) validation strategies for each supported command type.

    At the moment Lamia only implements an LLM validation strategy, so we avoid the
    premature complexity of a separate *registry* + *instances* split.  A single
    `_strategies` cache is enough to keep the already-constructed strategy
    instances (lazy-loaded on first use).  When new domains need validation we
    can extend `_create_strategy()` – until then YAGNI.
    """

    def __init__(self):
        # Cache of already constructed strategies (lazy singleton per CommandType)
        self._strategies: Dict[CommandType, ValidationStrategy] = {}

    async def get_strategy(self, command_type: CommandType, validators: List[BaseValidator]) -> ValidationStrategy:
        """Return a validation strategy for *command_type* (cached after first build)."""

        # Fast path: return cached instance if we have it
        if command_type in self._strategies:
            return self._strategies[command_type]

        # Otherwise build, cache and return
        strategy = await self._create_strategy(command_type, validators)
        self._strategies[command_type] = strategy
        return strategy

    async def _create_strategy(self, command_type: CommandType, validators: Optional[List[BaseValidator]] = None) -> ValidationStrategy:
        """Instantiate the appropriate validation strategy for *command_type*."""

        if command_type == CommandType.LLM:
            return LLMValidationStrategy(validators)
        elif command_type == CommandType.FILESYSTEM:
            return FSValidationStrategy(validators)
        elif command_type == CommandType.WEB:
            return ValidationStrategy(validators) 

        raise ValueError(f"No validation strategy implemented for command type: {command_type}")