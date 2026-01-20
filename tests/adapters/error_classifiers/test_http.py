"""Comprehensive tests for HTTP error classifier."""

import pytest
from unittest.mock import Mock
from aiohttp import ClientResponseError as AiohttpError, RequestInfo
from multidict import CIMultiDict
from requests import HTTPError as RequestsError
from requests.models import Response
from yarl import URL

from lamia.adapters.error_classifiers.http import HttpErrorClassifier
from lamia.adapters.error_classifiers.base import ErrorClassifier
from lamia.adapters.error_classifiers.categories import ErrorCategory

_DUMMY_URL = URL('http://example.com')
_DUMMY_REQUEST_INFO = RequestInfo(
    url=_DUMMY_URL, method='GET', headers=CIMultiDict(), real_url=_DUMMY_URL
)


def make_aiohttp_error(status: int, message: str = "") -> AiohttpError:
    """Create an aiohttp ClientResponseError for testing."""
    return AiohttpError(_DUMMY_REQUEST_INFO, (), status=status, message=message)


def make_requests_error(status_code: int, message: str = "") -> RequestsError:
    """Create a requests HTTPError for testing."""
    resp = Response()
    resp.status_code = status_code
    return RequestsError(message, response=resp)


class TestHttpErrorClassifierInterface:
    """Test HttpErrorClassifier interface and inheritance."""
    
    def test_inherits_from_error_classifier(self):
        """Test that HttpErrorClassifier inherits from ErrorClassifier."""
        classifier = HttpErrorClassifier()
        assert isinstance(classifier, ErrorClassifier)
    
    def test_implements_classify_error_method(self):
        """Test that HttpErrorClassifier implements classify_error."""
        assert hasattr(HttpErrorClassifier, 'classify_error')
        assert callable(HttpErrorClassifier.classify_error)
    
    def test_can_instantiate(self):
        """Test that HttpErrorClassifier can be instantiated."""
        classifier = HttpErrorClassifier()
        assert classifier is not None
        assert isinstance(classifier, HttpErrorClassifier)


class TestHttpErrorClassifierRateLimitDetection:
    """Test HTTP error classifier rate limit detection."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = HttpErrorClassifier()
    
    def test_http_429_status_code(self):
        """Test detection of HTTP 429 Too Many Requests."""
        error = make_aiohttp_error(429)
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.RATE_LIMIT
    
    def test_requests_style_429_status(self):
        """Test detection of 429 status in requests-style error."""
        error = make_requests_error(429)
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.RATE_LIMIT
    
    def test_rate_limit_message_patterns(self):
        """Test detection of rate limit via message patterns."""
        rate_limit_messages = [
            "rate limit exceeded",
            "too many requests",
            "quota exceeded",
            "ratelimit reached",
            "Rate Limit: API calls per minute exceeded"
        ]
        
        for message in rate_limit_messages:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.RATE_LIMIT, f"Failed for message: {message}"
    
    def test_rate_limit_case_insensitive(self):
        """Test that rate limit detection is case insensitive."""
        case_variations = [
            "RATE LIMIT EXCEEDED",
            "Rate Limit Exceeded", 
            "rate LIMIT exceeded",
            "TOO MANY REQUESTS",
            "Too Many Requests",
            "QUOTA EXCEEDED"
        ]
        
        for message in case_variations:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.RATE_LIMIT, f"Failed for message: {message}"
    
    def test_429_in_error_message_pattern_matching(self):
        """Test 429 detection via regex pattern matching in message."""
        messages_with_429 = [
            "HTTP 429 Too Many Requests",
            "Server returned 429",
            "Error 429: Rate limit exceeded",
            "Request failed with status 429"
        ]
        
        for message in messages_with_429:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.RATE_LIMIT, f"Failed for message: {message}"


class TestHttpErrorClassifierPermanentErrors:
    """Test HTTP error classifier permanent error detection."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = HttpErrorClassifier()
    
    def test_4xx_status_codes_permanent(self):
        """Test that 4xx status codes (except 429) are classified as permanent."""
        permanent_status_codes = [400, 401, 403, 404, 405, 406, 408, 409, 410, 422, 451]
        
        for status_code in permanent_status_codes:
            # aiohttp style
            error = make_aiohttp_error(status_code)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for status {status_code}"
            
            # requests style
            error = make_requests_error(status_code)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for requests-style status {status_code}"
    
    def test_4xx_pattern_matching_in_message(self):
        """Test 4xx detection via pattern matching in error message."""
        permanent_messages = [
            "HTTP 400 Bad Request",
            "401 Unauthorized access",
            "Server returned 403 Forbidden",
            "Error 404: Not Found",
            "405 Method Not Allowed"
        ]
        
        for message in permanent_messages:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for message: {message}"
    
    def test_permanent_error_message_patterns(self):
        """Test detection of permanent errors via message patterns."""
        permanent_messages = [
            "unauthorized access",
            "forbidden resource",
            "invalid api key",
            "authentication failed",
            "invalid request format",
            "bad request syntax",
            "resource not found",
            "endpoint not found"
        ]
        
        for message in permanent_messages:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for message: {message}"
    
    def test_permanent_errors_exclude_429(self):
        """Test that 429 is not classified as permanent despite being 4xx."""
        # Direct 429 status
        error = make_aiohttp_error(429)
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.RATE_LIMIT
        
        # 429 in message with other 4xx indicators
        error = Exception("HTTP 429 Too Many Requests - rate limit exceeded")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.RATE_LIMIT


