from typing import Dict

from ..managers import ValidationStrategy
from ..config_provider import ConfigProvider
from lamia.command_types import CommandType
from lamia.engine.validation_strategies.llm_validation_strategy import LLMValidationStrategy
from lamia.engine.validation_strategies.fs_validation_strategy import FSValidationStrategy
from lamia.validation.validator_registry import ValidatorRegistry

class ValidationStrategyFactory:
    """Provide (and cache) validation strategies for each supported command type.

    At the moment Lamia only implements an LLM validation strategy, so we avoid the
    premature complexity of a separate *registry* + *instances* split.  A single
    `_strategies` cache is enough to keep the already-constructed strategy
    instances (lazy-loaded on first use).  When new domains need validation we
    can extend `_create_strategy()` – until then YAGNI.
    """

    def __init__(self, config_provider: ConfigProvider):
        self.config_provider = config_provider
        # Cache of already constructed strategies (lazy singleton per CommandType)
        self._strategies: Dict[CommandType, ValidationStrategy] = {}

    async def get_strategy(self, command_type: CommandType) -> ValidationStrategy:
        """Return a validation strategy for *command_type* (cached after first build)."""

        # Fast path: return cached instance if we have it
        if command_type in self._strategies:
            return self._strategies[command_type]

        # Otherwise build, cache and return
        strategy = await self._create_strategy(command_type)
        self._strategies[command_type] = strategy
        return strategy

    async def _create_strategy(self, command_type: CommandType) -> ValidationStrategy:
        """Instantiate the appropriate validation strategy for *command_type*."""

        # Build validator registry (allows project / user extensions)
        ext_folder = self.config_provider.get_extensions_folder()
        registry = await ValidatorRegistry(self.config_provider.config, ext_folder).get_registry()

        if command_type == CommandType.LLM:
            return LLMValidationStrategy(registry)
        elif command_type == CommandType.FILESYSTEM:
            return FSValidationStrategy(registry)
        elif command_type == CommandType.WEB:
            return ValidationStrategy(registry)

        raise ValueError(f"No validation strategy implemented for command type: {command_type}")