"""External operation errors that bubble up to users.

These errors provide specific information about external system failures and are designed
to give users actionable feedback about what went wrong during operations.

All errors inherit from ExternalOperationError and include:
- retry_history: List of all retry attempts made  
- original_error: The underlying exception that caused the failure

User Error Handling Guide:
- ExternalOperationPermanentError: Don't retry, fix configuration/input
- ExternalOperationRateLimitError: Retry later or reduce request frequency  
- ExternalOperationTransientError: Safe to retry after a short delay
- ExternalOperationFailedError: Unclassified failure, investigate specific error details
"""

from typing import List, Optional

class ExternalOperationError(Exception):
    """Base exception for external operation failures.
    
    This is the base class for all external system operation errors. When you see
    this error or its subclasses, it means an external service (LLM API, filesystem, etc.)
    failed to complete the requested operation.
    
    Attributes:
        retry_history: List of all retry attempts made before failing
        original_error: The underlying exception that caused the failure
    
    Example:
        try:
            result = await lamia.run_async("What is the weather?")
        except ExternalOperationError as e:
            print(f"External system failed: {e}")
            print(f"Retry attempts: {len(e.retry_history)}")
            print(f"Original cause: {e.original_error}")
    """
    
    def __init__(self, message: str, retry_history: List[str], original_error: Optional[Exception] = None):
        super().__init__(message)
        self.retry_history = retry_history
        self.original_error = original_error

class ExternalOperationFailedError(ExternalOperationError):
    """Raised when external operation fails with unclassified error.
    
    This is the fallback error for failures that don't fit into specific
    categories (permanent, rate limit, transient). It indicates the operation
    failed but the exact cause couldn't be determined from error classification.
    
    What to do:
    - Check the original_error for specific details
    - Review retry_history to understand failure pattern  
    - Consider if this is a service issue or request problem
    - May require manual investigation of the underlying error
    
    Example:
        try:
            result = await lamia.run_async("Generate text")
        except ExternalOperationFailedError as e:
            print(f"Operation failed: {e.original_error}")
            print(f"Attempts made: {len(e.retry_history)}")
            # Investigate the specific error details
    """
    pass

class ExternalOperationTransientError(ExternalOperationError):
    """Raised when an external operation fails due to a transient error.
    
    These are temporary failures that are safe to retry. Examples include
    network timeouts, temporary service overload, or connection issues.
    
    What to do:
    - Safe to retry immediately or after a short delay
    - These errors are already automatically retried, so if you see this,
      all automatic retries have been exhausted
    - Consider implementing your own retry with exponential backoff
    
    Example:
        try:
            result = await lamia.run_async("Generate summary")
        except ExternalOperationTransientError as e:
            print("Temporary network issue, retrying in 30 seconds...")
            await asyncio.sleep(30)
            # Retry the operation
    """
    pass

class ExternalOperationRateLimitError(ExternalOperationError):
    """Raised when an external operation fails due to rate limiting.
    
    You've exceeded the API rate limits for the external service. This is common
    with LLM APIs that have requests-per-minute or tokens-per-minute limits.
    
    What to do:
    - Wait before retrying (check the service's rate limit documentation)
    - Reduce your request frequency  
    - Consider upgrading your API plan for higher limits
    - Implement request batching or queuing
    - Switch to a different model with higher limits
    
    Example:
        try:
            result = await lamia.run_async("Process this text") 
        except ExternalOperationRateLimitError as e:
            print("Rate limited, waiting 60 seconds...")
            await asyncio.sleep(60)
            # Consider reducing request frequency
    """
    pass

class ExternalOperationPermanentError(ExternalOperationError):
    """Raised when an external operation fails due to a permanent error.
    
    These are errors that won't be resolved by retrying, such as invalid API keys,
    malformed requests, insufficient permissions, or unsupported operations.
    
    What to do:
    - DON'T retry - the same error will occur
    - Check your API keys and configuration
    - Verify the request format and parameters
    - Check service documentation for supported features
    - Review permissions and account status
    
    Example:
        try:
            result = await lamia.run_async("Generate response")
        except ExternalOperationPermanentError as e:
            print("Configuration error - check API keys and permissions")
            print(f"Error details: {e.original_error}")
            # Fix configuration before retrying
    """
    pass 