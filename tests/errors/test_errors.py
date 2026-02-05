"""Tests for error classes."""

import pytest
from lamia.errors import (
    ExternalOperationError,
    ExternalOperationPermanentError,
    ExternalOperationRateLimitError,
    ExternalOperationTransientError,
    MissingAPIKeysError,
)


class TestMissingAPIKeysError:
    """Test MissingAPIKeysError."""

    def test_inheritance(self):
        """Test error inheritance."""
        error = MissingAPIKeysError("Test message")
        assert isinstance(error, Exception)
        assert isinstance(error, ValueError)

    def test_error_message(self):
        """Test error message handling."""
        message = "API key for OpenAI is missing"
        error = MissingAPIKeysError(message)
        assert str(error) == message

    def test_empty_message(self):
        """Test error with empty message."""
        error = MissingAPIKeysError("")
        assert str(error) == ""

    def test_error_raising(self):
        """Test that error can be raised and caught."""
        with pytest.raises(MissingAPIKeysError) as exc_info:
            raise MissingAPIKeysError("Test error")

        assert "Test error" in str(exc_info.value)


class TestExternalOperationError:
    """Test ExternalOperationError base class."""

    def test_inheritance(self):
        """Test error inheritance."""
        error = ExternalOperationError("Test message")
        assert isinstance(error, Exception)

    def test_error_message(self):
        """Test error message handling."""
        message = "External operation failed"
        error = ExternalOperationError(message)
        assert str(error) == message

    def test_error_raising(self):
        """Test that error can be raised and caught."""
        with pytest.raises(ExternalOperationError) as exc_info:
            raise ExternalOperationError("External error")

        assert "External error" in str(exc_info.value)


class TestExternalOperationTransientError:
    """Test ExternalOperationTransientError."""

    def test_inheritance(self):
        """Test error inheritance."""
        error = ExternalOperationTransientError("Test message")
        assert isinstance(error, Exception)
        assert isinstance(error, ExternalOperationError)

    def test_error_message(self):
        """Test error message handling."""
        message = "Transient error occurred"
        error = ExternalOperationTransientError(message)
        assert str(error) == message

    def test_error_raising(self):
        """Test that error can be raised and caught."""
        with pytest.raises(ExternalOperationTransientError) as exc_info:
            raise ExternalOperationTransientError("Temporary failure")

        assert "Temporary failure" in str(exc_info.value)

    def test_inheritance_catching(self):
        """Test that error can be caught as base class."""
        with pytest.raises(ExternalOperationError):
            raise ExternalOperationTransientError("Transient error")


class TestExternalOperationPermanentError:
    """Test ExternalOperationPermanentError."""

    def test_inheritance(self):
        """Test error inheritance."""
        error = ExternalOperationPermanentError("Test message")
        assert isinstance(error, Exception)
        assert isinstance(error, ExternalOperationError)

    def test_error_message(self):
        """Test error message handling."""
        message = "Permanent error occurred"
        error = ExternalOperationPermanentError(message)
        assert str(error) == message

    def test_error_raising(self):
        """Test that error can be raised and caught."""
        with pytest.raises(ExternalOperationPermanentError) as exc_info:
            raise ExternalOperationPermanentError("Permanent failure")

        assert "Permanent failure" in str(exc_info.value)

    def test_inheritance_catching(self):
        """Test that error can be caught as base class."""
        with pytest.raises(ExternalOperationError):
            raise ExternalOperationPermanentError("Permanent error")


class TestExternalOperationRateLimitError:
    """Test ExternalOperationRateLimitError."""

    def test_inheritance(self):
        """Test error inheritance."""
        error = ExternalOperationRateLimitError("Test message")
        assert isinstance(error, Exception)
        assert isinstance(error, ExternalOperationError)

    def test_error_message(self):
        """Test error message handling."""
        message = "Rate limit exceeded"
        error = ExternalOperationRateLimitError(message)
        assert str(error) == message

    def test_error_raising(self):
        """Test that error can be raised and caught."""
        with pytest.raises(ExternalOperationRateLimitError) as exc_info:
            raise ExternalOperationRateLimitError("Rate limit hit")

        assert "Rate limit hit" in str(exc_info.value)

    def test_inheritance_catching(self):
        """Test that error can be caught as base class."""
        with pytest.raises(ExternalOperationError):
            raise ExternalOperationRateLimitError("Rate limit error")


