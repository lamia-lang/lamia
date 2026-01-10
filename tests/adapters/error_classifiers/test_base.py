"""Tests for error classifier base classes."""

import pytest
from unittest.mock import Mock
from lamia.adapters.error_classifiers.base import ErrorClassifier
from lamia.adapters.error_classifiers.categories import ErrorCategory


class TestErrorClassifier:
    """Test ErrorClassifier interface."""
    
    def test_is_abstract(self):
        """Test that ErrorClassifier is abstract."""
        with pytest.raises(TypeError):
            ErrorClassifier()
    
    def test_abstract_methods_exist(self):
        """Test that abstract methods are defined."""
        assert hasattr(ErrorClassifier, 'classify_error')
        assert callable(ErrorClassifier.classify_error)


class MockErrorClassifier(ErrorClassifier):
    """Mock implementation for testing."""
    
    def __init__(self, default_category=ErrorCategory.TRANSIENT):
        self.default_category = default_category
        self.classified_errors = []
    
    def classify_error(self, error):
        self.classified_errors.append(error)
        return self.default_category


class TestErrorClassifierImplementation:
    """Test error classifier implementation through mock."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = MockErrorClassifier()
    
    def test_classify_error_basic(self):
        """Test basic error classification."""
        error = Exception("Test error")
        result = self.classifier.classify_error(error)
        
        assert result == ErrorCategory.TRANSIENT
        assert len(self.classifier.classified_errors) == 1
        assert self.classifier.classified_errors[0][0] == error
        assert self.classifier.classified_errors[0][1] is None
    
    def test_classify_error_with_context(self):
        """Test error classification with context."""
        error = ValueError("Invalid value")
        context = {"operation": "API call", "retry_count": 2}
        
        result = self.classifier.classify_error(error, context)
        
        assert result == ErrorCategory.TRANSIENT
        assert len(self.classifier.classified_errors) == 1
        assert self.classifier.classified_errors[0][1] == context
    
    def test_different_error_types(self):
        """Test classification of different error types."""
        errors = [
            Exception("Generic error"),
            ValueError("Value error"),
            ConnectionError("Connection failed"),
            TimeoutError("Request timed out")
        ]
        
        for error in errors:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT
        
        assert len(self.classifier.classified_errors) == 4
    
    def test_classify_error_different_categories(self):
        """Test classifier with different default categories."""
        categories = [
            ErrorCategory.TRANSIENT,
            ErrorCategory.PERMANENT,
            ErrorCategory.RATE_LIMIT,
            ErrorCategory.AUTHENTICATION
        ]
        
        for category in categories:
            classifier = MockErrorClassifier(default_category=category)
            result = classifier.classify_error(Exception("test"))
            assert result == category


class TestErrorClassifierWithRealExceptions:
    """Test error classifier with real exception types."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = MockErrorClassifier()
    
    def test_connection_errors(self):
        """Test classification of connection-related errors."""
        errors = [
            ConnectionError("Connection refused"),
            ConnectionResetError("Connection reset"),
            ConnectionAbortedError("Connection aborted"),
            ConnectionRefusedError("Connection refused")
        ]
        
        for error in errors:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT
    
    def test_timeout_errors(self):
        """Test classification of timeout errors."""
        import socket
        
        errors = [
            TimeoutError("Operation timed out"),
            socket.timeout("Socket timeout")
        ]
        
        for error in errors:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT
    
    def test_value_errors(self):
        """Test classification of value errors."""
        errors = [
            ValueError("Invalid value"),
            TypeError("Invalid type"),
            AttributeError("Missing attribute")
        ]
        
        for error in errors:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT
    
    def test_permission_errors(self):
        """Test classification of permission errors."""
        errors = [
            PermissionError("Access denied"),
            OSError("Operation not permitted")
        ]
        
        for error in errors:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT


class TestErrorClassifierEdgeCases:
    """Test error classifier edge cases."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = MockErrorClassifier()
    
    def test_classify_none_error(self):
        """Test classification with None error."""
        # Should handle gracefully or raise appropriate error
        try:
            result = self.classifier.classify_error(None)
            # If it doesn't raise, check that it was recorded
            assert len(self.classifier.classified_errors) == 1
            assert self.classifier.classified_errors[0][0] is None
        except (TypeError, AttributeError):
            # Acceptable if implementation doesn't handle None
            pass
    
    def test_classify_string_error(self):
        """Test classification with string instead of exception."""
        error_string = "String error message"
        result = self.classifier.classify_error(error_string)
        
        assert result == ErrorCategory.TRANSIENT
        assert len(self.classifier.classified_errors) == 1
        assert self.classifier.classified_errors[0][0] == error_string
    
    def test_classify_with_complex_context(self):
        """Test classification with complex context data."""
        error = Exception("Test error")
        context = {
            "operation": "database_query",
            "retry_count": 3,
            "timestamp": "2023-01-01T00:00:00Z",
            "user_id": "user123",
            "metadata": {
                "query": "SELECT * FROM users",
                "duration_ms": 5000
            }
        }
        
        result = self.classifier.classify_error(error, context)
        
        assert result == ErrorCategory.TRANSIENT
        assert len(self.classifier.classified_errors) == 1
        assert self.classifier.classified_errors[0][1] == context
    
    def test_classify_with_empty_context(self):
        """Test classification with empty context."""
        error = Exception("Test error")
        empty_contexts = [{}, None, ""]
        
        for context in empty_contexts:
            result = self.classifier.classify_error(error, context)
            assert result == ErrorCategory.TRANSIENT
    
    def test_multiple_classifications_state(self):
        """Test that classifier maintains state across multiple classifications."""
        errors_and_contexts = [
            (ValueError("Error 1"), {"type": "validation"}),
            (ConnectionError("Error 2"), {"type": "network"}),
            (Exception("Error 3"), None),
            (TimeoutError("Error 4"), {"timeout_seconds": 30})
        ]
        
        results = []
        for error, context in errors_and_contexts:
            result = self.classifier.classify_error(error, context)
            results.append(result)
        
        # All should return the default category
        assert all(r == ErrorCategory.TRANSIENT for r in results)
        
        # Should have recorded all classifications
        assert len(self.classifier.classified_errors) == 4
        
        # Verify all errors and contexts were recorded correctly
        for i, (error, context) in enumerate(errors_and_contexts):
            recorded_error, recorded_context = self.classifier.classified_errors[i]
            assert recorded_error == error
            assert recorded_context == context


class TestErrorClassifierDocumentation:
    """Test error classifier documentation and interface compliance."""
    
    def test_base_classifier_docstring(self):
        """Test that base classifier has documentation."""
        assert BaseErrorClassifier.__doc__ is not None
        assert len(BaseErrorClassifier.__doc__.strip()) > 0
    
    def test_classify_error_method_signature(self):
        """Test that classify_error method has expected signature."""
        import inspect
        
        # Get the signature of the abstract method
        sig = inspect.signature(BaseErrorClassifier.classify_error)
        params = list(sig.parameters.keys())
        
        # Should have self, error, and optionally context
        assert 'self' in params
        assert 'error' in params
        # Context parameter is implementation-dependent
    
    def test_error_categories_available(self):
        """Test that error categories are available and valid."""
        categories = [
            ErrorCategory.TRANSIENT,
            ErrorCategory.PERMANENT,
            ErrorCategory.RATE_LIMIT
        ]
        
        for category in categories:
            assert category is not None
            # Categories should be comparable/hashable
            assert hash(category) is not None