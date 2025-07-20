"""Local operation error classifier with minimal retries."""

from .base import ErrorClassifier
from ..config import ErrorCategory

# Local transient error patterns (very limited)
LOCAL_TRANSIENT_PATTERNS = [
    "temporary",
    "busy",
    "lock",
    "resource temporarily unavailable",
    "try again",
]

# Local transient exception types
LOCAL_TRANSIENT_EXCEPTIONS = (
    BlockingIOError,
    InterruptedError,
)


class LocalErrorClassifier(ErrorClassifier):
    """Local operation error classifier with minimal retries.
    
    Designed for in-process operations that should generally succeed
    immediately. Most local errors indicate code bugs or permanent
    configuration issues that won't be resolved by retrying.
    
    Only retries in very specific cases:
    - Resource locking conflicts
    - Temporary system resource unavailability
    """
    
    def classify_error(self, error: Exception) -> ErrorCategory:
        """Classify local operation errors.
        
        Args:
            error: Exception from local operation
            
        Returns:
            ErrorCategory - biased toward PERMANENT for local ops
        """
        error_msg = str(error).lower()
        
        # Check for the few transient local error cases
        if self._is_transient_error(error, error_msg):
            return ErrorCategory.TRANSIENT
        
        # Most local errors are permanent (code bugs, config issues)
        return ErrorCategory.PERMANENT
    
    def _is_transient_error(self, error: Exception, error_msg: str) -> bool:
        """Check if local error might be transient.
        
        Very conservative - only flags errors that are clearly
        due to temporary resource conflicts or system state.
        """
        # Check exception types
        if isinstance(error, LOCAL_TRANSIENT_EXCEPTIONS):
            return True
        
        # Check message patterns
        return any(pattern in error_msg for pattern in LOCAL_TRANSIENT_PATTERNS) 