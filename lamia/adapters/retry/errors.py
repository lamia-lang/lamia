"""Common types and exceptions for retry handling."""

from typing import List

class ExternalSystemError(Exception):
    """Base exception for all external system operation errors."""
    pass

class ExternalSystemRetryError(ExternalSystemError):
    """Exception raised when all retries have been exhausted."""
    def __init__(self, message: str, attempts: List[RetryAttempt], final_error: Exception):
        super().__init__(message)
        self.attempts = attempts
        self.final_error = final_error
        self.total_attempts = len(attempts)
        self.error_categories = [attempt.error_category for attempt in attempts]

class ExternalSystemRateLimitError(ExternalSystemRetryError):
    """Exception raised when rate limits were hit and retries exhausted."""
    pass

class ExternalSystemTransientError(ExternalSystemRetryError):
    """Exception raised when transient errors were hit and retries exhausted."""
    pass

class ExternalSystemPermanentError(ExternalSystemError):
    """Exception raised for permanent errors that should not be retried."""
    def __init__(self, message: str, original_error: Exception):
        super().__init__(message)
        self.original_error = original_error 