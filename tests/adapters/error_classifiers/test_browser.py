"""Comprehensive tests for Browser error classifier."""

import pytest
from unittest.mock import Mock
from lamia.adapters.error_classifiers.browser import BrowserErrorClassifier
from lamia.adapters.error_classifiers.base import ErrorClassifier  
from lamia.adapters.error_classifiers.categories import ErrorCategory
from lamia.errors import ExternalOperationPermanentError, ExternalOperationTransientError, ExternalOperationRateLimitError


class TestBrowserErrorClassifierInterface:
    """Test BrowserErrorClassifier interface and inheritance."""
    
    def test_inherits_from_error_classifier(self):
        """Test that BrowserErrorClassifier inherits from ErrorClassifier."""
        classifier = BrowserErrorClassifier()
        assert isinstance(classifier, ErrorClassifier)
    
    def test_implements_classify_error_method(self):
        """Test that BrowserErrorClassifier implements classify_error."""
        assert hasattr(BrowserErrorClassifier, 'classify_error')
        assert callable(BrowserErrorClassifier.classify_error)
    
    def test_can_instantiate(self):
        """Test that BrowserErrorClassifier can be instantiated."""
        classifier = BrowserErrorClassifier()
        assert classifier is not None
        assert isinstance(classifier, BrowserErrorClassifier)


class TestBrowserErrorClassifierExplicitErrorTypes:
    """Test BrowserErrorClassifier handling of explicit error types."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = BrowserErrorClassifier()
    
    def test_explicit_permanent_error(self):
        """Test explicit permanent error classification."""
        error = ExternalOperationPermanentError("Session invalid")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.PERMANENT
    
    def test_explicit_transient_error(self):
        """Test explicit transient error classification."""
        error = ExternalOperationTransientError("Element not found")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.TRANSIENT
    
    def test_explicit_rate_limit_error(self):
        """Test explicit rate limit error classification."""
        error = ExternalOperationRateLimitError("Too many requests")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.RATE_LIMIT
    
    def test_explicit_error_takes_precedence(self):
        """Test that explicit error types take precedence over message patterns."""
        # Error with permanent type but transient-like message
        error = ExternalOperationPermanentError("timeout occurred")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.PERMANENT
        
        # Error with transient type but permanent-like message  
        error = ExternalOperationTransientError("session not created")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.TRANSIENT


class TestBrowserErrorClassifierPermanentErrors:
    """Test BrowserErrorClassifier permanent error detection."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = BrowserErrorClassifier()
    
    def test_browser_initialization_errors(self):
        """Test permanent browser initialization errors."""
        initialization_errors = [
            "browser not initialized",
            "driver not initialized", 
            "Browser not supported",
            "Chrome not reachable",
            "WebDriver not found"
        ]
        
        for message in initialization_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for message: {message}"
    
    def test_session_errors(self):
        """Test permanent session-related errors."""
        session_errors = [
            "invalid session id",
            "session not created", 
            "session deleted by user",
            "No active session",
            "Session invalid or expired"
        ]
        
        for message in session_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for message: {message}"
    
    def test_browser_capability_errors(self):
        """Test permanent browser capability and configuration errors."""
        capability_errors = [
            "browser not supported on this platform",
            "invalid browser configuration", 
            "unsupported browser version",
            "browser capabilities not supported"
        ]
        
        for message in capability_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for message: {message}"
    
    def test_selector_syntax_errors(self):
        """Test permanent selector syntax errors."""
        selector_errors = [
            "invalid selector syntax",
            "malformed selector expression",
            "invalid xpath syntax",
            "css selector is malformed"
        ]
        
        for message in selector_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for message: {message}"
    
    def test_invalid_argument_errors(self):
        """Test permanent invalid argument errors."""
        argument_errors = [
            "invalid argument provided",
            "invalid parameter value",
            "unsupported action type",
            "invalid element locator"
        ]
        
        for message in argument_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for message: {message}"
    
    def test_connection_refused_errors(self):
        """Test permanent connection refused errors (browser/driver closed)."""
        connection_errors = [
            "connection refused to driver",
            "driver connection refused",
            "browser connection refused"
        ]
        
        for message in connection_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for message: {message}"
    
    def test_element_click_intercepted_errors(self):
        """Test permanent element click intercepted errors."""
        click_intercepted_errors = [
            "element click intercepted by modal",
            "click intercepted by overlay",
            "element is obscured by another element"
        ]
        
        for message in click_intercepted_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for message: {message}"
    
    def test_permanent_error_case_insensitive(self):
        """Test that permanent error detection is case insensitive."""
        case_variations = [
            "SESSION NOT CREATED",
            "Invalid Session ID",
            "BROWSER NOT SUPPORTED",
            "Chrome Not Reachable",
            "INVALID SELECTOR SYNTAX"
        ]
        
        for message in case_variations:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for message: {message}"


