from typing import Dict, Type
from ..interfaces import ValidationStrategy
from ..config_manager import ConfigManager
from lamia.command_types import CommandType

class ValidationStrategyFactory:
    """Factory for creating validation strategies based on domain type."""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self._strategy_registry: Dict[DomainType, Type[ValidationStrategy]] = {}
        self._strategy_instances: Dict[DomainType, ValidationStrategy] = {}
        self._register_strategies()
    
    def _register_strategies(self):
        """Register available validation strategy implementations."""
        # Import here to avoid circular imports
        from lamia.adapters.llm.strategy import ValidationStrategy as LLMValidationStrategy
        
        self._strategy_registry[CommandType.LLM] = LLMValidationStrategy
        # TODO: Register other strategies as they're implemented
        # self._strategy_registry[DomainType.FILESYSTEM] = FSValidationStrategy
        # self._strategy_registry[DomainType.WEB] = WebValidationStrategy
    
    async def get_strategy(self, domain_type: DomainType) -> ValidationStrategy:
        """Get or create a validation strategy for the specified domain type.
        
        Args:
            domain_type: The domain type to get a strategy for
            
        Returns:
            ValidationStrategy instance for the domain
            
        Raises:
            ValueError: If domain type is not supported
        """

        
        # Return existing instance if available (singleton pattern)
        if domain_type in self._strategy_instances:
            return self._strategy_instances[domain_type]
        
        # Create new instance with proper dependencies
        strategy_class = self._strategy_registry[domain_type]
        
        if domain_type == CommandType.LLM:
            # Create LLM validation strategy with proper dependencies
            strategy = await self._create_llm_validation_strategy(strategy_class)
        else:
            # For other domains, use the config_manager approach
            strategy = strategy_class(self.config_manager)
            await strategy.initialize()
        
        self._strategy_instances[domain_type] = strategy
        return strategy
    
    async def _create_llm_validation_strategy(self, strategy_class):
        """Create LLM validation strategy with proper dependencies."""
        from lamia.adapters.llm.strategy import RetryConfig
        from lamia.validation.validator_registry import ValidatorRegistry
        
        validation_config = self.config_manager.config.get('validation', {})
        retry_config = RetryConfig(
            max_retries=validation_config.get('max_retries'),
            fallback_models=validation_config.get('fallback_models'),
            validators=validation_config.get('validators')
        )
        
        # Use ValidatorRegistry for registry
        ext_folder = self.config_manager.get_extensions_folder()
        validator_registry = ValidatorRegistry(self.config_manager.config, ext_folder)
        registry = await validator_registry.get_registry()
        
        strategy = strategy_class(
            config=retry_config,
            validator_registry=registry
        )
        await strategy.initialize()
        return strategy
    
    async def close_all(self):
        """Close all created strategy instances."""
        for strategy in self._strategy_instances.values():
            await strategy.close()
        self._strategy_instances.clear() 