class TestHttpErrorClassifierTransientErrors:
    """Test HTTP error classifier transient error detection."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = HttpErrorClassifier()
    
    def test_5xx_status_codes_transient(self):
        """Test that 5xx status codes are classified as transient."""
        transient_status_codes = [500, 501, 502, 503, 504, 505, 507, 508, 509, 510, 511]
        
        for status_code in transient_status_codes:
            # aiohttp style
            error = make_aiohttp_error(status_code)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for status {status_code}"
            
            # requests style  
            error = make_requests_error(status_code)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for requests-style status {status_code}"
    
    def test_5xx_pattern_matching_in_message(self):
        """Test 5xx detection via pattern matching in error message."""
        transient_messages = [
            "HTTP 500 Internal Server Error",
            "502 Bad Gateway",
            "Server returned 503 Service Unavailable",
            "Error 504: Gateway Timeout"
        ]
        
        for message in transient_messages:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"
    
    def test_connection_and_timeout_exceptions(self):
        """Test that connection and timeout exceptions are transient."""
        transient_exceptions = [
            ConnectionError("Connection failed"),
            TimeoutError("Request timed out"),
            ConnectionResetError("Connection reset by peer"),
            ConnectionRefusedError("Connection refused"),
            ConnectionAbortedError("Connection aborted")
        ]
        
        for error in transient_exceptions:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for error: {type(error).__name__}"
    
    def test_transient_error_message_patterns(self):
        """Test detection of transient errors via message patterns."""
        transient_messages = [
            "connection timeout occurred", 
            "network connection failed",
            "server error - please retry",
            "service unavailable temporarily", 
            "connection reset by peer",
            "network is unreachable"
        ]
        
        for message in transient_messages:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"
    
    def test_connection_error_type_names(self):
        """Test detection of transient errors via error type names."""
        # Create mock errors with specific type names
        connection_error_types = [
            "ConnectorError",
            "TimeoutError", 
            "ConnectionError",
            "NetworkTimeout"
        ]
        
        for error_type in connection_error_types:
            # Create a mock error with the specific type name
            error = Mock()
            error.__class__.__name__ = error_type
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for error type: {error_type}"


class TestHttpErrorClassifierStatusCodeEdgeCases:
    """Test HTTP error classifier edge cases for status codes."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = HttpErrorClassifier()
    
    def test_missing_status_attributes(self):
        """Test handling of errors without status attributes."""
        error_without_status = Exception("Generic network error")
        result = self.classifier.classify_error(error_without_status)
        # Should default to transient for unknown HTTP errors
        assert result == ErrorCategory.TRANSIENT
    
    def test_invalid_status_attributes(self):
        """Test handling of errors with invalid status attributes.""" 
        # Error with non-numeric status
        error = Mock()
        error.status = "not_a_number"
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.TRANSIENT
        
        # Error with None status
        error = Mock()
        error.status = None
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.TRANSIENT
    
    def test_nested_response_object_errors(self):
        """Test handling of complex nested response objects."""
        # Error with nested response but no status_code
        error = Mock()
        error.response = Mock()
        # Deliberately not setting status_code
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.TRANSIENT
        
        # Error with response that has invalid status_code
        error = Mock()
        error.response = Mock()
        error.response.status_code = "invalid"
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.TRANSIENT
    
    def test_both_status_and_response_attributes(self):
        """Test error with both status and response.status_code attributes."""
        # Should prefer status attribute (aiohttp style)
        error = Mock()
        error.status = 503
        error.response = Mock()
        error.response.status_code = 404
        
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.TRANSIENT  # Should use error.status (503)
    
    def test_unusual_status_codes(self):
        """Test handling of unusual or non-standard status codes."""
        unusual_codes = [0, 199, 299, 399, 600, 999, -1]
        
        for code in unusual_codes:
            error = Mock() 
            error.status = code
            result = self.classifier.classify_error(error)
            assert isinstance(result, ErrorCategory)
            # Should handle gracefully without crashing


