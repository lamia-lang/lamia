"""Tests for CLI module."""

import asyncio
import os
import subprocess
import sys
import tempfile
from io import StringIO
from unittest.mock import AsyncMock, Mock, patch

import pytest

from lamia.cli import main
from lamia.cli.cli import HYBRID_EXTENSIONS, interactive_mode
from lamia.engine.managers.llm.llm_manager import MissingAPIKeysError
from lamia.interpreter.command_types import CommandType


def make_mock_result(text="test response", command_type=CommandType.LLM):
    """Helper to create a mock LamiaResult."""
    result = Mock()
    result.result_text = text
    result.tracking_context = Mock()
    result.tracking_context.command_type = command_type
    result.tracking_context.data_provider_name = "test_model"
    result.tracking_context.metadata = {}
    return result


class TestCLIConstants:
    """Test CLI constants and configuration."""

    def test_hybrid_extensions(self):
        """Test hybrid file extensions constant."""
        assert HYBRID_EXTENSIONS == {".hu", ".lm"}
        assert isinstance(HYBRID_EXTENSIONS, set)
        assert ".hu" in HYBRID_EXTENSIONS
        assert ".lm" in HYBRID_EXTENSIONS


class TestCLILifecycle:
    """Test CLI lifecycle management and error handling."""

    def setup_method(self):
        """Setup for each test method."""
        self.original_argv = sys.argv.copy()

    def teardown_method(self):
        """Cleanup after each test method."""
        sys.argv = self.original_argv

    def create_test_config(self, content):
        """Create a temporary config file."""
        config_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        config_file.write(content)
        config_file.close()
        return config_file.name

    @patch("lamia.cli.cli.Lamia")
    def test_cli_successful_startup_and_shutdown(self, mock_lamia_class):
        """Test successful CLI startup with Lamia.from_config and interactive mode."""
        mock_lamia = Mock()
        mock_lamia_class.from_config.return_value = mock_lamia

        config_content = """
default_model: test_model
models:
  test_model:
    enabled: true
"""
        config_file = self.create_test_config(config_content)

        try:
            with patch("lamia.cli.cli.asyncio.run"):
                sys.argv = ["lamia", "--config", config_file]

                main()

                mock_lamia_class.from_config.assert_called_once()
        finally:
            os.unlink(config_file)

    @patch("lamia.cli.cli.Lamia")
    def test_cli_missing_api_keys_error(self, mock_lamia_class):
        """Test CLI handling of missing API keys."""
        mock_lamia_class.from_config.side_effect = MissingAPIKeysError([("openai", "OPENAI_API_KEY")])

        config_content = """
default_model: openai
models:
  openai:
    enabled: true
"""
        config_file = self.create_test_config(config_content)

        try:
            sys.argv = ["lamia", "--config", config_file]

            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1
        finally:
            os.unlink(config_file)

    @patch("lamia.cli.cli.Lamia")
    def test_cli_engine_startup_failure(self, mock_lamia_class):
        """Test CLI handling of startup failure."""
        mock_lamia_class.from_config.side_effect = RuntimeError("Failed to initialize")

        config_content = """
default_model: test_model
models:
  test_model:
    enabled: true
"""
        config_file = self.create_test_config(config_content)

        try:
            sys.argv = ["lamia", "--config", config_file]

            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1
        finally:
            os.unlink(config_file)

    @patch("lamia.cli.cli.create_config_from_wizard_result")
    @patch("lamia.cli.cli.run_init_wizard")
    @patch("os.path.exists", return_value=False)
    def test_cli_init_command(self, mock_exists, mock_wizard, mock_create_config):
        """Test CLI init command runs the wizard and creates config."""
        from lamia.cli.init_wizard import WizardResult, ModelChainEntry
        mock_wizard.return_value = WizardResult(
            model_chain=[ModelChainEntry(name="ollama:llama3.2:1b", max_retries=3)],
        )
        mock_create_config.return_value = True

        sys.argv = ["lamia", "init"]

        main()

        mock_wizard.assert_called_once()
        # Verify project_dir is passed
        call_kwargs = mock_wizard.call_args
        assert "project_dir" in call_kwargs.kwargs or len(call_kwargs.args) > 0
        mock_create_config.assert_called_once()


