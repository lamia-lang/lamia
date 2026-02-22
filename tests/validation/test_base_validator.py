"""Comprehensive tests for BaseValidator class and validation framework base classes."""

import pytest
from unittest.mock import Mock, MagicMock
from lamia.validation.base import (
    BaseValidator,
    ValidationResult,
    TrackingContext
)
from lamia.interpreter.command_types import CommandType
from lamia.engine.validation_manager import ValidationStatsTracker


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_validation_result_creation(self):
        """Test creating a ValidationResult with all fields."""
        context = TrackingContext(
            data_provider_name="test:provider",
            command_type=CommandType.LLM,
            metadata={"key": "value"}
        )

        result = ValidationResult(
            is_valid=True,
            error_message="Error occurred",
            hint="Try again",
            raw_text="raw response",
            validated_text="validated response",
            typed_result={"data": "value"},
            info_loss={"field": "truncated"},
            execution_context=context
        )

        assert result.is_valid is True
        assert result.error_message == "Error occurred"
        assert result.hint == "Try again"
        assert result.raw_text == "raw response"
        assert result.validated_text == "validated response"
        assert result.typed_result == {"data": "value"}
        assert result.info_loss == {"field": "truncated"}
        assert result.execution_context == context

    def test_validation_result_minimal(self):
        """Test creating a minimal ValidationResult."""
        result = ValidationResult(is_valid=False)

        assert result.is_valid is False
        assert result.error_message is None
        assert result.hint is None
        assert result.raw_text is None
        assert result.validated_text is None
        assert result.typed_result is None
        assert result.info_loss is None
        assert result.execution_context is None

    def test_validation_result_valid(self):
        """Test creating a valid ValidationResult."""
        result = ValidationResult(
            is_valid=True,
            validated_text="valid text",
            typed_result="parsed_value"
        )

        assert result.is_valid is True
        assert result.validated_text == "valid text"
        assert result.typed_result == "parsed_value"

    def test_validation_result_invalid(self):
        """Test creating an invalid ValidationResult."""
        result = ValidationResult(
            is_valid=False,
            error_message="Validation failed",
            hint="Please fix the format"
        )

        assert result.is_valid is False
        assert result.error_message == "Validation failed"
        assert result.hint == "Please fix the format"


class TestTrackingContext:
    """Test TrackingContext dataclass."""

    def test_tracking_context_creation(self):
        """Test creating a TrackingContext with all fields."""
        context = TrackingContext(
            data_provider_name="openai:gpt-4o",
            command_type=CommandType.LLM,
            metadata={"request_id": "123", "temperature": 0.7}
        )

        assert context.data_provider_name == "openai:gpt-4o"
        assert context.command_type == CommandType.LLM
        assert context.metadata == {"request_id": "123", "temperature": 0.7}

    def test_tracking_context_minimal(self):
        """Test creating a minimal TrackingContext."""
        context = TrackingContext(
            data_provider_name="test:provider",
            command_type=CommandType.WEB
        )

        assert context.data_provider_name == "test:provider"
        assert context.command_type == CommandType.WEB
        assert context.metadata is None

    def test_tracking_context_metadata_types(self):
        """Test TrackingContext with different metadata types."""
        context = TrackingContext(
            data_provider_name="test:provider",
            command_type=CommandType.LLM,
            metadata={
                "string_field": "value",
                "int_field": 42,
                "float_field": 3.14,
                "bool_field": True
            }
        )

        assert context.metadata["string_field"] == "value"
        assert context.metadata["int_field"] == 42
        assert context.metadata["float_field"] == 3.14
        assert context.metadata["bool_field"] is True