class TestHttpErrorClassifierMultiLibrarySupport:
    """Test HTTP error classifier support for different HTTP libraries."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = HttpErrorClassifier()
    
    def test_aiohttp_style_errors(self):
        """Test classification of aiohttp-style errors."""
        error = make_aiohttp_error(502)
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.TRANSIENT
    
    def test_requests_style_errors(self):
        """Test classification of requests-style errors."""
        error = make_requests_error(401)
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.PERMANENT
    
    def test_httpx_style_errors(self):
        """Test classification of httpx-style errors via message pattern."""
        # httpx not imported, so test via message pattern
        error = Exception("HTTP 429 Too Many Requests")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.RATE_LIMIT
    
    def test_urllib_style_errors(self):
        """Test classification of urllib-style errors."""
        # urllib HTTPError - typically has code attribute
        error = Mock()
        error.code = 503
        error.__class__.__name__ = "HTTPError"
        
        # Even without status/response.status_code, pattern matching might catch it
        result = self.classifier.classify_error(error) 
        # Should handle gracefully
        assert isinstance(result, ErrorCategory)


class TestHttpErrorClassifierPriorityAndDefaults:
    """Test HTTP error classifier decision priority and defaults."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = HttpErrorClassifier()
    
    def test_rate_limit_takes_priority_over_permanent(self):
        """Test that rate limit detection takes priority over permanent classification."""
        # Error that could be both permanent (4xx) and rate limit
        error = make_aiohttp_error(429)  # 4xx but special case for rate limiting
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.RATE_LIMIT
    
    def test_permanent_takes_priority_over_transient(self):
        """Test that permanent classification takes priority over transient."""
        # Error message that contains both permanent and transient indicators
        error = Exception("401 Unauthorized - connection timeout occurred")
        
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.PERMANENT  # Should prioritize 401/unauthorized
    
    def test_default_classification_for_unknown_errors(self):
        """Test default classification for unknown HTTP errors."""
        unknown_errors = [
            Exception("Unknown HTTP error"),
            Exception("Mysterious network issue"),
            ValueError("Non-HTTP related error"),
            RuntimeError("Generic runtime error")
        ]
        
        for error in unknown_errors:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT  # Should default to transient (safer to retry)
    
    def test_classification_consistency(self):
        """Test that classification is consistent for the same error."""
        error = ConnectionError("Network connection failed")
        
        # Should return same result multiple times
        result1 = self.classifier.classify_error(error)
        result2 = self.classifier.classify_error(error)
        result3 = self.classifier.classify_error(error)
        
        assert result1 == result2 == result3
        assert result1 == ErrorCategory.TRANSIENT
    
    def test_empty_error_message_handling(self):
        """Test handling of errors with empty messages."""
        empty_message_errors = [
            Exception(""),
            ConnectionError(""),
            TimeoutError(""),
            ValueError("")
        ]
        
        for error in empty_message_errors:
            result = self.classifier.classify_error(error)
            assert isinstance(result, ErrorCategory)
            # Should handle gracefully without crashing


