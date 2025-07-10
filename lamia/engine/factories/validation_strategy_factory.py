from typing import Dict, Any

from ..interfaces import ValidationStrategy
from ..config_manager import ConfigManager
from lamia.command_types import CommandType


class ValidationStrategyFactory:
    """Provide (and cache) validation strategies for each supported command type.

    At the moment Lamia only implements an LLM validation strategy, so we avoid the
    premature complexity of a separate *registry* + *instances* split.  A single
    `_strategies` cache is enough to keep the already-constructed strategy
    instances (lazy-loaded on first use).  When new domains need validation we
    can extend `_create_strategy()` – until then YAGNI.
    """

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
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

        if command_type == CommandType.LLM:
            return await self._create_llm_validation_strategy()

        raise ValueError(f"No validation strategy implemented for command type: {command_type}")

    async def _create_llm_validation_strategy(self) -> ValidationStrategy:
        """Build the LLM validation strategy with its dependencies."""

        from lamia.adapters.llm.llm_validation_strategy import ValidationStrategy as LLMValidationStrategy, RetryConfig
        from lamia.validation.validator_registry import ValidatorRegistry

        # Fetch validation-specific configuration
        validation_cfg: Dict[str, Any] = self.config_manager.get_validation_config()

        retry_config = RetryConfig(
            max_retries=validation_cfg.get("max_retries", 1),
            fallback_models=validation_cfg.get("fallback_models"),
            validators=validation_cfg.get("validators"),
        )

        # Build validator registry (allows project / user extensions)
        ext_folder = self.config_manager.get_extensions_folder()
        registry = await ValidatorRegistry(self.config_manager.config, ext_folder).get_registry()

        strategy = LLMValidationStrategy(
            config=retry_config,
            validator_registry=registry,
        )

        # Some strategies might expose async initialise hooks – call if present.
        initialise = getattr(strategy, "initialize", None)
        if callable(initialise):
            await initialise()

        return strategy