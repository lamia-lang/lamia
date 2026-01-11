"""Comprehensive tests for Facade module: main Lamia API and command processor."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from lamia.facade.lamia import Lamia
from lamia.facade.command_processor import process_string_command
from lamia.facade.result_types import LamiaResult
from lamia.interpreter.commands import Command
from lamia.interpreter.command_types import CommandType
from lamia.validation.base import TrackingContext, ValidationResult
from lamia.engine.engine import LamiaEngine
from lamia.types import ExternalOperationRetryConfig
from lamia import LLMModel


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def mock_engine():
    """Create a mock LamiaEngine."""
    engine = Mock(spec=LamiaEngine)
    engine.execute = AsyncMock(return_value=ValidationResult(
        is_valid=True,
        validated_text="Generated response",
        result_type="Processed result",
        raw_text="Generated response",
        execution_context=TrackingContext(
            data_provider_name="openai:gpt-4o",
            command_type=CommandType.LLM
        )
    ))
    engine.cleanup = AsyncMock(return_value=None)
    engine.get_validation_stats = Mock(return_value={"total_attempts": 1})
    engine.config_provider = Mock()
    engine.config_provider.override_model_chain_with = Mock()
    engine.config_provider.reset_model_chain = Mock()
    return engine


@pytest.fixture
def mock_config_provider():
    """Create a mock config provider."""
    return Mock()


# ============================================================================
# LAMIA CLASS INITIALIZATION TESTS
# ============================================================================

class TestLamiaInitialization:
    """Test Lamia class initialization."""

    @patch('lamia.facade.lamia.build_config_from_models')
    @patch('lamia.facade.lamia.LamiaEngine')
    def test_init_with_single_model(self, mock_engine_class, mock_build_config):
        """Test initialization with a single model."""
        mock_config = Mock()
        mock_build_config.return_value = mock_config

        lamia = Lamia("openai:gpt-4o")

        mock_build_config.assert_called_once_with(
            ("openai:gpt-4o",),
            None,  # api_keys
            None,  # retry_config
            None   # web_config
        )
        mock_engine_class.assert_called_once_with(mock_config)

    @patch('lamia.facade.lamia.build_config_from_models')
    @patch('lamia.facade.lamia.LamiaEngine')
    def test_init_with_multiple_models(self, mock_engine_class, mock_build_config):
        """Test initialization with multiple models."""
        mock_config = Mock()
        mock_build_config.return_value = mock_config

        lamia = Lamia("openai:gpt-4o", "anthropic:claude-3")

        mock_build_config.assert_called_once_with(
            ("openai:gpt-4o", "anthropic:claude-3"),
            None,
            None,
            None
        )

    @patch('lamia.facade.lamia.build_config_from_models')
    @patch('lamia.facade.lamia.LamiaEngine')
    def test_init_with_api_keys(self, mock_engine_class, mock_build_config):
        """Test initialization with API keys."""
        mock_config = Mock()
        mock_build_config.return_value = mock_config
        api_keys = {'openai': 'sk-test123'}

        lamia = Lamia("openai:gpt-4o", api_keys=api_keys)

        mock_build_config.assert_called_once_with(
            ("openai:gpt-4o",),
            api_keys,
            None,
            None
        )

    @patch('lamia.facade.lamia.build_config_from_models')
    @patch('lamia.facade.lamia.LamiaEngine')
    def test_init_with_retry_config(self, mock_engine_class, mock_build_config):
        """Test initialization with retry configuration."""
        mock_config = Mock()
        mock_build_config.return_value = mock_config
        retry_config = ExternalOperationRetryConfig(
            max_attempts=5,
            base_delay=1.0,
            max_delay=30.0,
            exponential_base=2.0
        )

        lamia = Lamia("openai:gpt-4o", retry_config=retry_config)

        mock_build_config.assert_called_once_with(
            ("openai:gpt-4o",),
            None,
            retry_config,
            None
        )

    @patch('lamia.facade.lamia.build_config_from_models')
    @patch('lamia.facade.lamia.LamiaEngine')
    def test_init_with_web_config(self, mock_engine_class, mock_build_config):
        """Test initialization with web configuration."""
        mock_config = Mock()
        mock_build_config.return_value = mock_config
        web_config = {'browser': 'chrome', 'headless': True}

        lamia = Lamia("openai:gpt-4o", web_config=web_config)

        mock_build_config.assert_called_once_with(
            ("openai:gpt-4o",),
            None,
            None,
            web_config
        )

    @patch('lamia.facade.lamia.build_config_from_dict')
    @patch('lamia.facade.lamia.LamiaEngine')
    @patch('lamia.facade.lamia.build_config_from_models')
    def test_from_config_class_method(self, mock_build_models, mock_engine_class, mock_build_dict):
        """Test from_config class method."""
        mock_build_dict.return_value = (["openai:gpt-4o"], None)
        mock_config_provider = Mock()
        mock_build_models.return_value = mock_config_provider

        config = {
            'models': ['openai:gpt-4o'],
            'web_config': {'browser': 'chrome'}
        }

        lamia = Lamia.from_config(config)

        mock_build_dict.assert_called_once_with(config)
        assert isinstance(lamia, Lamia)


# ============================================================================
# LAMIA RUN_ASYNC TESTS
# ============================================================================

@pytest.mark.asyncio
class TestLamiaRunAsync:
    """Test Lamia run_async method."""

    @patch('lamia.facade.lamia.build_config_from_models')
    @patch('lamia.facade.lamia.process_string_command')
    async def test_run_async_with_string_command(self, mock_process, mock_build_config, mock_engine):
        """Test run_async with string command."""
        mock_build_config.return_value = Mock()
        mock_command = Command(command_type=CommandType.LLM, content="test")
        mock_process.return_value = (mock_command, None)

        with patch('lamia.facade.lamia.LamiaEngine', return_value=mock_engine):
            lamia = Lamia("openai:gpt-4o")
            result = await lamia.run_async("Generate a joke")

        mock_process.assert_called_once_with("Generate a joke")
        mock_engine.execute.assert_called_once()
        assert result == "Processed result"  # result_type when no return_type specified

    @patch('lamia.facade.lamia.build_config_from_models')
    @patch('lamia.facade.lamia.process_string_command')
    async def test_run_async_with_python_result(self, mock_process, mock_build_config, mock_engine):
        """Test run_async when Python execution succeeds."""
        mock_build_config.return_value = Mock()
        python_result = LamiaResult(
            result_text="42",
            typed_result=42,
            tracking_context=TrackingContext(
                data_provider_name="python",
                command_type="python"
            )
        )
        mock_process.return_value = (None, python_result)

        with patch('lamia.facade.lamia.LamiaEngine', return_value=mock_engine):
            lamia = Lamia("openai:gpt-4o")
            result = await lamia.run_async("2 + 2")

        # Should return Python result without calling engine
        assert result == python_result
        mock_engine.execute.assert_not_called()

    @patch('lamia.facade.lamia.build_config_from_models')
    async def test_run_async_with_command_object(self, mock_build_config, mock_engine):
        """Test run_async with Command object."""
        mock_build_config.return_value = Mock()
        command = Command(command_type=CommandType.LLM, content="test")

        with patch('lamia.facade.lamia.LamiaEngine', return_value=mock_engine):
            lamia = Lamia("openai:gpt-4o")
            result = await lamia.run_async(command)

        mock_engine.execute.assert_called_once_with(command, return_type=None)
        assert result == "Processed result"

    @patch('lamia.facade.lamia.build_config_from_models')
    @patch('lamia.facade.lamia.process_string_command')
    async def test_run_async_with_return_type(self, mock_process, mock_build_config, mock_engine):
        """Test run_async with return_type specified."""
        mock_build_config.return_value = Mock()
        mock_command = Command(command_type=CommandType.LLM, content="test")
        mock_process.return_value = (mock_command, None)

        with patch('lamia.facade.lamia.LamiaEngine', return_value=mock_engine):
            lamia = Lamia("openai:gpt-4o")
            result = await lamia.run_async("Generate text", return_type=str)

        # Should return LamiaResult when return_type is specified
        assert isinstance(result, LamiaResult)
        assert result.typed_result == "Processed result"
        assert result.result_text == "Generated response"

    @patch('lamia.facade.lamia.build_config_from_models')
    @patch('lamia.facade.lamia.process_string_command')
    async def test_run_async_with_model_override(self, mock_process, mock_build_config, mock_engine):
        """Test run_async with model override."""
        mock_build_config.return_value = Mock()
        mock_command = Command(command_type=CommandType.LLM, content="test")
        mock_process.return_value = (mock_command, None)

        with patch('lamia.facade.lamia.LamiaEngine', return_value=mock_engine):
            lamia = Lamia("openai:gpt-4o")
            result = await lamia.run_async("Generate text", models="anthropic:claude-3")

        # Should override and reset model chain
        mock_engine.config_provider.override_model_chain_with.assert_called_once_with("anthropic:claude-3")
        mock_engine.config_provider.reset_model_chain.assert_called_once()


# ============================================================================
# LAMIA RUN TESTS
# ============================================================================

class TestLamiaRun:
    """Test Lamia run synchronous method."""

    @patch('lamia.facade.lamia.build_config_from_models')
    @patch('lamia.facade.lamia.process_string_command')
    def test_run_synchronous(self, mock_process, mock_build_config, mock_engine):
        """Test run method (synchronous wrapper)."""
        mock_build_config.return_value = Mock()
        mock_command = Command(command_type=CommandType.LLM, content="test")
        mock_process.return_value = (mock_command, None)

        with patch('lamia.facade.lamia.LamiaEngine', return_value=mock_engine):
            lamia = Lamia("openai:gpt-4o")
            result = lamia.run("Generate a joke")

        assert result == "Processed result"
        mock_engine.execute.assert_called_once()

    @patch('lamia.facade.lamia.build_config_from_models')
    @patch('lamia.facade.lamia.process_string_command')
    def test_run_with_return_type(self, mock_process, mock_build_config, mock_engine):
        """Test run with return_type specified."""
        mock_build_config.return_value = Mock()
        mock_command = Command(command_type=CommandType.LLM, content="test")
        mock_process.return_value = (mock_command, None)

        with patch('lamia.facade.lamia.LamiaEngine', return_value=mock_engine):
            lamia = Lamia("openai:gpt-4o")
            result = lamia.run("Generate text", return_type=str)

        assert isinstance(result, LamiaResult)

    @patch('lamia.facade.lamia.build_config_from_models')
    def test_run_inside_async_context_raises_error(self, mock_build_config, mock_engine):
        """Test that run() raises error when called inside async context."""
        mock_build_config.return_value = Mock()

        async def async_test():
            with patch('lamia.facade.lamia.LamiaEngine', return_value=mock_engine):
                lamia = Lamia("openai:gpt-4o")
                with pytest.raises(RuntimeError, match="cannot be used inside an async context"):
                    lamia.run("test command")

        asyncio.run(async_test())


# ============================================================================
# LAMIA CONTEXT MANAGER TESTS
# ============================================================================

@pytest.mark.asyncio
class TestLamiaContextManager:
    """Test Lamia async context manager protocol."""

    @patch('lamia.facade.lamia.build_config_from_models')
    async def test_async_context_manager_enter(self, mock_build_config, mock_engine):
        """Test async context manager __aenter__."""
        mock_build_config.return_value = Mock()

        with patch('lamia.facade.lamia.LamiaEngine', return_value=mock_engine):
            async with Lamia("openai:gpt-4o") as lamia:
                assert isinstance(lamia, Lamia)

    @patch('lamia.facade.lamia.build_config_from_models')
    async def test_async_context_manager_exit(self, mock_build_config, mock_engine):
        """Test async context manager __aexit__ calls cleanup."""
        mock_build_config.return_value = Mock()

        with patch('lamia.facade.lamia.LamiaEngine', return_value=mock_engine):
            async with Lamia("openai:gpt-4o") as lamia:
                pass

        mock_engine.cleanup.assert_called_once()

    @patch('lamia.facade.lamia.build_config_from_models')
    async def test_async_context_manager_exception_handling(self, mock_build_config, mock_engine):
        """Test async context manager cleanup on exception."""
        mock_build_config.return_value = Mock()

        with patch('lamia.facade.lamia.LamiaEngine', return_value=mock_engine):
            try:
                async with Lamia("openai:gpt-4o") as lamia:
                    raise ValueError("Test exception")
            except ValueError:
                pass

        # Should still call cleanup
        mock_engine.cleanup.assert_called_once()


# ============================================================================
# LAMIA CLEANUP AND DESTRUCTOR TESTS
# ============================================================================

class TestLamiaCleanup:
    """Test Lamia cleanup and __del__ method."""

    @patch('lamia.facade.lamia.build_config_from_models')
    def test_get_validation_stats(self, mock_build_config, mock_engine):
        """Test getting validation statistics."""
        mock_build_config.return_value = Mock()

        with patch('lamia.facade.lamia.LamiaEngine', return_value=mock_engine):
            lamia = Lamia("openai:gpt-4o")
            stats = lamia.get_validation_stats()

        assert stats == {"total_attempts": 1}
        mock_engine.get_validation_stats.assert_called_once()

    @patch('lamia.facade.lamia.build_config_from_models')
    @patch('lamia.facade.lamia.asyncio.run')
    def test_del_no_running_loop(self, mock_asyncio_run, mock_build_config, mock_engine):
        """Test __del__ cleanup when no event loop is running."""
        mock_build_config.return_value = Mock()

        with patch('lamia.facade.lamia.LamiaEngine', return_value=mock_engine):
            with patch('lamia.facade.lamia.asyncio.get_running_loop', side_effect=RuntimeError):
                lamia = Lamia("openai:gpt-4o")
                del lamia

        # Should use asyncio.run for cleanup
        mock_asyncio_run.assert_called()


# ============================================================================
# COMMAND PROCESSOR TESTS
# ============================================================================

class TestCommandProcessor:
    """Test command processing utilities."""

    @patch('lamia.facade.command_processor.run_python_code')
    def test_process_string_command_python_success(self, mock_run_python):
        """Test processing string command with successful Python execution."""
        mock_run_python.return_value = 42

        command, result = process_string_command("2 + 2")

        assert command is None
        assert isinstance(result, LamiaResult)
        assert result.typed_result == 42
        assert result.result_text == "42"
        assert result.tracking_context.data_provider_name == "python"

    @patch('lamia.facade.command_processor.run_python_code')
    @patch('lamia.facade.command_processor.CommandParser')
    def test_process_string_command_python_syntax_error(self, mock_parser, mock_run_python):
        """Test processing string command with Python syntax error falls back to parsing."""
        mock_run_python.side_effect = SyntaxError("invalid syntax")
        mock_command = Command(command_type=CommandType.LLM, content="test")
        mock_parser_instance = Mock()
        mock_parser_instance.parsed_command = mock_command
        mock_parser.return_value = mock_parser_instance

        command, result = process_string_command("invalid python $$")

        assert command == mock_command
        assert result is None
        mock_parser.assert_called_once_with("invalid python $$")

    @patch('lamia.facade.command_processor.run_python_code')
    @patch('lamia.facade.command_processor.CommandParser')
    def test_process_string_command_python_runtime_error(self, mock_parser, mock_run_python):
        """Test processing string command with Python runtime error falls back to parsing."""
        mock_run_python.side_effect = Exception("division by zero")
        mock_command = Command(command_type=CommandType.LLM, content="test")
        mock_parser_instance = Mock()
        mock_parser_instance.parsed_command = mock_command
        mock_parser.return_value = mock_parser_instance

        command, result = process_string_command("1 / 0")

        assert command == mock_command
        assert result is None

    @patch('lamia.facade.command_processor.run_python_code')
    def test_process_string_command_python_none_result(self, mock_run_python):
        """Test processing string command with None result from Python."""
        mock_run_python.return_value = None

        command, result = process_string_command("print('hello')")

        assert command is None
        assert isinstance(result, LamiaResult)
        assert result.typed_result is None
        assert result.result_text == ""

    @patch('lamia.facade.command_processor.run_python_code')
    @patch('lamia.facade.command_processor.CommandParser')
    def test_process_string_command_llm_command(self, mock_parser, mock_run_python):
        """Test processing LLM command (not Python code)."""
        mock_run_python.side_effect = SyntaxError("not python")
        mock_command = Command(command_type=CommandType.LLM, content="Generate a joke")
        mock_parser_instance = Mock()
        mock_parser_instance.parsed_command = mock_command
        mock_parser.return_value = mock_parser_instance

        command, result = process_string_command("Generate a joke")

        assert command == mock_command
        assert result is None
        assert command.content == "Generate a joke"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@pytest.mark.asyncio
class TestFacadeIntegration:
    """Integration tests for Facade module."""

    @patch('lamia.facade.lamia.build_config_from_models')
    @patch('lamia.facade.lamia.process_string_command')
    async def test_end_to_end_llm_request(self, mock_process, mock_build_config, mock_engine):
        """Test end-to-end LLM request flow."""
        mock_build_config.return_value = Mock()
        mock_command = Command(command_type=CommandType.LLM, content="Generate text")
        mock_process.return_value = (mock_command, None)

        with patch('lamia.facade.lamia.LamiaEngine', return_value=mock_engine):
            lamia = Lamia("openai:gpt-4o")

            # Test async version
            result_async = await lamia.run_async("Generate a joke")
            assert result_async == "Processed result"

            # Test sync version
            result_sync = lamia.run("Generate a joke")
            assert result_sync == "Processed result"

    @patch('lamia.facade.lamia.build_config_from_models')
    @patch('lamia.facade.lamia.process_string_command')
    async def test_end_to_end_python_execution(self, mock_process, mock_build_config, mock_engine):
        """Test end-to-end Python execution flow."""
        mock_build_config.return_value = Mock()
        python_result = LamiaResult(
            result_text="4",
            typed_result=4,
            tracking_context=TrackingContext(
                data_provider_name="python",
                command_type="python"
            )
        )
        mock_process.return_value = (None, python_result)

        with patch('lamia.facade.lamia.LamiaEngine', return_value=mock_engine):
            lamia = Lamia("openai:gpt-4o")
            result = await lamia.run_async("2 + 2")

        assert result == python_result
        # Engine should not be called for Python results
        mock_engine.execute.assert_not_called()

    @patch('lamia.facade.lamia.build_config_from_models')
    async def test_end_to_end_with_context_manager(self, mock_build_config, mock_engine):
        """Test end-to-end flow with async context manager."""
        mock_build_config.return_value = Mock()

        with patch('lamia.facade.lamia.LamiaEngine', return_value=mock_engine):
            async with Lamia("openai:gpt-4o") as lamia:
                command = Command(command_type=CommandType.LLM, content="test")
                result = await lamia.run_async(command)

                assert result == "Processed result"

        # Cleanup should be called
        mock_engine.cleanup.assert_called_once()

    @patch('lamia.facade.lamia.build_config_from_models')
    @patch('lamia.facade.lamia.process_string_command')
    async def test_end_to_end_model_override(self, mock_process, mock_build_config, mock_engine):
        """Test end-to-end with model override."""
        mock_build_config.return_value = Mock()
        mock_command = Command(command_type=CommandType.LLM, content="test")
        mock_process.return_value = (mock_command, None)

        with patch('lamia.facade.lamia.LamiaEngine', return_value=mock_engine):
            lamia = Lamia("openai:gpt-4o")
            result = await lamia.run_async(
                "Generate text",
                models=("anthropic:claude-3", 2)  # Model with priority
            )

        # Should override and reset
        mock_engine.config_provider.override_model_chain_with.assert_called_once()
        mock_engine.config_provider.reset_model_chain.assert_called_once()
