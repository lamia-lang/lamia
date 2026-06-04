"""Integration tests for encoding validation in the engine retry loop.

Tests that the engine wraps validators with EncodingValidatorWrapper when
command.target_encoding is set to a non-UTF-8 encoding.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from lamia.engine.engine import LamiaEngine
from lamia.engine.config_provider import ConfigProvider
from lamia.interpreter.commands import LLMCommand, Command
from lamia.interpreter.command_types import CommandType
from lamia.validation.base import ValidationResult
from lamia.validation.encoding import EncodingValidatorWrapper


def _make_config_provider() -> ConfigProvider:
    return ConfigProvider({
        "model_chain": [],
        "extensions_folder": "extensions",
    })


class TestCommandTargetEncoding:
    """Test that target_encoding is available on commands."""

    def test_llm_command_default_none(self):
        cmd = LLMCommand(prompt="test")
        assert cmd.target_encoding is None

    def test_llm_command_with_encoding(self):
        cmd = LLMCommand(prompt="test", target_encoding="ascii")
        assert cmd.target_encoding == "ascii"

    def test_base_command_class_attribute_default(self):
        assert Command.target_encoding is None

    def test_llm_command_type_preserved(self):
        cmd = LLMCommand(prompt="test", target_encoding="latin-1")
        assert cmd.command_type == CommandType.LLM
        assert cmd.target_encoding == "latin-1"


class TestEngineEncodingWrapping:
    """Test that engine wraps validator with encoding check."""

    @pytest.mark.asyncio
    async def test_wraps_validator_for_non_utf8(self):
        config = _make_config_provider()
        engine = LamiaEngine(config)

        mock_validator = MagicMock()
        engine.validator_factory.get_validator = MagicMock(return_value=mock_validator)

        mock_manager = AsyncMock()
        mock_manager.execute = AsyncMock(return_value=ValidationResult(is_valid=True))
        engine.manager_factory.get_manager = MagicMock(return_value=mock_manager)
        engine.validator_registry.check_validator = MagicMock(return_value=(True, []))

        cmd = LLMCommand(prompt="generate ASCII data", target_encoding="ascii")
        mock_return_type = MagicMock()
        await engine.execute(cmd, return_type=mock_return_type)

        actual_validator = mock_manager.execute.call_args[0][1]
        assert isinstance(actual_validator, EncodingValidatorWrapper)

    @pytest.mark.asyncio
    async def test_no_wrapping_for_utf8(self):
        config = _make_config_provider()
        engine = LamiaEngine(config)

        mock_validator = MagicMock()
        engine.validator_factory.get_validator = MagicMock(return_value=mock_validator)

        mock_manager = AsyncMock()
        mock_manager.execute = AsyncMock(return_value=ValidationResult(is_valid=True))
        engine.manager_factory.get_manager = MagicMock(return_value=mock_manager)
        engine.validator_registry.check_validator = MagicMock(return_value=(True, []))

        cmd = LLMCommand(prompt="generate data", target_encoding="utf-8")
        mock_return_type = MagicMock()
        await engine.execute(cmd, return_type=mock_return_type)

        actual_validator = mock_manager.execute.call_args[0][1]
        assert not isinstance(actual_validator, EncodingValidatorWrapper)

    @pytest.mark.asyncio
    async def test_no_wrapping_when_encoding_none(self):
        config = _make_config_provider()
        engine = LamiaEngine(config)

        mock_validator = MagicMock()
        engine.validator_factory.get_validator = MagicMock(return_value=mock_validator)

        mock_manager = AsyncMock()
        mock_manager.execute = AsyncMock(return_value=ValidationResult(is_valid=True))
        engine.manager_factory.get_manager = MagicMock(return_value=mock_manager)
        engine.validator_registry.check_validator = MagicMock(return_value=(True, []))

        cmd = LLMCommand(prompt="generate data")
        mock_return_type = MagicMock()
        await engine.execute(cmd, return_type=mock_return_type)

        actual_validator = mock_manager.execute.call_args[0][1]
        assert not isinstance(actual_validator, EncodingValidatorWrapper)

    @pytest.mark.asyncio
    async def test_no_wrapping_without_return_type(self):
        config = _make_config_provider()
        engine = LamiaEngine(config)

        mock_manager = AsyncMock()
        mock_manager.execute = AsyncMock(return_value=ValidationResult(is_valid=True))
        engine.manager_factory.get_manager = MagicMock(return_value=mock_manager)

        cmd = LLMCommand(prompt="test", target_encoding="ascii")
        await engine.execute(cmd, return_type=None)

        actual_validator = mock_manager.execute.call_args[0][1]
        assert actual_validator is None

    @pytest.mark.asyncio
    async def test_wrapping_case_insensitive_utf8(self):
        """UTF-8 in any case should not trigger wrapping."""
        config = _make_config_provider()
        engine = LamiaEngine(config)

        mock_validator = MagicMock()
        engine.validator_factory.get_validator = MagicMock(return_value=mock_validator)

        mock_manager = AsyncMock()
        mock_manager.execute = AsyncMock(return_value=ValidationResult(is_valid=True))
        engine.manager_factory.get_manager = MagicMock(return_value=mock_manager)
        engine.validator_registry.check_validator = MagicMock(return_value=(True, []))

        for enc in ("UTF-8", "Utf-8", "UTF8"):
            cmd = LLMCommand(prompt="test", target_encoding=enc)
            mock_return_type = MagicMock()
            await engine.execute(cmd, return_type=mock_return_type)
            actual_validator = mock_manager.execute.call_args[0][1]
            assert not isinstance(actual_validator, EncodingValidatorWrapper), (
                f"Should not wrap for encoding={enc!r}"
            )

    @pytest.mark.asyncio
    async def test_wraps_for_latin1(self):
        config = _make_config_provider()
        engine = LamiaEngine(config)

        mock_validator = MagicMock()
        engine.validator_factory.get_validator = MagicMock(return_value=mock_validator)

        mock_manager = AsyncMock()
        mock_manager.execute = AsyncMock(return_value=ValidationResult(is_valid=True))
        engine.manager_factory.get_manager = MagicMock(return_value=mock_manager)
        engine.validator_registry.check_validator = MagicMock(return_value=(True, []))

        cmd = LLMCommand(prompt="test", target_encoding="latin-1")
        mock_return_type = MagicMock()
        await engine.execute(cmd, return_type=mock_return_type)

        actual_validator = mock_manager.execute.call_args[0][1]
        assert isinstance(actual_validator, EncodingValidatorWrapper)

    @pytest.mark.asyncio
    async def test_contract_check_runs_on_inner_validator(self):
        """Contract check should see the real validator, not the wrapper."""
        config = _make_config_provider()
        engine = LamiaEngine(config)

        mock_validator = MagicMock()
        engine.validator_factory.get_validator = MagicMock(return_value=mock_validator)

        mock_manager = AsyncMock()
        mock_manager.execute = AsyncMock(return_value=ValidationResult(is_valid=True))
        engine.manager_factory.get_manager = MagicMock(return_value=mock_manager)

        check_mock = MagicMock(return_value=(True, []))
        engine.validator_registry.check_validator = check_mock

        cmd = LLMCommand(prompt="test", target_encoding="ascii")
        mock_return_type = MagicMock()
        await engine.execute(cmd, return_type=mock_return_type)

        # Contract check must have been called with the inner validator type,
        # NOT with EncodingValidatorWrapper.
        checked_type = check_mock.call_args[0][0]
        assert checked_type is not EncodingValidatorWrapper
