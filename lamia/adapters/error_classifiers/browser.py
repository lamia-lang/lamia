"""Browser error classifier optimized for web automation operations."""

from .base import ErrorClassifier
from .categories import ErrorCategory
from lamia.errors import ExternalOperationPermanentError, ExternalOperationTransientError, ExternalOperationRateLimitError

# Browser permanent error patterns
BROWSER_PERMANENT_PATTERNS = [
    "not initialized",
    "invalid session",
    "session not created",
    "browser not supported",
    "invalid argument",
    "invalid selector syntax",
    "malformed selector",
    "connection refused",  # Browser/driver was closed
    "session deleted",
    "chrome not reachable",
]

# Browser transient error patterns
BROWSER_TRANSIENT_PATTERNS = [
    "element not found",
    "not found",
    "not visible",
    "not clickable",
    "timeout",
    "stale element",
    "connection",
    "network",
    "server error",
    "webdriver error",
    "element not interactable",
    "element is not attached",
]


class BrowserErrorClassifier(ErrorClassifier):
    """Browser-specific error classifier.
    
    Optimized for browser automation - treats element not found as transient
    since selectors might work on retry or need AI-powered resolution.
    Most browser errors are transient (timing issues, DOM changes)
    with only a few permanent cases (invalid sessions, unsupported browsers).
    """
    
    def classify_error(self, error: Exception) -> ErrorCategory:
        """Classify browser errors.
        
        Args:
            error: Exception from browser operation
            
        Returns:
            ErrorCategory for retry behavior (no RATE_LIMIT for browsers)
        """
        # Respect explicit error types from adapters
        if isinstance(error, ExternalOperationPermanentError):
            return ErrorCategory.PERMANENT
        if isinstance(error, ExternalOperationTransientError):
            return ErrorCategory.TRANSIENT
        if isinstance(error, ExternalOperationRateLimitError):
            return ErrorCategory.RATE_LIMIT
        
        error_msg = str(error).lower()
        
        # Check for permanent errors first (rare for browsers)
        if self._is_permanent_error(error, error_msg):
            return ErrorCategory.PERMANENT
        
        # Check for transient errors (most common for browsers)
        if self._is_transient_error(error, error_msg):
            return ErrorCategory.TRANSIENT
        
        # Default to transient for unknown browser errors
        # (conservative approach - most browser errors are retryable or need AI help)
        return ErrorCategory.TRANSIENT
    
    def _is_permanent_error(self, error: Exception, error_msg: str) -> bool:
        """Check if error indicates a permanent failure."""
        return any(pattern in error_msg for pattern in BROWSER_PERMANENT_PATTERNS)
    
    def _is_transient_error(self, error: Exception, error_msg: str) -> bool:
        """Check if error indicates a transient failure."""
        return any(pattern in error_msg for pattern in BROWSER_TRANSIENT_PATTERNS)