class TestBrowserErrorClassifierTransientErrors:
    """Test BrowserErrorClassifier transient error detection."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = BrowserErrorClassifier()
    
    def test_element_not_found_errors(self):
        """Test transient element not found errors."""
        element_errors = [
            "element not found on page",
            "no such element exception",
            "element not located",
            "unable to find element"
        ]
        
        for message in element_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"
    
    def test_element_visibility_errors(self):
        """Test transient element visibility errors."""
        visibility_errors = [
            "element not visible on page",
            "element is not displayed", 
            "element not clickable at coordinates",
            "element is not interactable",
            "element not attached to DOM"
        ]
        
        for message in visibility_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"
    
    def test_timing_and_timeout_errors(self):
        """Test transient timing and timeout errors."""
        timeout_errors = [
            "element wait timeout",
            "page load timeout exceeded",
            "script execution timeout",
            "implicit wait timeout",
            "explicit wait timeout"
        ]
        
        for message in timeout_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"
    
    def test_stale_element_errors(self):
        """Test transient stale element errors."""
        stale_errors = [
            "stale element reference",
            "element no longer attached to DOM",
            "stale element exception", 
            "element reference is stale"
        ]
        
        for message in stale_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"
    
    def test_network_and_connection_errors(self):
        """Test transient network and connection errors."""
        network_errors = [
            "network connection lost",
            "connection reset during navigation",
            "temporary network error",
            "dns resolution failed"
        ]
        
        for message in network_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"
    
    def test_server_errors(self):
        """Test transient server errors."""
        server_errors = [
            "internal server error",
            "service temporarily unavailable", 
            "server returned 503",
            "upstream server error"
        ]
        
        for message in server_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"
    
    def test_webdriver_errors(self):
        """Test transient webdriver errors."""
        webdriver_errors = [
            "webdriver connection timeout",
            "webdriver command failed",
            "webdriver communication error",
            "driver process crashed"
        ]
        
        for message in webdriver_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"
    
    def test_transient_error_case_insensitive(self):
        """Test that transient error detection is case insensitive."""
        case_variations = [
            "ELEMENT NOT FOUND",
            "Element Not Visible",
            "TIMEOUT EXCEEDED", 
            "Stale Element Reference",
            "WEBDRIVER ERROR"
        ]
        
        for message in case_variations:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"


class TestBrowserErrorClassifierPlaywrightErrors:
    """Test BrowserErrorClassifier with Playwright-specific errors."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = BrowserErrorClassifier()
    
    def test_playwright_timeout_errors(self):
        """Test Playwright timeout error classification."""
        playwright_timeouts = [
            "Timeout 30000ms exceeded waiting for selector",
            "Page did not load within timeout",
            "Element not found within specified timeout",
            "Navigation timeout exceeded"
        ]
        
        for message in playwright_timeouts:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"
    
    def test_playwright_browser_connection_errors(self):
        """Test Playwright browser connection error classification."""
        playwright_connection_errors = [
            "Browser process crashed",
            "Lost connection to browser",
            "Browser executable not found",  # Permanent
            "Failed to launch browser process"
        ]
        
        expected = [ErrorCategory.TRANSIENT, ErrorCategory.TRANSIENT, ErrorCategory.PERMANENT, ErrorCategory.TRANSIENT]
        
        for message, expected_category in zip(playwright_connection_errors, expected):
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for message: {message}"
    
    def test_playwright_page_errors(self):
        """Test Playwright page-related error classification."""
        playwright_page_errors = [
            "Page closed before operation completed",
            "Page was closed",
            "Navigation was cancelled",
            "Frame was detached"
        ]
        
        for message in playwright_page_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"


