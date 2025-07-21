"""External system retry handling."""

from .retry_handler import RetryHandler
from lamia.errors import (
    ExternalOperationError,
    ExternalOperationFailedError, 
    ExternalOperationTransientError,
    ExternalOperationRateLimitError,
    ExternalOperationPermanentError
)

# Optional wrappers
try:
    from .wrappers.llm import RetryWrappedLLMAdapter
except ImportError:
    pass

try:
    from .wrappers.fs import RetryWrappedFSAdapter
except ImportError:
    pass
