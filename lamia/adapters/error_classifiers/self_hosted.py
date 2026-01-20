"""Self-hosted LLM error classifier for Ollama, local models, and custom servers."""

from .base import ErrorClassifier
from .categories import ErrorCategory

# Self-hosted LLM permanent error patterns
SELF_HOSTED_PERMANENT_PATTERNS = [
    "model not found",
    "model not loaded",
    "does not exist",
    "invalid model",
    "unknown model",
    "unsupported model",
    "authentication",
    "unauthorized",
    "forbidden",
    "access denied",
    "credentials",
    "bad request",
    "invalid request",
    "malformed",
    "unsupported parameter",
    "invalid endpoint",
    "endpoint path",
    "not found",
    "configuration",
    "misconfigured",
    "not in library",
    "corrupted",
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
]

# Self-hosted rarely has rate limiting, but some might implement it
SELF_HOSTED_RATE_LIMIT_PATTERNS = [
    "rate limit",
    "rate too high",
    "too many requests",
    "too many concurrent",
    "quota",
    "concurrency",
    "concurrent request",
    "queue full",
    "queue at capacity",
    "queue size",
    "at capacity",
]


class SelfHostedLLMErrorClassifier(ErrorClassifier):
    """Error classifier for self-hosted LLMs (Ollama, local models, custom servers).
    
    Classifies based on LLM-specific error message patterns.
    HTTP status codes are handled by HttpErrorClassifier.
    """

    def classify_error(self, error: Exception) -> ErrorCategory:
        """Classify self-hosted LLM errors based on message patterns."""
        error_msg = str(error).lower()

        if any(p in error_msg for p in SELF_HOSTED_RATE_LIMIT_PATTERNS):
            return ErrorCategory.RATE_LIMIT

        if any(p in error_msg for p in SELF_HOSTED_PERMANENT_PATTERNS):
            return ErrorCategory.PERMANENT

        if any(p in error_msg for p in SELF_HOSTED_TRANSIENT_PATTERNS):
            return ErrorCategory.TRANSIENT

        # Default to transient for unknown self-hosted errors
        return ErrorCategory.TRANSIENT