class TestBrowserErrorClassifierSeleniumErrors:
    """Test BrowserErrorClassifier with Selenium-specific errors."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = BrowserErrorClassifier()
    
    def test_selenium_webdriver_exceptions(self):
        """Test Selenium WebDriver exception classification."""
        selenium_exceptions = [
            "WebDriverException: chrome not reachable",  # Permanent
            "NoSuchElementException: Unable to locate element",  # Transient
            "TimeoutException: Timeout waiting for page load",  # Transient
            "StaleElementReferenceException: Element is stale",  # Transient
            "InvalidSessionIdException: Invalid session",  # Permanent
            "SessionNotCreatedException: Could not start session"  # Permanent
        ]
        
        expected = [
            ErrorCategory.PERMANENT, ErrorCategory.TRANSIENT, ErrorCategory.TRANSIENT,
            ErrorCategory.TRANSIENT, ErrorCategory.PERMANENT, ErrorCategory.PERMANENT
        ]
        
        for message, expected_category in zip(selenium_exceptions, expected):
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for message: {message}"
    
    def test_selenium_element_interaction_errors(self):
        """Test Selenium element interaction error classification."""
        interaction_errors = [
            "ElementNotInteractableException: Element is not interactable",
            "ElementClickInterceptedException: Click intercepted",  # Permanent
            "InvalidElementStateException: Element in invalid state",
            "MoveTargetOutOfBoundsException: Move target out of bounds"
        ]
        
        expected = [ErrorCategory.TRANSIENT, ErrorCategory.PERMANENT, ErrorCategory.TRANSIENT, ErrorCategory.TRANSIENT]
        
        for message, expected_category in zip(interaction_errors, expected):
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for message: {message}"


class TestBrowserErrorClassifierEdgeCases:
    """Test BrowserErrorClassifier edge cases and error handling."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = BrowserErrorClassifier()
    
    def test_empty_error_message(self):
        """Test handling of errors with empty messages."""
        empty_errors = [
            Exception(""),
            RuntimeError(""),
            ValueError("")
        ]
        
        for error in empty_errors:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT  # Default for browsers
    
    def test_none_error_handling(self):
        """Test handling of None error."""
        try:
            result = self.classifier.classify_error(None)
            assert result == ErrorCategory.TRANSIENT
        except (TypeError, AttributeError):
            # Acceptable if implementation doesn't handle None
            pass
    
    def test_mixed_pattern_errors(self):
        """Test errors that match multiple patterns."""
        mixed_pattern_errors = [
            "session not created due to timeout",  # Permanent + transient patterns
            "invalid selector caused connection error",  # Permanent + transient patterns
            "element not found - browser not supported"  # Transient + permanent patterns
        ]
        
        for message in mixed_pattern_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert isinstance(result, ErrorCategory)
            # Should prioritize permanent over transient based on implementation
    
    def test_unicode_error_messages(self):
        """Test handling of Unicode error messages."""
        unicode_errors = [
            Exception("\u5143\u7d20\u672a\u627e\u5230 (element not found)"),
            Exception("\u8d85\u65f6\u9519\u8bef (timeout error)"),
            Exception("\u6d4f\u89c8\u5668\u9519\u8bef \ud83d\ude31")
        ]
        
        for error in unicode_errors:
            result = self.classifier.classify_error(error)
            assert isinstance(result, ErrorCategory)
    
    def test_very_long_error_messages(self):
        """Test handling of very long error messages."""
        long_message = "element not found " * 1000  # Very long message
        error = Exception(long_message)
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.TRANSIENT


