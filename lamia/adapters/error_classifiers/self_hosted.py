"""Self-hosted LLM error classifier for Ollama, local models, and custom servers."""

from .base import ErrorClassifier
from .categories import ErrorCategory

# Self-hosted LLM permanent error patterns
SELF_HOSTED_PERMANENT_PATTERNS = [
    "model not found",
    "model not loaded", 
    "invalid model",
    "authentication",
    "unauthorized",
    "forbidden",
    "bad request",
    "invalid request",
    "not found",
    "configuration error",
]

# Self-hosted LLM transient error patterns
SELF_HOSTED_TRANSIENT_PATTERNS = [
    "timeout",
    "connection",
    "network",
    "server error",
    "internal error", 
    "service unavailable",
    "out of memory",
    "oom",
    "memory",
    "resource",
    "busy",
    "loading",
    "processing",
    "queue",
]

# Self-hosted rarely has rate limiting, but some might implement it
SELF_HOSTED_RATE_LIMIT_PATTERNS = [
    "rate limit",
    "too many requests",
    "quota",
    "concurrency limit",
    "queue full",
]


class SelfHostedLLMErrorClassifier(ErrorClassifier):
    """Error classifier for self-hosted LLMs (Ollama, local models, custom servers).
    
    Optimized for self-hosted model characteristics:
    - Rarely have rate limiting (but some custom servers might)
    - Hardware-dependent errors (memory, CPU, GPU)
    - Model loading and inference errors
    - Longer inference times on slow hardware
    """
    
    def classify_error(self, error: Exception) -> ErrorCategory:
        """Classify self-hosted LLM errors.
        
        Args:
            error: Exception from self-hosted LLM operation
            
        Returns:
            ErrorCategory for retry behavior
        """
        error_msg = str(error).lower()
        
        # Check for rate limiting first (rare but possible)
        if self._is_rate_limit_error(error_msg):
            return ErrorCategory.RATE_LIMIT
        
        # Check for permanent errors
        if self._is_permanent_error(error, error_msg):
            return ErrorCategory.PERMANENT
        
        # Check for transient errors (most common for self-hosted)
        if self._is_transient_error(error, error_msg):
            return ErrorCategory.TRANSIENT
        
        # Default to transient for unknown self-hosted errors
        # (hardware issues are often transient)
        return ErrorCategory.TRANSIENT
    
    def _is_rate_limit_error(self, error_msg: str) -> bool:
        """Check if error indicates rate limiting (rare for self-hosted)."""
        return any(pattern in error_msg for pattern in SELF_HOSTED_RATE_LIMIT_PATTERNS)
    
    def _is_permanent_error(self, error: Exception, error_msg: str) -> bool:
        """Check if error indicates a permanent failure."""
        # Check for HTTP status codes (if using HTTP client)
        if hasattr(error, 'status') and 400 <= error.status < 500 and error.status != 429:
            return True
        if hasattr(error, 'response') and hasattr(error.response, 'status_code'):
            status = error.response.status_code
            if 400 <= status < 500 and status != 429:
                return True
        
        # Check message patterns
        return any(pattern in error_msg for pattern in SELF_HOSTED_PERMANENT_PATTERNS)
    
    def _is_transient_error(self, error: Exception, error_msg: str) -> bool:
        """Check if error indicates a transient failure."""
        # Check for HTTP 5xx errors
        if hasattr(error, 'status') and 500 <= error.status < 600:
            return True
        if hasattr(error, 'response') and hasattr(error.response, 'status_code'):
            if 500 <= error.response.status_code < 600:
                return True
        
        # Check for connection/timeout exceptions
        if isinstance(error, (ConnectionError, TimeoutError)):
            return True
        
        # Check message patterns
        return any(pattern in error_msg for pattern in SELF_HOSTED_TRANSIENT_PATTERNS) 