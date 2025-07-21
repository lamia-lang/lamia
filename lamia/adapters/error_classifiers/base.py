"""Base error classifier abstract class."""

from abc import ABC, abstractmethod
from lamia.adapters.retry.strategies import ErrorCategory

class ErrorClassifier(ABC):
    """Base class for error classification strategies.
    
    Error classifiers determine how exceptions should be categorized
    for retry behavior:
    - PERMANENT: Never retry (auth failures, bad requests)
    - TRANSIENT: Retry with standard delays (network issues, 5xx errors)
    - RATE_LIMIT: Retry with longer delays (429 errors, quota exceeded)
    """
    
    @abstractmethod
    def classify_error(self, error: Exception) -> ErrorCategory:
        """Classify an error to determine retry behavior.
        
        Args:
            error: The exception to classify
            
        Returns:
            ErrorCategory indicating the type of error and retry strategy
        """
        pass 