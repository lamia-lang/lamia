"""Error categories for retry decisions."""

from enum import Enum

class ErrorCategory(Enum):
    """Categories of errors for retry decisions."""
    PERMANENT = "permanent"   # Never retry (invalid credentials, etc)
    TRANSIENT = "transient"  # Temporary issues (network, timeout)
    RATE_LIMIT = "rate_limit"  # Special case for rate limiting 