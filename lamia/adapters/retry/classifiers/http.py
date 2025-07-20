"""HTTP error classifier that works with multiple HTTP libraries."""

import re
from .base import ErrorClassifier
from ..config import ErrorCategory

# HTTP Status Codes
HTTP_TOO_MANY_REQUESTS = 429
HTTP_CLIENT_ERROR_START = 400
HTTP_CLIENT_ERROR_END = 500
HTTP_SERVER_ERROR_START = 500
HTTP_SERVER_ERROR_END = 600

# Rate limiting patterns
RATE_LIMIT_PATTERNS = [
    "rate limit",
    "too many requests", 
    "quota",
    "ratelimit",
]

# Permanent error patterns
PERMANENT_ERROR_PATTERNS = [
    "unauthorized",
    "forbidden", 
    "invalid api key",
    "authentication",
    "invalid request",
    "bad request",
    "not found",
]

# Transient error patterns
TRANSIENT_ERROR_PATTERNS = [
    "timeout",
    "connection",
    "network", 
    "server error",
    "service unavailable",
]

# Connection/timeout error types (partial name matching)
CONNECTION_ERROR_TYPES = [
    "connector",
    "timeout",
    "connection",
]


class HttpErrorClassifier(ErrorClassifier):
    """HTTP-specific error classifier that works with multiple HTTP libraries.
    
    Supports aiohttp, requests, httpx, and other HTTP client libraries
    by using both attribute inspection and pattern matching.
    """
    
    def classify_error(self, error: Exception) -> ErrorCategory:
        """Classify HTTP errors from various libraries.
        
        Args:
            error: Exception from HTTP operation
            
        Returns:
            ErrorCategory for retry behavior
        """
        error_msg = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # Check for rate limiting first (highest priority)
        if self._is_rate_limit_error(error, error_msg):
            return ErrorCategory.RATE_LIMIT
        
        # Check for permanent errors (don't retry)
        if self._is_permanent_error(error, error_msg):
            return ErrorCategory.PERMANENT
        
        # Check for transient errors (retry with standard delays)
        if self._is_transient_error(error, error_msg, error_type):
            return ErrorCategory.TRANSIENT
        
        # Default to transient for unknown HTTP errors (safer to retry)
        return ErrorCategory.TRANSIENT
    
    def _is_rate_limit_error(self, error: Exception, error_msg: str) -> bool:
        """Check if error indicates rate limiting."""
        # Check HTTP status code
        if self._has_status_code(error, HTTP_TOO_MANY_REQUESTS):
            return True
        
        # Check message patterns
        return any(pattern in error_msg for pattern in RATE_LIMIT_PATTERNS)
    
    def _is_permanent_error(self, error: Exception, error_msg: str) -> bool:
        """Check if error indicates a permanent failure."""
        # Check for 4xx errors (except 429)
        if self._has_4xx_status_code(error):
            return True
        
        # Check message patterns
        return any(pattern in error_msg for pattern in PERMANENT_ERROR_PATTERNS)
    
    def _is_transient_error(self, error: Exception, error_msg: str, error_type: str) -> bool:
        """Check if error indicates a transient failure."""
        # Check for 5xx server errors
        if self._has_5xx_status_code(error):
            return True
        
        # Check for connection/timeout exceptions
        if isinstance(error, (ConnectionError, TimeoutError)):
            return True
        
        # Check error type names
        if any(conn_type in error_type for conn_type in CONNECTION_ERROR_TYPES):
            return True
        
        # Check message patterns
        return any(pattern in error_msg for pattern in TRANSIENT_ERROR_PATTERNS)
    
    def _has_status_code(self, error: Exception, status_code: int) -> bool:
        """Check if error has specific HTTP status code (works across HTTP libraries)."""
        # aiohttp, httpx style
        if hasattr(error, 'status') and error.status == status_code:
            return True
        
        # requests style
        if hasattr(error, 'response') and hasattr(error.response, 'status_code'):
            return error.response.status_code == status_code
        
        # Pattern matching in error message
        return re.search(rf'\b{status_code}\b', str(error)) is not None
    
    def _has_4xx_status_code(self, error: Exception) -> bool:
        """Check if error has 4xx status code (excluding 429)."""
        # aiohttp, httpx style
        if hasattr(error, 'status'):
            status = error.status
            return (HTTP_CLIENT_ERROR_START <= status < HTTP_CLIENT_ERROR_END 
                   and status != HTTP_TOO_MANY_REQUESTS)
        
        # requests style
        if hasattr(error, 'response') and hasattr(error.response, 'status_code'):
            status = error.response.status_code
            return (HTTP_CLIENT_ERROR_START <= status < HTTP_CLIENT_ERROR_END 
                   and status != HTTP_TOO_MANY_REQUESTS)
        
        # Pattern matching (4xx but not 429)
        return (bool(re.search(r'\b4[0-9]{2}\b', str(error))) 
               and not re.search(r'\b429\b', str(error)))
    
    def _has_5xx_status_code(self, error: Exception) -> bool:
        """Check if error has 5xx status code."""
        # aiohttp, httpx style
        if hasattr(error, 'status'):
            return HTTP_SERVER_ERROR_START <= error.status < HTTP_SERVER_ERROR_END
        
        # requests style  
        if hasattr(error, 'response') and hasattr(error.response, 'status_code'):
            return (HTTP_SERVER_ERROR_START <= error.response.status_code < HTTP_SERVER_ERROR_END)
        
        # Pattern matching
        return bool(re.search(r'\b5[0-9]{2}\b', str(error))) 