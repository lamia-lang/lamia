import asyncio
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from lamia.validation.base import ValidationResult

from .config_manager import ConfigManager
from lamia.validation.validator_registry import ValidatorRegistry

logger = logging.getLogger(__name__)

@dataclass
class ValidationStats:
    """Statistics about validation operations."""
    total_validations: int = 0
    successful_validations: int = 0
    failed_validations: int = 0
    avg_execution_time_ms: float = 0.0
    by_validator_type: Dict[str, int] = field(default_factory=dict)

class ValidationManager:
    """Manages validation across all domains and tracks statistics."""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.enabled = self._is_validation_enabled()
        self.stats = ValidationStats()
        self.recent_results: List[ValidationResult] = []
        self.max_recent_results = 100  # Keep last 100 results
        
        # Initialize domain-specific components
        self._llm_strategy = None
        # TODO: Add other domain strategies
        # self._fs_strategy = None
        # self._web_strategy = None
        
    def _is_validation_enabled(self) -> bool:
        """Check if validation is enabled in config."""
        validation_config = self.config_manager.config.get('validation', {})
        return validation_config.get('enabled', False)
    
    async def initialize(self):
        """Initialize validation components if enabled."""
        if not self.enabled:
            logger.info("Validation disabled")
            return
            
        # Initialize LLM validation strategy
        await self._initialize_llm_strategy()
        
        logger.info("ValidationManager initialized")
    
    async def _initialize_llm_strategy(self):
        """Initialize LLM-specific validation strategy."""
        from lamia.adapters.llm.strategy import ValidationStrategy, RetryConfig
        
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
        
        self._llm_strategy = ValidationStrategy(
            config=retry_config,
            validator_registry=registry
        )
    
    async def validate_llm_response(self, llm_manager, prompt: str, **kwargs) -> Any:
        """Validate LLM response using domain-specific strategy."""
        if not self.enabled or not self._llm_strategy:
            # If validation disabled, use llm_manager directly  
            return await llm_manager.generate(prompt, **kwargs)
        
        # Get primary adapter through llm_manager (proper encapsulation)
        primary_adapter = await llm_manager._get_primary_adapter()

        validation_result = await self._llm_strategy.execute_with_retries(
            primary_adapter=primary_adapter,
            prompt=prompt,
            create_adapter_fn=lambda model: llm_manager.create_adapter_from_config(override_model=model),
            **kwargs
        )
        self._record_validation_result(validation_result)
        
        return validation_result

    
    def _record_validation_result(self, result: ValidationResult):
        """Record validation result and update statistics."""
        # Add to recent results
        self.recent_results.append(result)
        if len(self.recent_results) > self.max_recent_results:
            self.recent_results.pop(0)
        
        # Update statistics
        self.stats.total_validations += 1
        
        if result.success:
            self.stats.successful_validations += 1
        else:
            self.stats.failed_validations += 1
        
        # Update averages
        if self.stats.total_validations > 0:
            total_time = (self.stats.avg_execution_time_ms * (self.stats.total_validations - 1) + 
                         result.execution_time_ms)
            self.stats.avg_execution_time_ms = total_time / self.stats.total_validations
        
        # Update by-domain stats
        domain_count = self.stats.by_domain.get(result.domain, 0)
        self.stats.by_domain[result.domain] = domain_count + 1
        
        # Update by-validator-type stats
        validator_count = self.stats.by_validator_type.get(result.validator_type, 0)
        self.stats.by_validator_type[result.validator_type] = validator_count + 1
    
    def get_validation_stats(self) -> ValidationStats:
        """Get current validation statistics."""
        return self.stats
    
    def get_recent_results(self, limit: Optional[int] = None) -> List[ValidationResult]:
        """Get recent validation results."""
        if limit is None:
            return self.recent_results.copy()
        return self.recent_results[-limit:]
    
    async def close(self):
        """Cleanup validation manager resources."""
        # TODO: Cleanup strategies if needed
        logger.info("ValidationManager closed") 