"""Retry-related error types for external operations."""

from typing import List, Optional

class ExternalOperationError(Exception):
    """Base exception for external operation failures."""
    
    def __init__(self, message: str, retry_history: List[str], original_error: Optional[Exception] = None):
        super().__init__(message)
        self.retry_history = retry_history
        self.original_error = original_error

class ExternalOperationRetryError(ExternalOperationError):
    """Raised when an external operation fails after all retry attempts."""
    pass

class ExternalOperationTransientError(ExternalOperationError):
    """Raised when an external operation fails due to a transient error."""
    pass

class ExternalOperationRateLimitError(ExternalOperationError):
    """Raised when an external operation fails due to rate limiting."""
    pass

class ExternalOperationPermanentError(ExternalOperationError):
    """Raised when an external operation fails due to a permanent error."""
    pass 