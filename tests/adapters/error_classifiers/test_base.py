"""Comprehensive tests for ErrorClassifier base interface."""

import pytest
from abc import ABC
from lamia.adapters.error_classifiers.base import ErrorClassifier
from lamia.adapters.error_classifiers.categories import ErrorCategory


class TestErrorClassifierInterface:
    """Test ErrorClassifier abstract interface."""
    
    def test_is_abstract_base_class(self):
        """Test that ErrorClassifier is an abstract base class."""
        assert issubclass(ErrorClassifier, ABC)
        
        # Should not be able to instantiate directly
        with pytest.raises(TypeError):
            ErrorClassifier()
    
    def test_abstract_methods_exist(self):
        """Test that all required abstract methods are defined."""
        abstract_methods = ['classify_error']
        
        for method_name in abstract_methods:
            assert hasattr(ErrorClassifier, method_name)
            method = getattr(ErrorClassifier, method_name)
            assert callable(method)
    
    def test_classify_error_method_signature(self):
        """Test classify_error method signature."""
        method = ErrorClassifier.classify_error
        assert method.__name__ == 'classify_error'
        assert "Classify an error" in method.__doc__
        assert "ErrorCategory" in method.__doc__
    
    def test_method_documentation(self):
        """Test that methods are properly documented."""
        doc = ErrorClassifier.classify_error.__doc__
        assert "Args:" in doc
        assert "Returns:" in doc
        assert "error:" in doc.lower()


class ConcreteErrorClassifier(ErrorClassifier):
    """Concrete implementation for testing abstract interface."""
    
    def __init__(self, default_category=ErrorCategory.TRANSIENT):
        self.default_category = default_category
        self.classified_errors = []
    
    def classify_error(self, error: Exception) -> ErrorCategory:
        self.classified_errors.append(error)
        return self.default_category


class TestErrorClassifierImplementation:
    """Test error classifier implementation through concrete class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = ConcreteErrorClassifier()
    
    def test_classify_error_basic(self):
        """Test basic error classification."""
        error = Exception("Test error")
        result = self.classifier.classify_error(error)
        
        assert result == ErrorCategory.TRANSIENT
        assert len(self.classifier.classified_errors) == 1
        assert self.classifier.classified_errors[0] == error
    
    def test_classify_error_return_type(self):
        """Test that classify_error returns ErrorCategory."""
        error = ValueError("Invalid value")
        result = self.classifier.classify_error(error)
        
        assert isinstance(result, ErrorCategory)
        assert result in [ErrorCategory.TRANSIENT, ErrorCategory.PERMANENT, ErrorCategory.RATE_LIMIT]
    
    def test_different_error_types(self):
        """Test classification of different error types."""
        errors = [
            Exception("Generic error"),
            ValueError("Value error"), 
            ConnectionError("Connection failed"),
            TimeoutError("Request timed out"),
            RuntimeError("Runtime issue"),
            OSError("OS level error")
        ]
        
        results = []
        for error in errors:
            result = self.classifier.classify_error(error)
            assert isinstance(result, ErrorCategory)
            results.append(result)
        
        assert len(self.classifier.classified_errors) == 6
        assert all(isinstance(r, ErrorCategory) for r in results)
    
    def test_classify_error_different_categories(self):
        """Test classifier with different default categories."""
        categories = [
            ErrorCategory.TRANSIENT,
            ErrorCategory.PERMANENT, 
            ErrorCategory.RATE_LIMIT
        ]
        
        for category in categories:
            classifier = ConcreteErrorClassifier(default_category=category)
            result = classifier.classify_error(Exception("test"))
            assert result == category


class TestErrorClassifierWithRealExceptions:
    """Test error classifier with real exception types."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = ConcreteErrorClassifier()
    
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
            assert isinstance(result, ErrorCategory)
            assert result == ErrorCategory.TRANSIENT  # Default behavior
    
    def test_timeout_errors(self):
        """Test classification of timeout errors."""
        import socket
        
        errors = [
            TimeoutError("Operation timed out"),
            socket.timeout("Socket timeout")
        ]
        
        for error in errors:
            result = self.classifier.classify_error(error)
            assert isinstance(result, ErrorCategory)
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
            assert isinstance(result, ErrorCategory)
            assert result == ErrorCategory.TRANSIENT
    
    def test_permission_errors(self):
        """Test classification of permission errors."""
        errors = [
            PermissionError("Access denied"),
            OSError("Operation not permitted"),
            FileNotFoundError("File not found"),
            IsADirectoryError("Is a directory")
        ]
        
        for error in errors:
            result = self.classifier.classify_error(error)
            assert isinstance(result, ErrorCategory)
            assert result == ErrorCategory.TRANSIENT
    
    def test_custom_exceptions(self):
        """Test classification of custom exception types."""
        class CustomError(Exception):
            pass
        
        class SpecialError(ValueError):
            def __init__(self, message, code=None):
                super().__init__(message)
                self.code = code
        
        errors = [
            CustomError("Custom error message"),
            SpecialError("Special error", code=500),
            SpecialError("Another special error", code="AUTH_FAILED")
        ]
        
        for error in errors:
            result = self.classifier.classify_error(error)
            assert isinstance(result, ErrorCategory)
            assert result == ErrorCategory.TRANSIENT


