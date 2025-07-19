import asyncio
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime
from dataclasses import dataclass, field
from lamia.engine.managers.manager import Manager
from lamia.command_types import CommandType
from lamia.validation.base import ValidationResult, BaseValidator

logger = logging.getLogger(__name__)

@dataclass
class ValidationStats:
    """Statistics about validation operations across all domains."""
    total_validations: int = 0
    successful_validations: int = 0
    failed_validations: int = 0
    avg_execution_time_ms: float = 0.0
    by_domain: Dict[CommandType, int] = field(default_factory=dict)

class ValidationStrategyNotFoundError(LookupError):
    """Raised when no validation strategy exists for the requested command type."""

class ValidationManager:
    """Manages validation across all domains and tracks centralized statistics."""
    
    def __init__(self):
        
        # Centralized statistics tracking
        self.stats = ValidationStats()
        self.recent_results: List[ValidationResult] = []
        self.max_recent_results = 100  # Keep last 100 results
    
    async def validate(self, command_type: CommandType, manager: Manager, content: str, validator: Optional[BaseValidator] = None) -> ValidationResult:
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
            # Execute validation
            validation_result = await manager.execute(content, validator)
            
            # Record successful validation
            execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
            self._record_validation_result(validation_result, command_type, execution_time)
            
            return validation_result
            
        except Exception as e:
            # Record failed validation
            execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
            validation_result = ValidationResult(
                is_valid=False,
                error_message=str(e)
            )
            self._record_validation_result(validation_result, command_type, execution_time)
            raise
    
    def _record_validation_result(self, result: ValidationResult, command_type: CommandType, execution_time_ms: float):
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
        
        # Update by-domain stats (store as simple string key)
        domain_key = command_type.value if isinstance(command_type, CommandType) else str(command_type)
        self.stats.by_domain[domain_key] = self.stats.by_domain.get(domain_key, 0) + 1
    
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