class TestErrorHierarchy:
    """Test error class hierarchy relationships."""

    def test_external_operation_error_hierarchy(self):
        """Test that all external operation errors inherit correctly."""
        transient = ExternalOperationTransientError("test")
        permanent = ExternalOperationPermanentError("test")
        rate_limit = ExternalOperationRateLimitError("test")

        assert isinstance(transient, ExternalOperationError)
        assert isinstance(permanent, ExternalOperationError)
        assert isinstance(rate_limit, ExternalOperationError)

        assert isinstance(transient, Exception)
        assert isinstance(permanent, Exception)
        assert isinstance(rate_limit, Exception)

    def test_catch_all_external_operations(self):
        """Test that all external operation errors can be caught by base class."""
        errors = [
            ExternalOperationTransientError("transient"),
            ExternalOperationPermanentError("permanent"),
            ExternalOperationRateLimitError("rate limit"),
        ]

        for error in errors:
            with pytest.raises(ExternalOperationError):
                raise error

    def test_distinct_error_types(self):
        """Test that different error types are distinct."""
        transient = ExternalOperationTransientError("test")
        permanent = ExternalOperationPermanentError("test")
        rate_limit = ExternalOperationRateLimitError("test")
        missing_api = MissingAPIKeysError("test")

        assert not isinstance(transient, ExternalOperationPermanentError)
        assert not isinstance(permanent, ExternalOperationTransientError)
        assert not isinstance(rate_limit, ExternalOperationTransientError)
        assert not isinstance(missing_api, ExternalOperationError)


class TestErrorMessages:
    """Test error message handling."""

    def test_all_errors_accept_messages(self):
        """Test that all errors accept string messages."""
        message = "Test error message"
        errors = [
            MissingAPIKeysError(message),
            ExternalOperationError(message),
            ExternalOperationTransientError(message),
            ExternalOperationPermanentError(message),
            ExternalOperationRateLimitError(message),
        ]

        for error in errors:
            assert str(error) == message

    def test_error_repr(self):
        """Test error string representation."""
        errors = [
            MissingAPIKeysError("API error"),
            ExternalOperationTransientError("Transient error"),
            ExternalOperationPermanentError("Permanent error"),
            ExternalOperationRateLimitError("Rate limit error"),
        ]

        for error in errors:
            repr_str = repr(error)
            assert error.__class__.__name__ in repr_str
            assert str(error) in repr_str


class TestErrorUsagePatterns:
    """Test common error usage patterns."""

    def test_nested_exception_handling(self):
        """Test handling of nested exceptions."""
        try:
            try:
                raise ExternalOperationTransientError("Inner error")
            except ExternalOperationTransientError as e:
                raise ExternalOperationPermanentError("Outer error") from e
        except ExternalOperationError as e:
            assert e.__cause__ is not None
            assert isinstance(e.__cause__, ExternalOperationTransientError)

    def test_exception_chaining(self):
        """Test exception chaining."""
        try:
            try:
                raise ValueError("Original error")
            except ValueError as e:
                raise ExternalOperationError("Wrapper error") from e
        except ExternalOperationError as e:
            assert e.__cause__ is not None
            assert isinstance(e.__cause__, ValueError)

    def test_conditional_error_handling(self):
        """Test conditional error handling based on error type."""
        def handle_error(error):
            if isinstance(error, ExternalOperationTransientError):
                return "retry"
            if isinstance(error, ExternalOperationPermanentError):
                return "fail"
            if isinstance(error, ExternalOperationRateLimitError):
                return "backoff"
            return "unknown"

        assert handle_error(ExternalOperationTransientError("test")) == "retry"
        assert handle_error(ExternalOperationPermanentError("test")) == "fail"
        assert handle_error(ExternalOperationRateLimitError("test")) == "backoff"
        assert handle_error(MissingAPIKeysError("test")) == "unknown"


class TestErrorInitialization:
    """Test error initialization with various parameters."""

    def test_error_with_no_args(self):
        """Test error initialization with no arguments."""
        try:
            error = ExternalOperationError()
            assert str(error) == ""
        except TypeError:
            pass

    def test_error_with_multiple_args(self):
        """Test error initialization with multiple arguments."""
        try:
            error = ExternalOperationError("message", "code", 500)
            assert "message" in str(error)
        except (TypeError, AttributeError):
            pass

    def test_error_with_kwargs(self):
        """Test error initialization with keyword arguments."""
        try:
            error = ExternalOperationError("message", code=500, retry_after=60)
            assert str(error) == "message"
        except (TypeError, AttributeError):
            pass
