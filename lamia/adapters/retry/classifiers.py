"""Error classification system for different adapter types."""

from abc import ABC, abstractmethod
from typing import Type, Dict, Optional
import re

from .config import ErrorCategory


class ErrorClassifier(ABC):
    """Base class for error classification strategies."""
    
    @abstractmethod
    def classify_error(self, error: Exception) -> ErrorCategory:
        """Classify an error to determine retry behavior."""
        pass


class HttpErrorClassifier(ErrorClassifier):
    """HTTP-specific error classifier that works with multiple HTTP libraries."""
    
    def classify_error(self, error: Exception) -> ErrorCategory:
        """Classify HTTP errors from various libraries (aiohttp, requests, httpx, etc.)."""
        error_msg = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # Check for rate limiting (HTTP 429 or message patterns)
        if (
            self._has_status_code(error, 429)
            or "rate limit" in error_msg
            or "too many requests" in error_msg
            or "quota" in error_msg
            or "ratelimit" in error_msg
        ):
            return ErrorCategory.RATE_LIMIT
        
        # Check for permanent errors (4xx except 429)
        if (
            self._has_4xx_status_code(error)
            or "unauthorized" in error_msg
            or "forbidden" in error_msg
            or "invalid api key" in error_msg
            or "authentication" in error_msg
            or "invalid request" in error_msg
            or "bad request" in error_msg
            or "not found" in error_msg
        ):
            return ErrorCategory.PERMANENT
        
        # Check for transient errors (network, timeouts, 5xx)
        if (
            self._has_5xx_status_code(error)
            or "timeout" in error_msg
            or "connection" in error_msg
            or "network" in error_msg
            or "server error" in error_msg
            or "service unavailable" in error_msg
            or "connector" in error_type
            or "timeout" in error_type
            or isinstance(error, (ConnectionError, TimeoutError))
        ):
            return ErrorCategory.TRANSIENT
        
        # Default to transient for unknown errors (safer to retry)
        return ErrorCategory.TRANSIENT
    
    def _has_status_code(self, error: Exception, status_code: int) -> bool:
        """Check if error has specific HTTP status code (works across HTTP libraries)."""
        # aiohttp, httpx
        if hasattr(error, 'status') and error.status == status_code:
            return True
        # requests
        if hasattr(error, 'response') and hasattr(error.response, 'status_code'):
            return error.response.status_code == status_code
        # Pattern matching in error message
        return re.search(rf'\b{status_code}\b', str(error)) is not None
    
    def _has_4xx_status_code(self, error: Exception) -> bool:
        """Check if error has 4xx status code (excluding 429)."""
        # aiohttp, httpx
        if hasattr(error, 'status') and 400 <= error.status < 500 and error.status != 429:
            return True
        # requests
        if hasattr(error, 'response') and hasattr(error.response, 'status_code'):
            status = error.response.status_code
            return 400 <= status < 500 and status != 429
        # Pattern matching
        return bool(re.search(r'\b4[0-9]{2}\b', str(error)) and not re.search(r'\b429\b', str(error)))
    
    def _has_5xx_status_code(self, error: Exception) -> bool:
        """Check if error has 5xx status code."""
        # aiohttp, httpx
        if hasattr(error, 'status') and 500 <= error.status < 600:
            return True
        # requests
        if hasattr(error, 'response') and hasattr(error.response, 'status_code'):
            return 500 <= error.response.status_code < 600
        # Pattern matching
        return bool(re.search(r'\b5[0-9]{2}\b', str(error)))


class FilesystemErrorClassifier(ErrorClassifier):
    """Filesystem-specific error classifier (no rate limiting)."""
    
    def classify_error(self, error: Exception) -> ErrorCategory:
        """Classify filesystem errors."""
        error_msg = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # Permanent errors (permissions, not found, etc.)
        if (
            isinstance(error, (PermissionError, FileNotFoundError))
            or "permission" in error_msg
            or "access denied" in error_msg
            or "no such file" in error_msg
            or "directory not found" in error_msg
            or "invalid path" in error_msg
            or "read-only" in error_msg
        ):
            return ErrorCategory.PERMANENT
        
        # Transient errors (disk space, temporary locks, etc.)
        if (
            isinstance(error, (OSError, IOError))
            or "disk" in error_msg
            or "space" in error_msg
            or "busy" in error_msg
            or "lock" in error_msg
            or "temporary" in error_msg
        ):
            return ErrorCategory.TRANSIENT
        
        # Default to transient for filesystem operations
        return ErrorCategory.TRANSIENT


class LocalErrorClassifier(ErrorClassifier):
    """Local operation error classifier (minimal retries)."""
    
    def classify_error(self, error: Exception) -> ErrorCategory:
        """Classify local operation errors - most should be permanent."""
        error_msg = str(error).lower()
        
        # Very few local errors should be retried
        if (
            "temporary" in error_msg
            or "busy" in error_msg
            or "lock" in error_msg
        ):
            return ErrorCategory.TRANSIENT
        
        # Most local errors are permanent
        return ErrorCategory.PERMANENT


# Registry of classifiers by adapter type
_CLASSIFIER_REGISTRY: Dict[str, Type[ErrorClassifier]] = {
    "http": HttpErrorClassifier,
    "filesystem": FilesystemErrorClassifier,
    "local": LocalErrorClassifier,
}


def get_error_classifier(external_system_type: str) -> ErrorClassifier:
    """Get appropriate error classifier based on external system type."""
    # Map adapter types to classifier types
    if "http" in external_system_type.lower() or "llm" in external_system_type.lower():
        classifier_type = "http"
    elif "fs" in external_system_type.lower() or "file" in external_system_type.lower():
        classifier_type = "filesystem"  
    elif "local" in external_system_type.lower():
        classifier_type = "local"
    else:
        # Default to HTTP classifier for most external systems
        classifier_type = "http"
    
    classifier_class = _CLASSIFIER_REGISTRY.get(classifier_type, HttpErrorClassifier)
    return classifier_class()


def register_error_classifier(system_type: str, classifier_class: Type[ErrorClassifier]) -> None:
    """Register a custom error classifier for a specific system type."""
    _CLASSIFIER_REGISTRY[system_type] = classifier_class 