class TestBrowserErrorClassifierDefaultBehavior:
    """Test BrowserErrorClassifier default behavior and decision priority."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = BrowserErrorClassifier()
    
    def test_default_classification_for_unknown_errors(self):
        """Test default classification for unknown browser errors."""
        unknown_errors = [
            Exception("Unknown browser error"),
            Exception("Mysterious automation failure"), 
            ValueError("Non-browser related error"),
            RuntimeError("Generic runtime error")
        ]
        
        for error in unknown_errors:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT  # Should default to transient (conservative approach)
    
    def test_permanent_takes_priority_over_transient(self):
        """Test that permanent classification takes priority over transient."""
        # Error with both permanent and transient indicators
        mixed_error = Exception("invalid session id - element not found")
        result = self.classifier.classify_error(mixed_error)
        assert result == ErrorCategory.PERMANENT  # Should prioritize permanent
    
    def test_no_rate_limiting_classification(self):
        """Test that browser errors don't classify as RATE_LIMIT by default."""
        # Browser automation typically doesn't have rate limiting
        potential_rate_limit_messages = [
            "too many requests to page",
            "rate limit exceeded", 
            "quota exceeded for browser"
        ]
        
        for message in potential_rate_limit_messages:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            # Should not be RATE_LIMIT unless explicitly set via error types
            assert result in [ErrorCategory.PERMANENT, ErrorCategory.TRANSIENT]
    
    def test_classification_consistency(self):
        """Test that classification is consistent for the same error."""
        error = Exception("element not found on page")
        
        # Should return same result multiple times
        result1 = self.classifier.classify_error(error)
        result2 = self.classifier.classify_error(error)
        result3 = self.classifier.classify_error(error)
        
        assert result1 == result2 == result3
        assert result1 == ErrorCategory.TRANSIENT
    
    def test_browser_specific_vs_generic_errors(self):
        """Test distinction between browser-specific and generic errors."""
        browser_specific_errors = [
            Exception("webdriver session timeout"),
            Exception("chrome browser not reachable"),
            Exception("playwright page closed")
        ]
        
        generic_errors = [
            Exception("network connection failed"),
            Exception("server returned 500"),
            Exception("file not found")
        ]
        
        # All should be classified (browser classifier handles both)
        for error in browser_specific_errors + generic_errors:
            result = self.classifier.classify_error(error)
            assert isinstance(result, ErrorCategory)


class TestBrowserErrorClassifierIntegrationScenarios:
    """Test BrowserErrorClassifier with realistic integration scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = BrowserErrorClassifier()
    
    def test_page_load_failure_scenarios(self):
        """Test classification of page load failure scenarios."""
        page_load_errors = [
            ("Page load timeout after 30s", ErrorCategory.TRANSIENT),
            ("DNS resolution failed for domain", ErrorCategory.TRANSIENT),
            ("Connection refused by target server", ErrorCategory.PERMANENT),
            ("Invalid URL format provided", ErrorCategory.PERMANENT),
            ("SSL certificate verification failed", ErrorCategory.TRANSIENT)
        ]
        
        for message, expected_category in page_load_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for message: {message}"
    
    def test_form_interaction_errors(self):
        """Test classification of form interaction errors."""
        form_errors = [
            ("Input element not interactable", ErrorCategory.TRANSIENT),
            ("Element click intercepted by modal", ErrorCategory.PERMANENT),
            ("Form submission timeout", ErrorCategory.TRANSIENT),
            ("Invalid form element selector", ErrorCategory.PERMANENT)
        ]
        
        for message, expected_category in form_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for message: {message}"
    
    def test_javascript_execution_errors(self):
        """Test classification of JavaScript execution errors."""
        js_errors = [
            ("Script execution timeout exceeded", ErrorCategory.TRANSIENT),
            ("JavaScript error during execution", ErrorCategory.TRANSIENT),
            ("Invalid JavaScript syntax provided", ErrorCategory.PERMANENT),
            ("Script returned undefined result", ErrorCategory.TRANSIENT)
        ]
        
        for message, expected_category in js_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for message: {message}"
    
    def test_multi_browser_support_scenarios(self):
        """Test classification across different browser types."""
        browser_specific_errors = [
            ("Chrome: session not created", ErrorCategory.PERMANENT),
            ("Firefox: element not found", ErrorCategory.TRANSIENT),
            ("Safari: webdriver timeout", ErrorCategory.TRANSIENT),
            ("Edge: invalid selector syntax", ErrorCategory.PERMANENT)
        ]
        
        for message, expected_category in browser_specific_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for message: {message}"


class TestBrowserErrorClassifierTypedSeleniumExceptions:
    """Test BrowserErrorClassifier handling of actual Selenium exception types."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = BrowserErrorClassifier()
    
    @pytest.fixture
    def selenium_available(self):
        """Check if Selenium is available."""
        try:
            from selenium.common.exceptions import NoSuchElementException
            return True
        except ImportError:
            return False
    
    def test_selenium_no_such_element_exception(self):
        """Test actual Selenium NoSuchElementException is classified as transient."""
        try:
            from selenium.common.exceptions import NoSuchElementException
            error = NoSuchElementException("Element not found")
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT
        except ImportError:
            pytest.skip("Selenium not installed")
    
    def test_selenium_stale_element_reference_exception(self):
        """Test actual Selenium StaleElementReferenceException is classified as transient."""
        try:
            from selenium.common.exceptions import StaleElementReferenceException
            error = StaleElementReferenceException("Element is stale")
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT
        except ImportError:
            pytest.skip("Selenium not installed")
    
    def test_selenium_timeout_exception(self):
        """Test actual Selenium TimeoutException is classified as transient."""
        try:
            from selenium.common.exceptions import TimeoutException
            error = TimeoutException("Timeout waiting for element")
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT
        except ImportError:
            pytest.skip("Selenium not installed")
    
    def test_selenium_element_not_interactable_exception(self):
        """Test actual Selenium ElementNotInteractableException is classified as transient."""
        try:
            from selenium.common.exceptions import ElementNotInteractableException
            error = ElementNotInteractableException("Element not interactable")
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT
        except ImportError:
            pytest.skip("Selenium not installed")
    
    def test_selenium_invalid_selector_exception(self):
        """Test actual Selenium InvalidSelectorException is classified as permanent."""
        try:
            from selenium.common.exceptions import InvalidSelectorException
            error = InvalidSelectorException("Invalid selector syntax")
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT
        except ImportError:
            pytest.skip("Selenium not installed")
    
    def test_selenium_invalid_session_id_exception(self):
        """Test actual Selenium InvalidSessionIdException is classified as permanent."""
        try:
            from selenium.common.exceptions import InvalidSessionIdException
            error = InvalidSessionIdException("Session is invalid")
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT
        except ImportError:
            pytest.skip("Selenium not installed")


