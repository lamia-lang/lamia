"""Base error classifier abstract class."""

from abc import ABC, abstractmethod
from .categories import ErrorCategory

class ErrorClassifier(ABC):
    """Base class for error classification strategies.
    
    Error classifiers determine how exceptions should be categorized
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