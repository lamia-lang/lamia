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