class TestBrowserErrorClassifierTypedPlaywrightExceptions:
    """Test BrowserErrorClassifier handling of actual Playwright exception types."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = BrowserErrorClassifier()
    
    def test_playwright_timeout_error(self):
        """Test actual Playwright TimeoutError is classified as transient."""
        try:
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            error = PlaywrightTimeoutError("Timeout waiting for element")
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT
        except ImportError:
            pytest.skip("Playwright not installed")


class TestBrowserErrorClassifierTypedPythonExceptions:
    """Test BrowserErrorClassifier handling of Python built-in exception types."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = BrowserErrorClassifier()
    
    def test_python_timeout_error(self):
        """Test Python built-in TimeoutError is classified as transient."""
        error = TimeoutError("Connection timed out")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.TRANSIENT
    
    def test_python_connection_error(self):
        """Test Python built-in ConnectionError is classified as transient."""
        error = ConnectionError("Connection failed")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.TRANSIENT
    
    def test_python_connection_reset_error(self):
        """Test Python built-in ConnectionResetError is classified as transient."""
        error = ConnectionResetError("Connection reset by peer")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.TRANSIENT
    
    def test_python_connection_refused_error(self):
        """Test Python built-in ConnectionRefusedError is classified as transient."""
        # Note: Python's ConnectionRefusedError is TRANSIENT (network issue)
        # but "connection refused" in message is PERMANENT (driver closed)
        # The typed exception takes priority
        error = ConnectionRefusedError("Connection refused")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.TRANSIENT
    
    def test_python_broken_pipe_error(self):
        """Test Python built-in BrokenPipeError is classified as transient."""
        error = BrokenPipeError("Broken pipe")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.TRANSIENT


class TestBrowserErrorClassifierTypedVsPatternPriority:
    """Test that typed exceptions take priority over pattern matching."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = BrowserErrorClassifier()
    
    def test_typed_transient_beats_permanent_pattern(self):
        """Test typed transient exception beats permanent pattern in message."""
        # ConnectionRefusedError is typed as transient
        # but "connection refused" pattern would be permanent
        error = ConnectionRefusedError("connection refused - driver closed")
        result = self.classifier.classify_error(error)
        # Typed exception wins - ConnectionRefusedError is transient
        assert result == ErrorCategory.TRANSIENT
    
    def test_lamia_error_beats_typed_exception(self):
        """Test Lamia explicit errors beat typed exceptions."""
        # Even if we somehow get an ExternalOperationPermanentError
        # that looks like a transient message, Lamia type wins
        error = ExternalOperationPermanentError("element not found - retry later")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.PERMANENT
    
    def test_pattern_fallback_for_generic_exception(self):
        """Test pattern matching is used for generic Exception."""
        # Generic Exception can't be typed, so patterns are used
        error = Exception("invalid selector syntax")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.PERMANENT
    
    def test_pattern_fallback_for_custom_exception(self):
        """Test pattern matching is used for custom exception classes."""
        class CustomBrowserError(Exception):
            pass
        
        error = CustomBrowserError("element not found")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.TRANSIENT