class TestErrorClassifierEdgeCases:
    """Test error classifier edge cases and robustness."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = ConcreteErrorClassifier()
    
    def test_classify_none_error(self):
        """Test classification with None error."""
        # Most implementations should handle this gracefully
        try:
            result = self.classifier.classify_error(None)
            assert isinstance(result, ErrorCategory)
            assert len(self.classifier.classified_errors) == 1
            assert self.classifier.classified_errors[0] is None
        except (TypeError, AttributeError) as e:
            # Acceptable if implementation doesn't handle None
            assert "None" in str(e) or "NoneType" in str(e)
    
    def test_classify_empty_error_message(self):
        """Test classification with empty error message."""
        errors = [
            Exception(""),
            ValueError(""),
            RuntimeError("")
        ]
        
        for error in errors:
            result = self.classifier.classify_error(error)
            assert isinstance(result, ErrorCategory)
            assert result == ErrorCategory.TRANSIENT
    
    def test_multiple_classifications_independence(self):
        """Test that multiple classifiers work independently."""
        classifier1 = ConcreteErrorClassifier(ErrorCategory.PERMANENT)
        classifier2 = ConcreteErrorClassifier(ErrorCategory.RATE_LIMIT)
        
        error = Exception("Test error")
        
        result1 = classifier1.classify_error(error)
        result2 = classifier2.classify_error(error)
        
        assert result1 == ErrorCategory.PERMANENT
        assert result2 == ErrorCategory.RATE_LIMIT
        assert len(classifier1.classified_errors) == 1
        assert len(classifier2.classified_errors) == 1
    
    def test_classify_error_with_complex_hierarchy(self):
        """Test classification with complex exception hierarchy."""
        class BaseCustomError(Exception):
            pass
        
        class NetworkCustomError(BaseCustomError):
            pass
        
        class TimeoutCustomError(NetworkCustomError):
            def __init__(self, message, timeout_seconds=None):
                super().__init__(message)
                self.timeout_seconds = timeout_seconds
        
        errors = [
            BaseCustomError("Base error"),
            NetworkCustomError("Network error"),
            TimeoutCustomError("Timeout error", timeout_seconds=30)
        ]
        
        for error in errors:
            result = self.classifier.classify_error(error)
            assert isinstance(result, ErrorCategory)
            assert result == ErrorCategory.TRANSIENT
    
    def test_classify_error_state_tracking(self):
        """Test that classifier properly tracks error classification state."""
        errors = [
            ValueError("Error 1"),
            ConnectionError("Error 2"), 
            Exception("Error 3"),
            TimeoutError("Error 4")
        ]
        
        results = []
        for error in errors:
            result = self.classifier.classify_error(error)
            results.append(result)
        
        # All should return the default category
        assert all(r == ErrorCategory.TRANSIENT for r in results)
        
        # Should have recorded all classifications
        assert len(self.classifier.classified_errors) == 4
        
        # Verify all errors were recorded correctly
        for i, error in enumerate(errors):
            assert self.classifier.classified_errors[i] == error


class TestErrorCategoryEnum:
    """Test ErrorCategory enum values and behavior."""
    
    def test_error_categories_exist(self):
        """Test that all expected error categories exist."""
        expected_categories = ["PERMANENT", "TRANSIENT", "RATE_LIMIT"]
        
        for category_name in expected_categories:
            assert hasattr(ErrorCategory, category_name)
            category = getattr(ErrorCategory, category_name)
            assert isinstance(category, ErrorCategory)
    
    def test_error_categories_values(self):
        """Test that error categories have expected string values."""
        assert ErrorCategory.PERMANENT.value == "permanent"
        assert ErrorCategory.TRANSIENT.value == "transient"
        assert ErrorCategory.RATE_LIMIT.value == "rate_limit"
    
    def test_error_categories_equality(self):
        """Test error category equality comparison."""
        assert ErrorCategory.PERMANENT == ErrorCategory.PERMANENT
        assert ErrorCategory.TRANSIENT == ErrorCategory.TRANSIENT
        assert ErrorCategory.RATE_LIMIT == ErrorCategory.RATE_LIMIT
        
        assert ErrorCategory.PERMANENT != ErrorCategory.TRANSIENT
        assert ErrorCategory.TRANSIENT != ErrorCategory.RATE_LIMIT
    
    def test_error_categories_hashable(self):
        """Test that error categories are hashable (can be dict keys)."""
        category_dict = {
            ErrorCategory.PERMANENT: "permanent_handler",
            ErrorCategory.TRANSIENT: "transient_handler",
            ErrorCategory.RATE_LIMIT: "rate_limit_handler"
        }
        
        assert len(category_dict) == 3
        assert category_dict[ErrorCategory.PERMANENT] == "permanent_handler"
        assert category_dict[ErrorCategory.TRANSIENT] == "transient_handler"
        assert category_dict[ErrorCategory.RATE_LIMIT] == "rate_limit_handler"
    
    def test_error_categories_string_representation(self):
        """Test string representation of error categories."""
        for category in ErrorCategory:
            str_repr = str(category)
            assert "ErrorCategory" in str_repr
            assert category.value in str_repr


class TestErrorClassifierIntegration:
    """Test error classifier integration and compatibility."""
    
    def test_classifier_inheritance(self):
        """Test that concrete classifier inherits from ErrorClassifier."""
        classifier = ConcreteErrorClassifier()
        assert isinstance(classifier, ErrorClassifier)
    
    def test_classifier_implements_all_abstract_methods(self):
        """Test that concrete classifier implements all required methods."""
        abstract_methods = ['classify_error']
        
        for method_name in abstract_methods:
            assert hasattr(ConcreteErrorClassifier, method_name)
            method = getattr(ConcreteErrorClassifier, method_name)
            assert callable(method)
    
    def test_error_classifier_consistency(self):
        """Test that classifier behavior is consistent across calls."""
        classifier = ConcreteErrorClassifier(ErrorCategory.PERMANENT)
        error = ValueError("Test error")
        
        # Should return same result for same error
        result1 = classifier.classify_error(error)
        result2 = classifier.classify_error(error)
        
        assert result1 == result2
        assert result1 == ErrorCategory.PERMANENT
    
    def test_classifier_with_all_category_types(self):
        """Test classifier works with all error category types."""
        for category in ErrorCategory:
            classifier = ConcreteErrorClassifier(default_category=category)
            error = Exception(f"Test error for {category}")
            
            result = classifier.classify_error(error)
            assert result == category
            assert isinstance(result, ErrorCategory)