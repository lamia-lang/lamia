"""Tests for the current LamiaEngine architecture.

LamiaEngine is a thin orchestrator that:
- Creates validators via ValidatorFactory
- Routes commands to the correct manager via ManagerFactory
- Records validation stats via ValidationStatsTracker
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from lamia.engine.engine import LamiaEngine
from lamia.engine.config_provider import ConfigProvider
from lamia.interpreter.command_types import CommandType
from lamia.validation.base import ValidationResult


def _make_config_provider() -> ConfigProvider:
    """Create a minimal ConfigProvider for tests."""
    return ConfigProvider({
        "model_chain": [],
        "extensions_folder": "extensions",
    })


def _make_llm_command() -> MagicMock:
    """Create a mock LLM command."""
    cmd = MagicMock()
    cmd.command_type = CommandType.LLM
    return cmd


def _make_web_command() -> MagicMock:
    """Create a mock web command."""
    cmd = MagicMock()
    cmd.command_type = CommandType.WEB
    return cmd


class TestEngineInit:
    """Test LamiaEngine initialization."""

    def test_init_creates_factories_and_managers(self):
        config = _make_config_provider()
        engine = LamiaEngine(config)

        assert engine.config_provider is config
        assert engine.validator_factory is not None
        assert engine.manager_factory is not None
        assert engine.validator_registry is not None
        assert engine.validation_manager is not None

    def test_init_passes_config_to_manager_factory(self):
        config = _make_config_provider()
        with patch("lamia.engine.engine.ManagerFactory") as MockFactory:
            LamiaEngine(config)
            MockFactory.assert_called_once_with(config)

    def test_init_passes_extensions_folder_to_registry(self):
        config = ConfigProvider({
            "model_chain": [],
            "extensions_folder": "my_exts",
        })
        with patch("lamia.engine.engine.ValidatorRegistry") as MockRegistry:
            LamiaEngine(config)
            MockRegistry.assert_called_once_with(extensions_folder="my_exts")


class TestEngineExecute:
    """Test LamiaEngine.execute() method."""

    @pytest.mark.asyncio
    async def test_execute_routes_to_correct_manager(self):
        config = _make_config_provider()
        engine = LamiaEngine(config)

        mock_manager = AsyncMock()
        mock_manager.execute = AsyncMock(return_value=ValidationResult(is_valid=True, raw_text="ok"))
        engine.manager_factory.get_manager = MagicMock(return_value=mock_manager)

        cmd = _make_llm_command()
        result = await engine.execute(cmd, return_type=None)

        engine.manager_factory.get_manager.assert_called_once_with(CommandType.LLM)
        mock_manager.execute.assert_awaited_once_with(cmd, None)
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_execute_with_return_type_creates_validator(self):
        config = _make_config_provider()
        engine = LamiaEngine(config)

        # Mock the validator factory
        mock_validator = MagicMock()
        engine.validator_factory.get_validator = MagicMock(return_value=mock_validator)

        # Mock validator registry to pass contract checks
        engine.validator_registry.check_validator = MagicMock(return_value=(True, []))

        # Mock the manager
        mock_manager = AsyncMock()
        mock_manager.execute = AsyncMock(return_value=ValidationResult(is_valid=True))
        engine.manager_factory.get_manager = MagicMock(return_value=mock_manager)

        mock_return_type = MagicMock()
        cmd = _make_llm_command()
        await engine.execute(cmd, return_type=mock_return_type)

        engine.validator_factory.get_validator.assert_called_once_with(
            CommandType.LLM,
            mock_return_type,
            validation_manager=engine.validation_manager,
        )
        mock_manager.execute.assert_awaited_once_with(cmd, mock_validator)

    @pytest.mark.asyncio
    async def test_execute_without_return_type_passes_none_validator(self):
        config = _make_config_provider()
        engine = LamiaEngine(config)

        mock_manager = AsyncMock()
        mock_manager.execute = AsyncMock(return_value=ValidationResult(is_valid=True))
        engine.manager_factory.get_manager = MagicMock(return_value=mock_manager)

        cmd = _make_llm_command()
        await engine.execute(cmd, return_type=None)

        mock_manager.execute.assert_awaited_once_with(cmd, None)

    @pytest.mark.asyncio
    async def test_execute_raises_on_failed_contract_check(self):
        config = _make_config_provider()
        engine = LamiaEngine(config)

        mock_validator = MagicMock()
        engine.validator_factory.get_validator = MagicMock(return_value=mock_validator)
        engine.validator_registry.check_validator = MagicMock(
            return_value=(False, ["Missing required method"])
        )

        cmd = _make_llm_command()
        with pytest.raises(ValueError, match="does not pass contract checks"):
            await engine.execute(cmd, return_type=MagicMock())

    @pytest.mark.asyncio
    async def test_execute_records_success_stats(self):
        config = _make_config_provider()
        engine = LamiaEngine(config)

        mock_manager = AsyncMock()
        mock_manager.execute = AsyncMock(return_value=ValidationResult(is_valid=True))
        engine.manager_factory.get_manager = MagicMock(return_value=mock_manager)
        engine.validation_manager.record_validation_result = MagicMock()

        cmd = _make_llm_command()
        await engine.execute(cmd, return_type=None)

        engine.validation_manager.record_validation_result.assert_called_once_with(True, CommandType.LLM)

    @pytest.mark.asyncio
    async def test_execute_records_failure_stats_on_invalid_result(self):
        config = _make_config_provider()
        engine = LamiaEngine(config)

        mock_manager = AsyncMock()
        mock_manager.execute = AsyncMock(return_value=ValidationResult(is_valid=False))
        engine.manager_factory.get_manager = MagicMock(return_value=mock_manager)
        engine.validation_manager.record_validation_result = MagicMock()

        cmd = _make_llm_command()
        await engine.execute(cmd, return_type=None)

        engine.validation_manager.record_validation_result.assert_called_once_with(False, CommandType.LLM)

    @pytest.mark.asyncio
    async def test_execute_records_failure_stats_on_exception(self):
        config = _make_config_provider()
        engine = LamiaEngine(config)

        mock_manager = AsyncMock()
        mock_manager.execute = AsyncMock(side_effect=RuntimeError("boom"))
        engine.manager_factory.get_manager = MagicMock(return_value=mock_manager)
        engine.validation_manager.record_validation_result = MagicMock()

        cmd = _make_llm_command()
        with pytest.raises(RuntimeError, match="boom"):
            await engine.execute(cmd, return_type=None)

        engine.validation_manager.record_validation_result.assert_called_once_with(False, CommandType.LLM)

    @pytest.mark.asyncio
    async def test_execute_propagates_manager_exception(self):
        config = _make_config_provider()
        engine = LamiaEngine(config)

        mock_manager = AsyncMock()
        mock_manager.execute = AsyncMock(side_effect=ConnectionError("network down"))
        engine.manager_factory.get_manager = MagicMock(return_value=mock_manager)

        cmd = _make_web_command()
        with pytest.raises(ConnectionError, match="network down"):
            await engine.execute(cmd, return_type=None)


class TestEngineStats:
    """Test LamiaEngine.get_validation_stats()."""

    def test_get_validation_stats_delegates_to_tracker(self):
        config = _make_config_provider()
        engine = LamiaEngine(config)

        mock_stats = MagicMock()
        engine.validation_manager.get_validation_stats = MagicMock(return_value=mock_stats)

        result = engine.get_validation_stats()
        assert result is mock_stats


class TestEngineCleanup:
    """Test LamiaEngine.cleanup()."""

    @pytest.mark.asyncio
    async def test_cleanup_closes_all_managers(self):
        config = _make_config_provider()
        engine = LamiaEngine(config)

        engine.manager_factory.close_all = AsyncMock()

        await engine.cleanup()

        engine.manager_factory.close_all.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cleanup_does_not_raise_on_error(self):
        config = _make_config_provider()
        engine = LamiaEngine(config)

        engine.manager_factory.close_all = AsyncMock(side_effect=RuntimeError("close failed"))

        # Should not raise
        await engine.cleanup()