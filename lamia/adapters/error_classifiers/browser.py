"""Browser error classifier using typed exceptions with pattern fallback."""

from typing import Tuple, Type

from .base import ErrorClassifier
from .categories import ErrorCategory
from lamia.errors import (
    ExternalOperationPermanentError,
    ExternalOperationTransientError,
    ExternalOperationRateLimitError,
)

# =============================================================================
# OPTIONAL TYPED IMPORTS - Selenium
# =============================================================================
try:
    from selenium.common.exceptions import (
        # Permanent - bad configuration, won't fix by retrying
        InvalidSelectorException,
        InvalidSessionIdException,
        NoSuchWindowException,
        UnexpectedAlertPresentException,
        InvalidArgumentException,
        InvalidCookieDomainException,
        NoSuchCookieException,
        InvalidCoordinatesException,
        # Transient - timing/DOM issues, might resolve
        NoSuchElementException,
        StaleElementReferenceException,
        TimeoutException,
        ElementNotInteractableException,
        ElementNotVisibleException,
        ElementClickInterceptedException,
        MoveTargetOutOfBoundsException,
        # Base class
        WebDriverException,
    )
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# =============================================================================
# OPTIONAL TYPED IMPORTS - Playwright
# =============================================================================
try:
    from playwright.async_api import (
        TimeoutError as PlaywrightTimeoutError,
        Error as PlaywrightError,
    )
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# =============================================================================
# TYPED EXCEPTION TUPLES (empty if library not installed)
# =============================================================================

def _get_selenium_exceptions() -> Tuple[Tuple[Type[Exception], ...], Tuple[Type[Exception], ...]]:
    """Get Selenium permanent and transient exception tuples."""
    if not SELENIUM_AVAILABLE:
        return ((), ())
    
    permanent = (
        InvalidSelectorException,      # Bad CSS/XPath syntax - fix the selector
        InvalidSessionIdException,     # Session dead - need new session
        NoSuchWindowException,         # Window closed - can't recover
        InvalidArgumentException,      # Bad argument - fix the code
        InvalidCookieDomainException,  # Wrong domain - fix the code
        NoSuchCookieException,         # Cookie doesn't exist - fix the code
        InvalidCoordinatesException,   # Bad coordinates - fix the code
    )
    
    transient = (
        NoSuchElementException,        # Element not found - might appear
        StaleElementReferenceException,# DOM changed - re-find element
        TimeoutException,              # Timeout - might succeed on retry
        ElementNotInteractableException,# Not ready - wait and retry
        ElementNotVisibleException,    # Not visible yet - wait and retry
        ElementClickInterceptedException,# Overlay blocking - might clear
        MoveTargetOutOfBoundsException,# Viewport issue - might scroll
    )
    
    return (permanent, transient)


def _get_playwright_exceptions() -> Tuple[Tuple[Type[Exception], ...], Tuple[Type[Exception], ...]]:
    """Get Playwright permanent and transient exception tuples."""
    if not PLAYWRIGHT_AVAILABLE:
        return ((), ())
    
    # Playwright has fewer typed exceptions - most info is in error message
    permanent: Tuple[Type[Exception], ...] = ()  # Playwright errors are mostly message-based
    transient = (PlaywrightTimeoutError,)  # Timeout is always transient
    
    return (permanent, transient)


# Build exception tuples at module load
_selenium_permanent, _selenium_transient = _get_selenium_exceptions()
_playwright_permanent, _playwright_transient = _get_playwright_exceptions()

# Combine all typed exceptions
TYPED_PERMANENT_EXCEPTIONS: Tuple[Type[Exception], ...] = _selenium_permanent + _playwright_permanent
TYPED_TRANSIENT_EXCEPTIONS: Tuple[Type[Exception], ...] = _selenium_transient + _playwright_transient + (
    # Python built-in transient exceptions
    TimeoutError,       # Generic timeout
    ConnectionError,    # Network connection issues
    ConnectionResetError,
    ConnectionRefusedError,
    ConnectionAbortedError,
    BrokenPipeError,
)


# =============================================================================
# PATTERN FALLBACK - For errors that lose type information
# =============================================================================