class TestBaseValidatorConstructorValidation:
    """Test BaseValidator constructor validation logic."""

    def test_validator_with_validate_method(self):
        """Test validator that implements validate() method."""

        class ValidateMethodValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "validate_method"

            @property
            def initial_hint(self) -> str:
                return "Use validate method"

            async def validate(self, response: str, execution_context=None, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

        # Should be able to instantiate
        validator = ValidateMethodValidator()
        assert validator is not None

    def test_validator_with_strict_permissive_methods(self):
        """Test validator that implements validate_strict and validate_permissive."""

        class StrictPermissiveValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "strict_permissive"

            @property
            def initial_hint(self) -> str:
                return "Use strict/permissive methods"

            async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

            async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

        # Should be able to instantiate
        validator = StrictPermissiveValidator()
        assert validator is not None

    def test_validator_with_both_patterns_raises_error(self):
        """Test that implementing both patterns raises TypeError."""

        class BothPatternsValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "both"

            @property
            def initial_hint(self) -> str:
                return "Invalid"

            async def validate(self, response: str, execution_context=None, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

            async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

            async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

        with pytest.raises(TypeError, match="Implement either validate\\(\\) OR validate_strict/validate_permissive"):
            BothPatternsValidator()

    def test_validator_with_no_implementation_raises_error(self):
        """Test that not implementing any pattern raises TypeError."""

        class NoImplementationValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "no_impl"

            @property
            def initial_hint(self) -> str:
                return "Invalid"

        with pytest.raises(TypeError, match="Must implement either validate\\(\\) or both validate_strict and validate_permissive"):
            NoImplementationValidator()

    def test_validator_with_only_strict_raises_error(self):
        """Test that implementing only validate_strict raises TypeError."""

        class OnlyStrictValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "only_strict"

            @property
            def initial_hint(self) -> str:
                return "Invalid"

            async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

        with pytest.raises(TypeError, match="Must implement either validate\\(\\) or both validate_strict and validate_permissive"):
            OnlyStrictValidator()

    def test_validator_with_only_permissive_raises_error(self):
        """Test that implementing only validate_permissive raises TypeError."""

        class OnlyPermissiveValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "only_permissive"

            @property
            def initial_hint(self) -> str:
                return "Invalid"

            async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

        with pytest.raises(TypeError, match="Must implement either validate\\(\\) or both validate_strict and validate_permissive"):
            OnlyPermissiveValidator()


class TestBaseValidatorInitialization:
    """Test BaseValidator initialization and configuration."""

    def test_default_initialization(self):
        """Test BaseValidator initialization with default parameters."""

        class TestValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "test"

            @property
            def initial_hint(self) -> str:
                return "Test hint"

            async def validate(self, response: str, execution_context=None, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

        validator = TestValidator()

        assert validator.strict is True
        assert validator.generate_hints is False
        assert validator.validation_manager is None

    def test_custom_initialization(self):
        """Test BaseValidator initialization with custom parameters."""

        class TestValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "test"

            @property
            def initial_hint(self) -> str:
                return "Test hint"

            async def validate(self, response: str, execution_context=None, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

        validation_manager = Mock(spec=ValidationStatsTracker)
        validator = TestValidator(strict=False, generate_hints=True, validation_manager=validation_manager)

        assert validator.strict is False
        assert validator.generate_hints is True
        assert validator.validation_manager is validation_manager


@pytest.mark.asyncio
class TestBaseValidatorValidationDispatch:
    """Test BaseValidator validation method dispatch."""

    async def test_dispatch_to_strict_when_strict_true(self):
        """Test that validate() dispatches to validate_strict when strict=True."""

        class TestValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "test"

            @property
            def initial_hint(self) -> str:
                return "Test hint"

            async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True, validated_text="strict result")

            async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True, validated_text="permissive result")

        validator = TestValidator(strict=True)
        result = await validator.validate("test response")

        assert result.validated_text == "strict result"

    async def test_dispatch_to_permissive_when_strict_false(self):
        """Test that validate() dispatches to validate_permissive when strict=False."""

        class TestValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "test"

            @property
            def initial_hint(self) -> str:
                return "Test hint"

            async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True, validated_text="strict result")

            async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True, validated_text="permissive result")

        validator = TestValidator(strict=False)
        result = await validator.validate("test response")

        assert result.validated_text == "permissive result"

    async def test_validate_sets_raw_text(self):
        """Test that validate() sets raw_text on the result."""

        class TestValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "test"

            @property
            def initial_hint(self) -> str:
                return "Test hint"

            async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

            async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

        validator = TestValidator()
        result = await validator.validate("original response text")

        assert result.raw_text == "original response text"

    async def test_validate_sets_execution_context(self):
        """Test that validate() sets execution_context on the result."""

        class TestValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "test"

            @property
            def initial_hint(self) -> str:
                return "Test hint"

            async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

            async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

        context = TrackingContext(
            data_provider_name="test:provider",
            command_type=CommandType.LLM
        )

        validator = TestValidator()
        result = await validator.validate("test response", execution_context=context)

        assert result.execution_context == context

    async def test_validate_tracks_successful_validation(self):
        """Test that validate() tracks successful validation attempts."""

        class TestValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "test"

            @property
            def initial_hint(self) -> str:
                return "Test hint"

            async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

            async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

        validation_manager = Mock(spec=ValidationStatsTracker)
        context = TrackingContext(
            data_provider_name="test:provider",
            command_type=CommandType.LLM
        )

        validator = TestValidator(validation_manager=validation_manager)
        result = await validator.validate("test response", execution_context=context)

        validation_manager.record_intermediate_validation_attempt.assert_called_once_with(
            provider_name="test:provider",
            is_successful=True
        )

    async def test_validate_tracks_failed_validation(self):
        """Test that validate() tracks failed validation attempts."""

        class TestValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "test"

            @property
            def initial_hint(self) -> str:
                return "Test hint"

            async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=False, error_message="Validation failed")

            async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=False, error_message="Validation failed")

        validation_manager = Mock(spec=ValidationStatsTracker)
        context = TrackingContext(
            data_provider_name="test:provider",
            command_type=CommandType.LLM
        )

        validator = TestValidator(validation_manager=validation_manager)
        result = await validator.validate("test response", execution_context=context)

        validation_manager.record_intermediate_validation_attempt.assert_called_once_with(
            provider_name="test:provider",
            is_successful=False
        )

    async def test_validate_does_not_track_without_context(self):
        """Test that validate() doesn't track without execution context."""

        class TestValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "test"

            @property
            def initial_hint(self) -> str:
                return "Test hint"

            async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

            async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

        validation_manager = Mock(spec=ValidationStatsTracker)
        validator = TestValidator(validation_manager=validation_manager)
        result = await validator.validate("test response")  # No execution_context

        # Should not call record_intermediate_validation_attempt without context
        validation_manager.record_intermediate_validation_attempt.assert_not_called()

    async def test_validate_does_not_track_without_manager(self):
        """Test that validate() doesn't track without validation manager."""

        class TestValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "test"

            @property
            def initial_hint(self) -> str:
                return "Test hint"

            async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

            async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

        context = TrackingContext(
            data_provider_name="test:provider",
            command_type=CommandType.LLM
        )

        validator = TestValidator()  # No validation_manager
        result = await validator.validate("test response", execution_context=context)

        # Should not crash, just not track
        assert result.is_valid is True


