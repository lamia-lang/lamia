"""HTTP error classifier using typed exceptions with pattern fallback."""

import re
from typing import Optional

from aiohttp import ClientResponseError as AiohttpError
from requests import HTTPError as RequestsError

from .base import ErrorClassifier
from .categories import ErrorCategory

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
    """HTTP error classifier using typed exceptions with pattern fallback."""
    
    def classify_error(self, error: Exception) -> ErrorCategory:
        """Classify HTTP errors."""
        status = self._extract_status_code(error)
        error_msg = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # Rate limiting first (status OR pattern)
        if status == HTTP_TOO_MANY_REQUESTS or any(p in error_msg for p in RATE_LIMIT_PATTERNS):
            return ErrorCategory.RATE_LIMIT
        
        # Status code classification
        if status is not None:
            if HTTP_CLIENT_ERROR_START <= status < HTTP_CLIENT_ERROR_END:
                return ErrorCategory.PERMANENT
            if HTTP_SERVER_ERROR_START <= status < HTTP_SERVER_ERROR_END:
                return ErrorCategory.TRANSIENT
        
        # Python typed exceptions
        if isinstance(error, (ConnectionError, TimeoutError)):
            return ErrorCategory.TRANSIENT
        
        # Check error type names
        if any(conn_type in error_type for conn_type in CONNECTION_ERROR_TYPES):
            return ErrorCategory.TRANSIENT
        
        # Pattern fallback
        if any(p in error_msg for p in PERMANENT_ERROR_PATTERNS):
            return ErrorCategory.PERMANENT
        if any(p in error_msg for p in TRANSIENT_ERROR_PATTERNS):
            return ErrorCategory.TRANSIENT
        
        return ErrorCategory.TRANSIENT
    
    def _extract_status_code(self, error: Exception) -> Optional[int]:
        """Extract status code from typed exceptions."""
        if isinstance(error, AiohttpError):
            return error.status
        if isinstance(error, RequestsError) and error.response is not None:
            return error.response.status_code
        
        # Extract from message
        match = re.search(r'\b([45]\d{2})\b', str(error))
        return int(match.group(1)) if match else None
