"""Browser error classifier using typed exceptions with pattern fallback."""

from typing import Tuple, Type

from .base import ErrorClassifier
from .categories import ErrorCategory
from lamia.errors import (
    ExternalOperationPermanentError,
    ExternalOperationTransientError,
    ExternalOperationRateLimitError,
)

# Optional Selenium imports
try:
    from selenium.common.exceptions import (
        InvalidSelectorException,
        InvalidSessionIdException,
        NoSuchWindowException,
        InvalidArgumentException,
        InvalidCookieDomainException,
        NoSuchCookieException,
        InvalidCoordinatesException,
        NoSuchElementException,
        StaleElementReferenceException,
        TimeoutException,
        ElementNotInteractableException,
        ElementNotVisibleException,
        ElementClickInterceptedException,
        MoveTargetOutOfBoundsException,
    )
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# Optional Playwright imports
try:
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


def _get_selenium_exceptions() -> Tuple[Tuple[Type[Exception], ...], Tuple[Type[Exception], ...]]:
    """Get Selenium permanent and transient exception tuples."""
    if not SELENIUM_AVAILABLE:
        return ((), ())
    
    permanent = (
        InvalidSelectorException,
        InvalidSessionIdException,
        NoSuchWindowException,
        InvalidArgumentException,
        InvalidCookieDomainException,
        NoSuchCookieException,
        InvalidCoordinatesException,
    )
    
    transient = (
        NoSuchElementException,
        StaleElementReferenceException,
        TimeoutException,
        ElementNotInteractableException,
        ElementNotVisibleException,
        ElementClickInterceptedException,
        MoveTargetOutOfBoundsException,
    )
    
    return (permanent, transient)


_selenium_permanent, _selenium_transient = _get_selenium_exceptions()
_playwright_transient = (PlaywrightTimeoutError,) if PLAYWRIGHT_AVAILABLE else ()

TYPED_PERMANENT = _selenium_permanent
TYPED_TRANSIENT = _selenium_transient + _playwright_transient + (
    TimeoutError,
    ConnectionError,
    ConnectionResetError,
    ConnectionRefusedError,
    ConnectionAbortedError,
    BrokenPipeError,
)

PERMANENT_PATTERNS = [
    "invalid session", "session not created", "session deleted", "no active session",
    "session invalid", "not initialized", "could not start session",
    "webdriver not found", "browser executable not found", "browser not supported", "not reachable",
    "connection refused",
    "invalid selector", "invalid xpath", "invalid css", "malformed",
    "invalid argument", "invalid parameter", "invalid browser configuration",
    "invalid url format", "invalid javascript syntax", "invalid form element", "invalid element locator",
    "unsupported", "not supported",
    "click intercepted", "element is obscured",
]

TRANSIENT_PATTERNS = [
    "element not found", "no such element", "not found",
    "not visible", "not clickable", "not interactable",
    "stale element", "element is not attached", "detached from dom",
    "timeout", "timed out",
    "connection", "network", "server error",
    "webdriver error",
]


class BrowserErrorClassifier(ErrorClassifier):
    """Browser error classifier using typed exceptions with pattern fallback."""
    
    def classify_error(self, error: Exception) -> ErrorCategory:
        """Classify browser errors."""
        # Lamia typed errors
        if isinstance(error, ExternalOperationPermanentError):
            return ErrorCategory.PERMANENT
        if isinstance(error, ExternalOperationTransientError):
            return ErrorCategory.TRANSIENT
        if isinstance(error, ExternalOperationRateLimitError):
            return ErrorCategory.RATE_LIMIT
        
        # Selenium/Playwright typed exceptions
        if TYPED_PERMANENT and isinstance(error, TYPED_PERMANENT):
            return ErrorCategory.PERMANENT
        if TYPED_TRANSIENT and isinstance(error, TYPED_TRANSIENT):
            return ErrorCategory.TRANSIENT
        
        # Pattern fallback
        error_msg = str(error).lower()
        
        if any(p in error_msg for p in PERMANENT_PATTERNS):
            return ErrorCategory.PERMANENT
        if any(p in error_msg for p in TRANSIENT_PATTERNS):
            return ErrorCategory.TRANSIENT
        
        return ErrorCategory.TRANSIENT
