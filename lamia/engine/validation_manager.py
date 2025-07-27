import asyncio
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime
from dataclasses import dataclass, field
from lamia.command_types import CommandType

logger = logging.getLogger(__name__)

@dataclass
class ValidationStats:
    """Statistics about validation operations across all domains."""
    total_validations: int = 0
    successful_validations: int = 0
    failed_validations: int = 0
    by_domain: Dict[CommandType, int] = field(default_factory=dict)
    # Intermediate validation tracking (per provider/model)
    intermediate_failures: Dict[str, int] = field(default_factory=dict)  # provider_name -> failure_count
    intermediate_successes: Dict[str, int] = field(default_factory=dict)  # provider_name -> success_count

class ValidationStatsTracker:
    """Tracks validation statistics across all domains."""
    
    def __init__(self):
        # Centralized statistics tracking
        self.stats = ValidationStats()
    
    def record_validation_result(self, is_valid: bool, command_type: CommandType):
        """Record validation result and update centralized statistics.
        
        Args:
            is_valid: Whether the validation was successful
            command_type: The type of command that was executed
        """
        # Update statistics
        self.stats.total_validations += 1
        
        if is_valid:
            self.stats.successful_validations += 1
        else:
            self.stats.failed_validations += 1
        
        # Update by-domain stats (store as simple string key)
        domain_key = command_type.value if isinstance(command_type, CommandType) else str(command_type)
        self.stats.by_domain[domain_key] = self.stats.by_domain.get(domain_key, 0) + 1
    
    def record_intermediate_validation_attempt(self, provider_name: str, is_successful: bool):
        """Record an intermediate validation attempt for detailed statistics.
        
        This tracks individual provider attempts before the final result, giving insights into
        provider reliability and validation success rates per provider.
        
        Args:
            provider_name: Name of the provider that attempted validation (e.g., "gpt-4", "selenium")
            is_successful: Whether this specific validation attempt succeeded
        """
        if is_successful:
            self.stats.intermediate_successes[provider_name] = self.stats.intermediate_successes.get(provider_name, 0) + 1
        else:
            self.stats.intermediate_failures[provider_name] = self.stats.intermediate_failures.get(provider_name, 0) + 1
            
        logger.debug(f"Recorded intermediate validation attempt for {provider_name}: {'success' if is_successful else 'failure'}")
    
    def get_provider_success_rates(self) -> Dict[str, Dict[str, float]]:
        """Get success rates and attempt counts for each provider based on intermediate validation attempts.
        
        Returns:
            Dict mapping provider names to their stats: {
                "provider_name": {
                    "success_rate": 0.85,
                    "total_attempts": 20,
                    "successes": 17,
                    "failures": 3
                }
            }
        """
        provider_stats = {}
        
        # Get all providers that have been used
        all_providers = set(self.stats.intermediate_successes.keys()) | set(self.stats.intermediate_failures.keys())
        
        for provider_name in all_providers:
            successes = self.stats.intermediate_successes.get(provider_name, 0)
            failures = self.stats.intermediate_failures.get(provider_name, 0)
            total_attempts = successes + failures
            
            provider_stats[provider_name] = {
                "success_rate": successes / total_attempts if total_attempts > 0 else 0.0,
                "total_attempts": total_attempts,
                "successes": successes,
                "failures": failures
            }
        
        return provider_stats
    
    def get_validation_stats(self) -> ValidationStats:
        """Get current validation statistics."""
        return self.stats
    
    def __del__(self):
        """Automatic cleanup - save stats to file or database if needed."""
        # Since this class doesn't have async resources, we can do
        # simple cleanup in the destructor
        if self.stats.total_validations > 0:
            logger.info(f"ValidationStatsTracker processed {self.stats.total_validations} validations") 
        # Future: could save stats to a file here 