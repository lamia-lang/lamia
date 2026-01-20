"""Filesystem error classifier using OS error codes and exception types.

Uses errno codes and Python's built-in exception hierarchy for reliable
classification instead of fragile string matching. Works across platforms
(Linux, macOS, Windows) with graceful handling of platform-specific codes.
"""

import errno
from typing import Set

from .base import ErrorClassifier
from .categories import ErrorCategory


def _get_errno(name: str) -> int:
    """Safely get errno code by name, returning -1 if not available on this platform."""
    return getattr(errno, name, -1)


# Permanent errno codes - these errors won't resolve by retrying
# Uses _get_errno() for cross-platform safety (some codes don't exist on Windows)
PERMANENT_ERRNO: Set[int] = {
    code for code in [
        _get_errno('ENOENT'),      # No such file or directory
        _get_errno('EACCES'),      # Permission denied
        _get_errno('EPERM'),       # Operation not permitted
        _get_errno('ENOTDIR'),     # Not a directory
        _get_errno('EISDIR'),      # Is a directory
        _get_errno('EEXIST'),      # File exists
        _get_errno('ENOTEMPTY'),   # Directory not empty
        _get_errno('EROFS'),       # Read-only filesystem
        _get_errno('ENAMETOOLONG'),# Filename too long
        _get_errno('EINVAL'),      # Invalid argument (often invalid paths)
        _get_errno('ELOOP'),       # Too many symbolic links (Unix only)
        _get_errno('EXDEV'),       # Cross-device link
        _get_errno('EMLINK'),      # Too many links
        _get_errno('ENODEV'),      # No such device
        _get_errno('ENXIO'),       # No such device or address
        _get_errno('ENOEXEC'),     # Exec format error
        _get_errno('EFAULT'),      # Bad address
    ] if code != -1  # Filter out unavailable codes
}

# Transient errno codes - these might resolve by retrying
TRANSIENT_ERRNO: Set[int] = {
    code for code in [
        _get_errno('ENOSPC'),      # No space left on device
        _get_errno('EAGAIN'),      # Resource temporarily unavailable
        _get_errno('EBUSY'),       # Device or resource busy
        _get_errno('ETXTBSY'),     # Text file busy (Unix only)
        _get_errno('ENOLCK'),      # No locks available
        _get_errno('EINTR'),       # Interrupted system call
        _get_errno('ENOMEM'),      # Out of memory
        _get_errno('EMFILE'),      # Too many open files
        _get_errno('ENFILE'),      # File table overflow
        _get_errno('EIO'),         # I/O error (can be transient on some devices)
        _get_errno('EDQUOT'),      # Disk quota exceeded (Unix only)
        _get_errno('EWOULDBLOCK'), # Operation would block (alias for EAGAIN on some systems)
    ] if code != -1  # Filter out unavailable codes
}

# Python's built-in permanent exception types (subclasses of OSError)
PERMANENT_EXCEPTION_TYPES = (
    FileNotFoundError,    # errno.ENOENT
    FileExistsError,      # errno.EEXIST
    PermissionError,      # errno.EACCES, errno.EPERM
    NotADirectoryError,   # errno.ENOTDIR
    IsADirectoryError,    # errno.EISDIR
)

# Python's built-in transient exception types
TRANSIENT_EXCEPTION_TYPES = (
    BlockingIOError,      # errno.EAGAIN, errno.EWOULDBLOCK
    InterruptedError,     # errno.EINTR
    TimeoutError,         # Timeout waiting for resource
)


class FilesystemErrorClassifier(ErrorClassifier):
    """Filesystem error classifier using errno codes and exception types.
    
    Relies on OS-level error codes for reliable classification rather than
    fragile string pattern matching. Filesystem errors are well-typed by
    the OS, making this approach much more robust.
    """
    
    def classify_error(self, error: Exception) -> ErrorCategory:
        """Classify filesystem errors using errno codes and exception types.
        
        Classification priority:
        1. Built-in exception types (most specific)
        2. errno codes from OSError
        3. Default to TRANSIENT (conservative - allows retry)
        
        Args:
            error: Exception from filesystem operation
            
        Returns:
            ErrorCategory.PERMANENT or ErrorCategory.TRANSIENT
        """
        # Check built-in permanent exception types first (most reliable)
        if isinstance(error, PERMANENT_EXCEPTION_TYPES):
            return ErrorCategory.PERMANENT
        
        # Check built-in transient exception types
        if isinstance(error, TRANSIENT_EXCEPTION_TYPES):
            return ErrorCategory.TRANSIENT
        
        # Check errno for OSError and subclasses
        if isinstance(error, OSError) and error.errno is not None:
            if error.errno in PERMANENT_ERRNO:
                return ErrorCategory.PERMANENT
            if error.errno in TRANSIENT_ERRNO:
                return ErrorCategory.TRANSIENT
        
        # Default to transient for unknown errors (conservative - allows retry)
        return ErrorCategory.TRANSIENT 