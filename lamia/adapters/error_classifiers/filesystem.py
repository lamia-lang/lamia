"""Filesystem error classifier optimized for file operations."""

from .base import ErrorClassifier
from .categories import ErrorCategory

# Filesystem permanent error patterns
FS_PERMANENT_PATTERNS = [
    "permission",
    "access denied",
    "no such file",
    "directory not found", 
    "invalid path",
    "read-only",
    "not a directory",
    "is a directory",
]

# Filesystem transient error patterns  
FS_TRANSIENT_PATTERNS = [
    "disk",
    "space",
    "busy", 
    "lock",
    "temporary",
    "resource",
    "quota",
]

# Permanent exception types
FS_PERMANENT_EXCEPTIONS = (
    PermissionError,
    FileNotFoundError,
    NotADirectoryError,
    IsADirectoryError,
)

# Transient exception types
FS_TRANSIENT_EXCEPTIONS = (
    OSError,
    IOError,
    BlockingIOError,
)


class FilesystemErrorClassifier(ErrorClassifier):
    """Filesystem-specific error classifier.
    
    Optimized for file operations - does not check for rate limiting
    since filesystems typically don't implement rate limits.
    Most filesystem errors are permanent (permissions, file not found)
    with only a few transient cases (disk full, file locks).
    """
    
    def classify_error(self, error: Exception) -> ErrorCategory:
        """Classify filesystem errors.
        
        Args:
            error: Exception from filesystem operation
            
        Returns:
            ErrorCategory for retry behavior (no RATE_LIMIT for FS)
        """
        error_msg = str(error).lower()
        
        # Check for permanent errors first (most common for FS)
        if self._is_permanent_error(error, error_msg):
            return ErrorCategory.PERMANENT
        
        # Check for transient errors (rare for FS)
        if self._is_transient_error(error, error_msg):
            return ErrorCategory.TRANSIENT
        
        # Default to transient for unknown FS errors
        # (conservative approach - some FS errors might be retryable)
        return ErrorCategory.TRANSIENT
    
    def _is_permanent_error(self, error: Exception, error_msg: str) -> bool:
        """Check if filesystem error is permanent.
        
        Most FS errors are permanent:
        - File/directory not found
        - Permission denied
        - Invalid paths
        - Read-only filesystem violations
        """
        # Check exception types
        if isinstance(error, FS_PERMANENT_EXCEPTIONS):
            return True
        
        # Check message patterns
        return any(pattern in error_msg for pattern in FS_PERMANENT_PATTERNS)
    
    def _is_transient_error(self, error: Exception, error_msg: str) -> bool:
        """Check if filesystem error is transient.
        
        Few FS errors are transient:
        - Disk space issues
        - File locking conflicts
        - Temporary resource unavailability
        """
        # Check exception types
        if isinstance(error, FS_TRANSIENT_EXCEPTIONS):
            # OSError and IOError can be either permanent or transient
            # Check the message to determine which
            return any(pattern in error_msg for pattern in FS_TRANSIENT_PATTERNS)
        
        # Check message patterns
        return any(pattern in error_msg for pattern in FS_TRANSIENT_PATTERNS) 