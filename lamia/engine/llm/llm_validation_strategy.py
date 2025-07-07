import asyncio
from typing import Any
import logging

from ..interfaces import ValidationStrategy, Manager, DomainType
from ..config_manager import ConfigManager
from lamia.adapters.llm.base import LLMResponse
from lamia.validation.base import ValidationResult
from lamia.validation.validator_registry import ValidatorRegistry

logger = logging.getLogger(__name__)

class LLMValidationStrategy(ValidationStrategy):
    """LLM-specific validation strategy implementation."""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self._strategy = None
        self._initialized = False
    
    @property
    def domain_type(self) -> DomainType:
        """Return the domain type this strategy validates."""
        return DomainType.LLM
    
    async def validate(self, manager: Manager, content: str, **kwargs) -> LLMResponse:
        """Validate LLM content using the existing validation strategy.
        
        Args:
            manager: The LLM manager to use
            content: The prompt to validate
            **kwargs: LLM generation parameters
            
        Returns:
            Validated LLMResponse
        """
        if not self._initialized:
            raise RuntimeError("LLM validation strategy not initialized")
        
        if manager.domain_type != DomainType.LLM:
            raise ValueError(f"Expected LLM manager, got {manager.domain_type}")
        
        # Get the primary adapter through the manager
        primary_adapter = await manager._get_primary_adapter()
        
        # Use the existing validation strategy
        return await self._strategy.execute_with_retries(
            primary_adapter=primary_adapter,
            prompt=content,
            create_adapter_fn=lambda model: manager.create_adapter_from_config(override_model=model),
            **kwargs
        )
    
    async def initialize(self) -> None:
        """Initialize the LLM validation strategy."""
        if self._initialized:
            return
            
        validation_config = self.config_manager.config.get('validation', {})
        if not validation_config.get('enabled', False):
            logger.info("LLM validation disabled")
            return
        
        # Import here to avoid circular imports
        from lamia.adapters.llm.strategy import ValidationStrategy as LLMStrategy, RetryConfig
        
        retry_config = RetryConfig(
            max_retries=validation_config.get('max_retries'),
            fallback_models=validation_config.get('fallback_models'),
            validators=validation_config.get('validators')
        )
        
        # Use ValidatorRegistry for registry
        ext_folder = self.config_manager.get_extensions_folder()
        validator_registry = ValidatorRegistry(self.config_manager.config, ext_folder)
        registry = await validator_registry.get_registry()
        
        self._strategy = LLMStrategy(
            config=retry_config,
            validator_registry=registry
        )
        
        self._initialized = True
        logger.info("LLM validation strategy initialized")
    
    async def close(self) -> None:
        """Close and cleanup validation strategy resources."""
        self._strategy = None
        self._initialized = False
        logger.info("LLM validation strategy closed") 