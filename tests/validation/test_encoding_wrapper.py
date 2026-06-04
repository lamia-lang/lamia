"""Tests for EncodingValidatorWrapper."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from lamia.validation.base import BaseValidator, ValidationResult, TrackingContext
from lamia.validation.encoding import EncodingValidatorWrapper
from lamia.interpreter.command_types import CommandType


class _StubValidator(BaseValidator):
    """Minimal validator that always succeeds, for testing the wrapper."""

    def __init__(self, validated_text: str = None):
        self._validated_text = validated_text
        super().__init__(generate_hints=True)

    async def validate(self, response: str, execution_context=None, **kwargs) -> ValidationResult:
        return ValidationResult(
            is_valid=True,
            validated_text=self._validated_text or response,
        )

    @property
    def name(self) -> str:
        return "stub"

    @property
    def initial_hint(self) -> str:
        return "Stub hint"


class _FailingValidator(BaseValidator):
    """Validator that always rejects content."""

    def __init__(self):
        super().__init__()

    async def validate(self, response: str, execution_context=None, **kwargs) -> ValidationResult:
        return ValidationResult(is_valid=False, error_message="format invalid")

    @property
    def name(self) -> str:
        return "failing"

    @property
    def initial_hint(self) -> str:
        return "Failing hint"


@pytest.mark.asyncio
class TestEncodingValidatorWrapperValidate:
    """Test the core validate method of EncodingValidatorWrapper."""

    async def test_ascii_accepts_plain_ascii(self):
        inner = _StubValidator()
        wrapper = EncodingValidatorWrapper(inner, "ascii")
        result = await wrapper.validate("Hello, World! 123")
        assert result.is_valid

    async def test_ascii_rejects_accented_chars(self):
        inner = _StubValidator()
        wrapper = EncodingValidatorWrapper(inner, "ascii")
        result = await wrapper.validate("café")
        assert not result.is_valid
        assert "U+00E9" in result.error_message
        assert "ascii" in result.error_message

    async def test_ascii_rejects_em_dash(self):
        inner = _StubValidator()
        wrapper = EncodingValidatorWrapper(inner, "ascii")
        result = await wrapper.validate("value — other")
        assert not result.is_valid
        assert "\u2014" in result.error_message or "U+2014" in result.error_message

    async def test_ascii_rejects_smart_quotes(self):
        inner = _StubValidator()
        wrapper = EncodingValidatorWrapper(inner, "ascii")
        result = await wrapper.validate('He said \u201chello\u201d')
        assert not result.is_valid

    async def test_latin1_accepts_accented_chars(self):
        inner = _StubValidator()
        wrapper = EncodingValidatorWrapper(inner, "latin-1")
        result = await wrapper.validate("café résumé")
        assert result.is_valid

    async def test_latin1_rejects_emoji(self):
        inner = _StubValidator()
        wrapper = EncodingValidatorWrapper(inner, "latin-1")
        result = await wrapper.validate("done \U0001f389")
        assert not result.is_valid
        assert "latin-1" in result.error_message

    async def test_latin1_rejects_cjk(self):
        inner = _StubValidator()
        wrapper = EncodingValidatorWrapper(inner, "latin-1")
        result = await wrapper.validate("\u65e5\u672c\u8a9e")
        assert not result.is_valid

    async def test_utf8_always_passes(self):
        """UTF-8 can encode any Python str — wrapper should never reject."""
        inner = _StubValidator()
        wrapper = EncodingValidatorWrapper(inner, "utf-8")
        result = await wrapper.validate("\u00a5\u20ac\U0001f389\u65e5\u672c\u8a9e")
        assert result.is_valid

    async def test_inner_failure_short_circuits(self):
        """If the inner validator rejects, encoding check should not run."""
        inner = _FailingValidator()
        wrapper = EncodingValidatorWrapper(inner, "ascii")
        result = await wrapper.validate("café")
        assert not result.is_valid
        assert result.error_message == "format invalid"

    async def test_uses_validated_text_for_encoding_check(self):
        """The wrapper should check validated_text (extracted content), not raw response."""
        inner = _StubValidator(validated_text="plain ascii only")
        wrapper = EncodingValidatorWrapper(inner, "ascii")
        result = await wrapper.validate("```\nplain ascii only\n```")
        assert result.is_valid

    async def test_validated_text_with_bad_encoding(self):
        inner = _StubValidator(validated_text="café")
        wrapper = EncodingValidatorWrapper(inner, "ascii")
        result = await wrapper.validate("raw response doesn't matter")
        assert not result.is_valid
        assert "U+00E9" in result.error_message

    async def test_hint_suggests_replacement(self):
        inner = _StubValidator()
        wrapper = EncodingValidatorWrapper(inner, "ascii")
        result = await wrapper.validate("café")
        assert "Replace" in result.hint
        assert "ascii-safe" in result.hint

    async def test_execution_context_forwarded_to_inner(self):
        inner = _StubValidator()
        wrapper = EncodingValidatorWrapper(inner, "ascii")
        ctx = TrackingContext(
            data_provider_name="test:model",
            command_type=CommandType.LLM,
        )
        result = await wrapper.validate("hello", execution_context=ctx)
        assert result.is_valid

    async def test_valid_result_returned_unchanged(self):
        """When encoding check passes, the inner result is returned as-is."""
        inner = _StubValidator(validated_text="clean")
        wrapper = EncodingValidatorWrapper(inner, "ascii")
        result = await wrapper.validate("clean")
        assert result.is_valid
        assert result.validated_text == "clean"


class TestEncodingValidatorWrapperProperties:
    """Test property proxying to inner validator."""

    def test_name_includes_encoding_and_inner_name(self):
        inner = _StubValidator()
        wrapper = EncodingValidatorWrapper(inner, "ascii")
        assert wrapper.name == "encoding(ascii):stub"

    def test_initial_hint_delegates_to_inner(self):
        inner = _StubValidator()
        wrapper = EncodingValidatorWrapper(inner, "ascii")
        assert wrapper.initial_hint == "Stub hint"

    def test_strict_proxied_to_inner(self):
        inner = _StubValidator()
        wrapper = EncodingValidatorWrapper(inner, "ascii")
        assert wrapper.strict is inner.strict
        wrapper.strict = False
        assert inner.strict is False

    def test_generate_hints_proxied_to_inner(self):
        inner = _StubValidator()
        wrapper = EncodingValidatorWrapper(inner, "ascii")
        assert wrapper.generate_hints is inner.generate_hints
        wrapper.generate_hints = False
        assert inner.generate_hints is False

    def test_validation_manager_proxied_to_inner(self):
        inner = _StubValidator()
        wrapper = EncodingValidatorWrapper(inner, "ascii")
        mock_manager = MagicMock()
        wrapper.validation_manager = mock_manager
        assert inner.validation_manager is mock_manager
        assert wrapper.validation_manager is mock_manager


class TestEncodingValidatorWrapperDelegation:
    """Test that helper methods delegate to inner validator."""

    def test_prepare_content_for_write_delegates(self):
        inner = _StubValidator()
        inner.prepare_content_for_write = MagicMock(return_value="combined")
        wrapper = EncodingValidatorWrapper(inner, "ascii")
        result = wrapper.prepare_content_for_write("existing", "new")
        inner.prepare_content_for_write.assert_called_once_with("existing", "new")
        assert result == "combined"

    def test_get_retry_hint_delegates(self):
        inner = _StubValidator()
        wrapper = EncodingValidatorWrapper(inner, "ascii")
        hint = wrapper.get_retry_hint(retry_hint="try again")
        assert hint is not None


@pytest.mark.asyncio
class TestEncodingValidatorWrapperEdgeCases:
    """Edge cases and various encoding scenarios."""

    async def test_windows_1252_accepts_euro_sign(self):
        inner = _StubValidator()
        wrapper = EncodingValidatorWrapper(inner, "cp1252")
        result = await wrapper.validate("Price: 50\u20ac")
        assert result.is_valid

    async def test_windows_1252_rejects_cjk(self):
        inner = _StubValidator()
        wrapper = EncodingValidatorWrapper(inner, "cp1252")
        result = await wrapper.validate("\u65e5\u672c")
        assert not result.is_valid

    async def test_shift_jis_accepts_japanese(self):
        inner = _StubValidator()
        wrapper = EncodingValidatorWrapper(inner, "shift_jis")
        result = await wrapper.validate("\u3053\u3093\u306b\u3061\u306f")
        assert result.is_valid

    async def test_empty_string_always_passes(self):
        inner = _StubValidator(validated_text="")
        wrapper = EncodingValidatorWrapper(inner, "ascii")
        result = await wrapper.validate("")
        assert result.is_valid

    async def test_first_bad_char_reported(self):
        """When multiple bad chars exist, the first one is reported."""
        inner = _StubValidator()
        wrapper = EncodingValidatorWrapper(inner, "ascii")
        result = await wrapper.validate("a\u00e9b\u00fc")
        assert not result.is_valid
        assert "U+00E9" in result.error_message
