"""Configuration for external system retry handling."""

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Optional

class ErrorCategory(Enum):
    """Categories of errors for retry decisions."""
    
    PERMANENT = "permanent"   # Never retry (invalid credentials, etc)
    TRANSIENT = "transient"  # Temporary issues (network, timeout)
    RATE_LIMIT = "rate_limit"  # Special case for rate limiting

@dataclass
class ExternalSystemRetryConfig:
    """Configuration for external system retry behavior."""
    
    max_attempts: int = 3
    base_delay: float = 1.0  # Initial delay between retries in seconds
    max_delay: float = 32.0  # Maximum delay between retries in seconds
    exponential_base: float = 2.0  # Each retry multiplies previous delay by this value
    max_total_duration: Optional[timedelta] = timedelta(minutes=5)

    @classmethod
    def for_local_operations(cls) -> 'ExternalSystemRetryConfig':
        """Get config optimized for local operations."""
        return cls(
            max_attempts=1,  # No retries
            base_delay=0.1,
            max_delay=1.0,
            max_total_duration=timedelta(seconds=100)
        )
    
    @classmethod
    def for_network_operations(cls) -> 'ExternalSystemRetryConfig':
        """Get config optimized for network operations."""
        return cls(
            max_attempts=3,
            base_delay=1.0,
            max_delay=32.0,
            max_total_duration=timedelta(minutes=5)
        )
    
    @classmethod
    def for_llm_operations(cls) -> 'ExternalSystemRetryConfig':
        """Get config optimized for LLM operations."""
        return cls(
            max_attempts=5,
            base_delay=2.0,
            max_delay=60.0,
            max_total_duration=timedelta(minutes=10)
        ) 