class TestHttpErrorClassifierComplexScenarios:
    """Test HTTP error classifier complex real-world scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = HttpErrorClassifier()
    
    def test_mixed_error_indicators(self):
        """Test errors with mixed classification indicators."""
        # Error that mentions multiple status codes
        mixed_error = Exception("Request failed: got 500, retried and got 401")
        result = self.classifier.classify_error(mixed_error)
        # Should classify based on first/strongest indicator
        assert isinstance(result, ErrorCategory)
    
    def test_api_gateway_errors(self):
        """Test classification of API Gateway specific errors."""
        gateway_errors = [
            Exception("502 Bad Gateway - upstream server error"),
            Exception("504 Gateway Timeout - upstream timeout"),
            Exception("503 Service Unavailable - rate limit exceeded"),  # Should be RATE_LIMIT
        ]
        
        expected = [ErrorCategory.TRANSIENT, ErrorCategory.TRANSIENT, ErrorCategory.RATE_LIMIT]
        
        for error, expected_category in zip(gateway_errors, expected):
            result = self.classifier.classify_error(error)
            assert result == expected_category
    
    def test_cloud_provider_specific_errors(self):
        """Test classification of cloud provider specific error messages."""
        cloud_errors = [
            Exception("AWS: Throttling Exception - too many requests"),
            Exception("GCP: quotaExceeded - API calls quota exceeded"),
            Exception("Azure: TooManyRequests - rate limit exceeded")
        ]
        
        for error in cloud_errors:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.RATE_LIMIT
    
    def test_authentication_vs_authorization_errors(self):
        """Test distinction between authentication and authorization errors."""
        auth_errors = [
            (Exception("401 Unauthorized - invalid token"), ErrorCategory.PERMANENT),
            (Exception("403 Forbidden - insufficient permissions"), ErrorCategory.PERMANENT),
            (Exception("Authentication required"), ErrorCategory.PERMANENT),
            (Exception("Invalid API key provided"), ErrorCategory.PERMANENT)
        ]
        
        for error, expected_category in auth_errors:
            result = self.classifier.classify_error(error)
            assert result == expected_category
    
    def test_network_infrastructure_errors(self):
        """Test classification of network infrastructure errors."""
        network_errors = [
            Exception("Connection refused by server"),
            Exception("Network unreachable"), 
            Exception("DNS resolution failed"),
            Exception("SSL handshake failed"),
            Exception("Connection reset by peer")
        ]
        
        for error in network_errors:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT
    
    def test_unicode_and_special_characters_in_errors(self):
        """Test handling of Unicode and special characters in error messages.""" 
        unicode_errors = [
            Exception("HTTP 429: \u592a\u591a\u8bf7\u6c42 (too many requests)"),
            Exception("500 \u0441\u0435\u0440\u0432\u0435\u0440\u043d\u0430\u044f \u043e\u0448\u0438\u0431\u043a\u0430"),
            Exception("Rate limit exceeded \ud83d\udcca"),
            Exception("Network error \u26a0\ufe0f")
        ]
        
        expected = [ErrorCategory.RATE_LIMIT, ErrorCategory.TRANSIENT, ErrorCategory.RATE_LIMIT, ErrorCategory.TRANSIENT]
        
        for error, expected_category in zip(unicode_errors, expected):
            result = self.classifier.classify_error(error)
            assert result == expected_category