class TestBaseValidatorGetRetryHint:
    """Test BaseValidator get_retry_hint functionality."""

    def test_get_retry_hint_disabled(self):
        """Test get_retry_hint returns None when generate_hints=False."""

        class TestValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "test"

            @property
            def initial_hint(self) -> str:
                return "Initial hint"

            async def validate(self, response: str, execution_context=None, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

        validator = TestValidator(generate_hints=False)
        hint = validator.get_retry_hint(error=Exception("Error"), retry_hint="Retry")

        assert hint is None

    def test_get_retry_hint_with_error(self):
        """Test get_retry_hint with error message."""

        class TestValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "test"

            @property
            def initial_hint(self) -> str:
                return "Initial hint"

            async def validate(self, response: str, execution_context=None, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

        validator = TestValidator(generate_hints=True)
        error = Exception("Validation failed")
        hint = validator.get_retry_hint(error=error)

        assert "Error: Validation failed" in hint
        assert "Initial hint" in hint

    def test_get_retry_hint_with_retry_message(self):
        """Test get_retry_hint with custom retry message."""

        class TestValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "test"

            @property
            def initial_hint(self) -> str:
                return "Initial hint"

            async def validate(self, response: str, execution_context=None, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

        validator = TestValidator(generate_hints=True)
        hint = validator.get_retry_hint(retry_hint="Please try again")

        assert "Please try again" in hint
        assert "Initial hint" in hint

    def test_get_retry_hint_with_error_and_retry(self):
        """Test get_retry_hint with both error and retry message."""

        class TestValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "test"

            @property
            def initial_hint(self) -> str:
                return "Initial hint"

            async def validate(self, response: str, execution_context=None, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

        validator = TestValidator(generate_hints=True)
        error = Exception("Parse error")
        hint = validator.get_retry_hint(error=error, retry_hint="Fix the format")

        assert "Error: Parse error" in hint
        assert "Fix the format" in hint
        assert "Initial hint" in hint

    def test_get_retry_hint_with_chained_errors(self):
        """Test get_retry_hint with chained exception errors."""

        class TestValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "test"

            @property
            def initial_hint(self) -> str:
                return "Initial hint"

            async def validate(self, response: str, execution_context=None, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

        validator = TestValidator(generate_hints=True)

        # Create chained exceptions
        try:
            try:
                raise ValueError("Inner error")
            except ValueError as e:
                raise RuntimeError("Outer error") from e
        except RuntimeError as error:
            hint = validator.get_retry_hint(error=error)

        assert "Outer error" in hint
        assert "Inner error" in hint
        assert "caused by" in hint

    def test_get_retry_hint_with_empty_error(self):
        """Test get_retry_hint with empty error message."""

        class TestValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "test"

            @property
            def initial_hint(self) -> str:
                return "Initial hint"

            async def validate(self, response: str, execution_context=None, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

        validator = TestValidator(generate_hints=True)
        error = Exception("")
        hint = validator.get_retry_hint(error=error)

        # Should still include initial hint even if error is empty
        assert "Initial hint" in hint

    def test_get_retry_hint_only_initial_hint(self):
        """Test get_retry_hint returns only initial hint when no error/retry."""

        class TestValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "test"

            @property
            def initial_hint(self) -> str:
                return "Initial hint"

            async def validate(self, response: str, execution_context=None, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

        validator = TestValidator(generate_hints=True)
        hint = validator.get_retry_hint()

        assert hint == "Initial hint"


class TestBaseValidatorAbstractMethods:
    """Test BaseValidator abstract methods enforcement."""

    def test_name_property_required(self):
        """Test that name property must be implemented."""

        with pytest.raises(TypeError):
            class NoNameValidator(BaseValidator):
                @property
                def initial_hint(self) -> str:
                    return "Hint"

                async def validate(self, response: str, execution_context=None, **kwargs) -> ValidationResult:
                    return ValidationResult(is_valid=True)

            # Should not be able to instantiate without name property
            validator = NoNameValidator()

    def test_initial_hint_property_required(self):
        """Test that initial_hint property must be implemented."""

        with pytest.raises(TypeError):
            class NoHintValidator(BaseValidator):
                @property
                def name(self) -> str:
                    return "test"

                async def validate(self, response: str, execution_context=None, **kwargs) -> ValidationResult:
                    return ValidationResult(is_valid=True)

            # Should not be able to instantiate without initial_hint property
            validator = NoHintValidator()