# Permanent patterns - errors that won't resolve by retrying
BROWSER_PERMANENT_PATTERNS = [
    # Session/driver issues
    "invalid session",
    "session not created",
    "session invalid or expired",
    "session deleted",
    "no active session",
    "could not start session",
    "not initialized",
    # Browser/driver not found or closed
    "webdriver not found",
    "browser executable not found",
    "browser not supported",
    "not reachable",
    "connection refused",  # Driver/browser closed - more specific than "connection"
    # Invalid selectors (fix the selector, don't retry)
    "invalid selector",
    "invalid xpath",
    "invalid css",
    "malformed",  # Catches "malformed selector", "css selector is malformed", etc.
    "invalid element locator",
    # Invalid configuration
    "invalid argument",
    "invalid parameter",
    "invalid browser configuration",
    "invalid url format",
    "invalid javascript syntax",
    "invalid form element",
    # Unsupported operations
    "unsupported",
    "not supported",
    # Click interception (needs different strategy, not retries)
    "click intercepted",
    "element is obscured",
]

# Transient patterns - errors that might resolve on retry or need AI help
BROWSER_TRANSIENT_PATTERNS = [
    # Element state issues (timing)
    "element not found",
    "no such element",
    "not found",
    "not visible",
    "not clickable",
    "not interactable",
    "stale element",
    "element is not attached",
    "detached from dom",
    # Timeouts
    "timeout",
    "timed out",
    # Network issues
    "connection",
    "network",
    "server error",
    # Generic driver errors
    "webdriver error",
]


class BrowserErrorClassifier(ErrorClassifier):
    """Browser error classifier using typed exceptions with pattern fallback.
    
    Classification uses a priority system:
    1. Lamia typed errors (highest priority - explicitly set by adapters)
    2. Selenium typed exceptions (if library installed)
    3. Playwright typed exceptions (if library installed)
    4. Pattern matching (fallback for wrapped/unknown errors)
    
    Most browser errors are TRANSIENT because:
    - Elements might appear after page load/animation
    - DOM changes can be resolved by re-finding elements
    - Timeouts might succeed on retry
    - AI-powered selector resolution can fix element-not-found errors
    
    PERMANENT errors are rare and indicate:
    - Bad selector syntax (fix the code)
    - Dead browser session (need restart)
    - Unsupported browser/feature (can't fix by retrying)
    """
    
    def classify_error(self, error: Exception) -> ErrorCategory:
        """Classify browser errors using typed exceptions with pattern fallback.
        
        Args:
            error: Exception from browser operation
            
        Returns:
            ErrorCategory for retry behavior
        """
        # Priority 1: Lamia typed errors (explicitly set by adapters)
        if isinstance(error, ExternalOperationPermanentError):
            return ErrorCategory.PERMANENT
        if isinstance(error, ExternalOperationTransientError):
            return ErrorCategory.TRANSIENT
        if isinstance(error, ExternalOperationRateLimitError):
            return ErrorCategory.RATE_LIMIT
        
        # Priority 2: Typed Selenium/Playwright exceptions
        # This works when exceptions bubble up directly from the library
        if TYPED_PERMANENT_EXCEPTIONS and isinstance(error, TYPED_PERMANENT_EXCEPTIONS):
            return ErrorCategory.PERMANENT
        if TYPED_TRANSIENT_EXCEPTIONS and isinstance(error, TYPED_TRANSIENT_EXCEPTIONS):
            return ErrorCategory.TRANSIENT
        
        # Priority 3: Pattern matching fallback
        # Needed when:
        # - Errors wrapped in generic Exception
        # - Custom exceptions from third-party code
        # - Errors serialized across process boundaries
        # - JavaScript execution errors (message-based)
        error_msg = str(error).lower()
        
        if self._is_permanent_pattern(error_msg):
            return ErrorCategory.PERMANENT
        
        if self._is_transient_pattern(error_msg):
            return ErrorCategory.TRANSIENT
        
        # Default to TRANSIENT (conservative - allows retry/AI resolution)
        return ErrorCategory.TRANSIENT
    
    def _is_permanent_pattern(self, error_msg: str) -> bool:
        """Check if error message matches permanent patterns."""
        return any(pattern in error_msg for pattern in BROWSER_PERMANENT_PATTERNS)
    
    def _is_transient_pattern(self, error_msg: str) -> bool:
        """Check if error message matches transient patterns."""
        return any(pattern in error_msg for pattern in BROWSER_TRANSIENT_PATTERNS)
