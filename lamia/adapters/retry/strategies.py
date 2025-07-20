"""Retry strategies for external system operations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class ErrorCategory(Enum):
    """Categories of errors for retry decisions."""
    PERMANENT = "permanent"   # Never retry (invalid credentials, etc)
    TRANSIENT = "transient"  # Temporary issues (network, timeout)
    RATE_LIMIT = "rate_limit"  # Special case for rate limiting

@dataclass
class RetryAttempt:
    """Metadata about a retry attempt."""
    attempt_number: int
    start_time: datetime
    error: Exception
    error_category: ErrorCategory


class RetryStrategy(ABC):
    """Base class for retry strategies."""
    
    @abstractmethod
    def should_retry(self, attempt: RetryAttempt) -> bool:
        """Determine if another retry should be attempted."""
        pass

    @abstractmethod
    def get_delay(self, attempt: RetryAttempt) -> float:
        """Get delay in seconds before next retry."""
        pass

class ExponentialBackoffStrategy(RetryStrategy):
    """Exponential backoff strategy with rate limit handling."""
    
    def __init__(
        self,
        base_delay: float,
        max_delay: float,
        exponential_base: float
    ):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base

    def should_retry(self, attempt: RetryAttempt) -> bool:
        return attempt.error_category != ErrorCategory.PERMANENT

    def get_delay(self, attempt: RetryAttempt) -> float:
        base_delay = self.base_delay * (self.exponential_base ** attempt.attempt_number)
        
        if attempt.error_category == ErrorCategory.RATE_LIMIT:
            base_delay *= 2  # Longer delays for rate limits
            
        return min(base_delay, self.max_delay)

class NoRetryStrategy(RetryStrategy):
    """Strategy that never retries."""
    
    def should_retry(self, attempt: RetryAttempt) -> bool:
        return False

    def get_delay(self, attempt: RetryAttempt) -> float:
        return 0.0 