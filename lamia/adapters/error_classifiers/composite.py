"""Composite error classifier that chains multiple classifiers."""

from .base import ErrorClassifier
from .categories import ErrorCategory


class CompositeErrorClassifier(ErrorClassifier):
    """Chains multiple classifiers, using the first decisive result.
    
    Classifiers are tried in order. The first classifier that returns
    PERMANENT or RATE_LIMIT wins. If all return TRANSIENT, returns TRANSIENT.
    """
    
    def __init__(self, *classifiers: ErrorClassifier):
        self.classifiers = classifiers
    
    def classify_error(self, error: Exception) -> ErrorCategory:
        """Classify error by trying each classifier in order."""
        for classifier in self.classifiers:
            result = classifier.classify_error(error)
            # PERMANENT and RATE_LIMIT are decisive - return immediately
            if result in (ErrorCategory.PERMANENT, ErrorCategory.RATE_LIMIT):
                return result
        # All returned TRANSIENT (the default), so return TRANSIENT
        return ErrorCategory.TRANSIENT