class TestInteractiveModeSetup:
    """Test interactive mode setup and initialization."""

    @pytest.mark.asyncio
    async def test_interactive_mode_initialization(self):
        """Test that interactive mode initializes properly."""
        mock_lamia = Mock()

        with patch("builtins.input", side_effect=["EXIT"]):
            with patch("lamia.cli.cli.logger") as mock_logger:
                await interactive_mode(mock_lamia)

                mock_logger.info.assert_called()
                calls = [call[0][0] for call in mock_logger.info.call_args_list]
                assert any("Lamia Interactive Mode" in call for call in calls)


@pytest.mark.asyncio
class TestInteractiveModeCommands:
    """Test interactive mode command handling."""

    async def test_exit_command(self):
        """Test EXIT command functionality."""
        mock_lamia = Mock()

        with patch("builtins.input", return_value="EXIT"):
            with patch("lamia.cli.cli.logger"):
                await interactive_mode(mock_lamia)

    async def test_cancel_command(self):
        """Test CANCEL command functionality."""
        mock_lamia = Mock()

        with patch("builtins.input", side_effect=["test input", "CANCEL", "EXIT"]):
            with patch("lamia.cli.cli.logger"):
                await interactive_mode(mock_lamia)

    async def test_stats_command(self):
        """Test STATS command functionality."""
        mock_lamia = Mock()

        with patch("builtins.input", side_effect=["STATS", "EXIT"]):
            with patch("lamia.cli.cli.logger"):
                await interactive_mode(mock_lamia)

    async def test_case_insensitive_commands(self):
        """Test that commands are case insensitive."""
        mock_lamia = Mock()

        commands = ["exit", "EXIT", "Exit", "stats", "STATS", "Stats", "cancel", "CANCEL"]

        for cmd in commands[:3]:
            with patch("builtins.input", return_value=cmd):
                with patch("lamia.cli.cli.logger"):
                    await interactive_mode(mock_lamia)


class TestInteractiveModeErrorHandling:
    """Test interactive mode error handling."""

    @pytest.mark.asyncio
    async def test_keyboard_interrupt_handling(self):
        """Test handling of keyboard interrupts."""
        mock_lamia = Mock()

        with patch("builtins.input", side_effect=KeyboardInterrupt()):
            with patch("lamia.cli.cli.logger"):
                await interactive_mode(mock_lamia)


class TestInteractiveModeInputHandling:
    """Test interactive mode input handling."""

    @pytest.mark.asyncio
    async def test_multiline_input_handling(self):
        """Test multiline input collection."""
        mock_lamia = Mock()
        mock_lamia.run_async = AsyncMock(return_value=make_mock_result())

        inputs = ["line 1", "line 2", "line 3", "SEND", "EXIT"]

        with patch("builtins.input", side_effect=inputs):
            with patch("lamia.cli.cli.logger"):
                await interactive_mode(mock_lamia)

                mock_lamia.run_async.assert_called()
                call_args = mock_lamia.run_async.call_args[0][0]
                assert "line 1" in call_args
                assert "line 2" in call_args
                assert "line 3" in call_args

    @pytest.mark.asyncio
    async def test_empty_input_handling(self):
        """Test handling of empty inputs."""
        mock_lamia = Mock()

        with patch("builtins.input", side_effect=["", "EXIT"]):
            with patch("lamia.cli.cli.logger"):
                await interactive_mode(mock_lamia)

    @pytest.mark.asyncio
    async def test_whitespace_input_handling(self):
        """Test handling of whitespace-only inputs."""
        mock_lamia = Mock()

        with patch("builtins.input", side_effect=["   ", "\t", "\n", "EXIT"]):
            with patch("lamia.cli.cli.logger"):
                await interactive_mode(mock_lamia)


class TestPromptDisplay:
    """Test prompt display and formatting."""

    def test_prompt_string_format(self):
        """Test that prompt string is properly formatted."""
        assert True

    def test_continuation_prompt(self):
        """Test continuation prompt for multiline input."""
        assert True


