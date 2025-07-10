import asyncio
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime
from dataclasses import dataclass, field
from lamia.engine.interfaces.manager import Manager
from lamia.engine.interfaces.command import CommandType
from .factories import ValidationStrategyFactory
from lamia.validation.base import ValidationResult

logger = logging.getLogger(__name__)

@dataclass
class ValidationStats:
    """Statistics about validation operations across all domains."""
    total_validations: int = 0
    successful_validations: int = 0
    failed_validations: int = 0
    avg_execution_time_ms: float = 0.0
    by_domain: Dict[CommandType, int] = field(default_factory=dict)
    by_validator_type: Dict[str, int] = field(default_factory=dict)

class ValidationManager:
    """Manages validation across all domains and tracks centralized statistics."""
    
    def __init__(self, validation_factory: ValidationStrategyFactory):
        self.validation_factory = validation_factory
        
        # Centralized statistics tracking
        self.stats = ValidationStats()
        self.recent_results: List[ValidationResult] = []
        self.max_recent_results = 100  # Keep last 100 results
    
    async def validate(self, command_type: CommandType, manager: Manager, content: str, **kwargs) -> Any:
        """Coordinate validation using the appropriate domain strategy.
        
        Args:
            manager: The domain manager to use
            content: The content to validate
            **kwargs: Domain-specific parameters
            
        Returns:
            Validated response from the domain
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Get the appropriate validation strategy
            strategy = await self.validation_factory.get_strategy(command_type)
            
            # Execute validation
            result = await strategy.validate(manager, content, **kwargs)
            
            # Record successful validation
            execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
            validation_result = ValidationResult(
                is_valid=True,
                validated_text=getattr(result, 'text', str(result))
            )
            self._record_validation_result(validation_result, execution_time)
            
            return result
            
        except ValueError as e:
            # Strategy not found for this domain - use manager directly
            logger.debug(f"No validation strategy for {domain_type}, using manager directly")
            return await manager.execute(content, **kwargs)
            
        except Exception as e:
            # Record failed validation
            execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
            validation_result = ValidationResult(
                is_valid=False,
                error_message=str(e)
            )
            self._record_validation_result(validation_result, domain_type, execution_time)
            raise
    
    def _record_validation_result(self, result: ValidationResult, domain_type: DomainType, execution_time_ms: float):
        """Record validation result and update centralized statistics."""
        # Add to recent results
        self.recent_results.append(result)
        if len(self.recent_results) > self.max_recent_results:
            self.recent_results.pop(0)
        
        # Update statistics
        self.stats.total_validations += 1
        
        if result.is_valid:
            self.stats.successful_validations += 1
        else:
            self.stats.failed_validations += 1
        
        # Update execution time averages
        if self.stats.total_validations > 0:
            total_time = (self.stats.avg_execution_time_ms * (self.stats.total_validations - 1) + 
                         execution_time_ms)
            self.stats.avg_execution_time_ms = total_time / self.stats.total_validations
        
        # Update by-domain stats
        domain_count = self.stats.by_domain.get(domain_type, 0)
        self.stats.by_domain[domain_type] = domain_count + 1
        
        # Update by-validator-type stats
        validator_type = f"{domain_type.value}_validation"
        validator_count = self.stats.by_validator_type.get(validator_type, 0)
        self.stats.by_validator_type[validator_type] = validator_count + 1
    
    def get_validation_stats(self) -> ValidationStats:
        """Get current validation statistics."""
        return self.stats
    
    def get_recent_results(self, limit: Optional[int] = None) -> List[ValidationResult]:
        """Get recent validation results."""
        if limit is None:
            return self.recent_results.copy()
        return self.recent_results[-limit:]
    
    def __del__(self):
        """Automatic cleanup - save stats to file or database if needed."""
        # Since this class doesn't have async resources, we can do
        # simple cleanup in the destructor
        if self.stats.total_validations > 0:
            logger.info(f"ValidationManager processed {self.stats.total_validations} validations") 
        # Future: could save stats to a file here 