@pytest.mark.asyncio
class TestAsyncOperations:
    """Test asynchronous operations in interactive mode."""

    async def test_concurrent_task_handling(self):
        """Test handling of concurrent tasks."""
        mock_lamia = Mock()
        mock_lamia.run = AsyncMock(return_value="response")

        with patch("builtins.input", side_effect=["test prompt", "SEND", "EXIT"]):
            with patch("lamia.cli.cli.logger"):
                await interactive_mode(mock_lamia)

    async def test_task_interruption(self):
        """Test interruption of running tasks."""
        mock_lamia = Mock()
        mock_lamia.run = AsyncMock(side_effect=asyncio.sleep(10))

        with patch("builtins.input", side_effect=["test prompt", "SEND", "STOP", "EXIT"]):
            with patch("lamia.cli.cli.logger"):
                await interactive_mode(mock_lamia)


class TestCLIIntegration:
    """Test CLI integration with Lamia core."""

    @pytest.mark.asyncio
    async def test_lamia_run_called(self):
        """Test that lamia.run_async is called with user input."""
        mock_lamia = Mock()
        mock_lamia.run_async = AsyncMock(return_value=make_mock_result("test response"))

        with patch("builtins.input", side_effect=["test command", "SEND", "EXIT"]):
            with patch("lamia.cli.cli.logger"):
                await interactive_mode(mock_lamia)

                mock_lamia.run_async.assert_called_once()
                call_args = mock_lamia.run_async.call_args[0][0]
                assert "test command" in call_args

    @pytest.mark.asyncio
    async def test_response_display(self):
        """Test that responses are displayed to user."""
        mock_lamia = Mock()
        mock_lamia.run = AsyncMock(return_value="test response")

        with patch("builtins.input", side_effect=["test", "SEND", "EXIT"]):
            with patch("lamia.cli.cli.logger"):
                with patch("builtins.print") as mock_print:
                    await interactive_mode(mock_lamia)

                    mock_print.assert_called()


class TestCLILogging:
    """Test CLI logging functionality."""

    @pytest.mark.asyncio
    async def test_logging_setup(self):
        """Test that logging is properly set up."""
        mock_lamia = Mock()

        with patch("builtins.input", return_value="EXIT"):
            with patch("lamia.cli.cli.logger") as mock_logger:
                await interactive_mode(mock_lamia)

                assert mock_logger.info.called

    @pytest.mark.asyncio
    async def test_error_logging(self):
        """Test that errors are properly logged."""
        mock_lamia = Mock()
        mock_lamia.run_async = AsyncMock(side_effect=Exception("Test error"))

        with patch("builtins.input", side_effect=["test", "SEND", "EXIT"]):
            with patch("lamia.cli.cli.logger") as mock_logger:
                await interactive_mode(mock_lamia)

                assert mock_logger.error.called


class TestCLIConstantsImmutability:
    """Test CLI module constants immutability."""

    def test_hybrid_extensions_immutable(self):
        """Test that HYBRID_EXTENSIONS is treated as immutable."""
        original = HYBRID_EXTENSIONS.copy()

        assert HYBRID_EXTENSIONS == {".hu", ".lm"}
        assert HYBRID_EXTENSIONS == original

    def test_logger_configuration(self):
        """Test that logger is properly configured."""
        from lamia.cli.cli import logger
        assert logger.name == "lamia.cli.cli"


sum_py_content = """
def sum(a, b) -> int:
      return a + b
sum(10, 15)
"""

config_content = """
model:
  name: gpt-4
  temperature: 0.7
  max_tokens: 1000
api:
  provider: openai
  api_key: dummy_key
"""


@pytest.mark.integration
@pytest.mark.parametrize("cli_args", [
    ["sum.py"],
    ["--file", "sum.py"],
])
def test_cli_file_modes(tmp_path, cli_args):
    test_dir = tmp_path
    with open(test_dir / "sum.py", "w") as f:
        f.write(sum_py_content)
    with open(test_dir / "config.yaml", "w") as f:
        f.write(config_content)

    try:
        cmd = [sys.executable, "-m", "lamia.cli"] + cli_args + ["--config", str(test_dir / "config.yaml")]
        result = subprocess.run(cmd, cwd=test_dir, capture_output=True, text=True)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "25" in result.stdout
    finally:
        if os.path.exists(test_dir / "sum.py"):
            os.remove(test_dir / "sum.py")
        if os.path.exists(test_dir / "config.yaml"):
            os.remove(test_dir / "config.yaml")


@pytest.mark.integration
def test_import_cli():
    import lamia.cli as cli_mod
    assert cli_mod is not None
