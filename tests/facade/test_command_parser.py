from unittest.mock import AsyncMock, MagicMock

import pytest

from lamia import Lamia
from lamia.facade.command_parser import CommandParser
from lamia.facade.result_types import LamiaResult
from lamia.interpreter.commands import LLMCommand, WebCommand, FileCommand, WebActionType, FileActionType


def test_parses_llm_command_by_default():
    parser = CommandParser("Generate a joke")

    assert isinstance(parser.parsed_command, LLMCommand)
    assert parser.parsed_command.prompt == "Generate a joke"
    assert parser.return_type is None


def test_parses_web_command_from_url():
    parser = CommandParser("https://example.com")

    assert isinstance(parser.parsed_command, WebCommand)
    assert parser.parsed_command.action == WebActionType.NAVIGATE
    assert parser.parsed_command.url == "https://example.com"


def test_parses_file_command_from_path():
    parser = CommandParser("/tmp/file.txt")

    assert isinstance(parser.parsed_command, FileCommand)
    assert parser.parsed_command.action == FileActionType.READ
    assert parser.parsed_command.path == "/tmp/file.txt"


def test_parses_return_type_suffix():
    parser = CommandParser("Generate->JSON")

    assert isinstance(parser.parsed_command, LLMCommand)
    assert parser.return_type == "JSON"


def test_use_cases_preserve_command_text():
    commands = [
        "https://example.com",
        "Navigate to https://google.com",
        "Click on the login button",
        "Type 'username' into the email field",
        "Submit the form",
        "file:///home/user/document.txt",
        "Read the configuration file",
        "Write data to output.json",
        "Delete temporary files",
        "What is the weather today?",
        "Explain quantum computing",
        "Write a Python function to sort a list",
        "Translate 'hello' to Spanish",
        "Summarize the following text: ...",
        "Search for 'lamia automation' on https://github.com",
        "Read file:///data/users.json and count the entries",
        "Navigate to the admin panel and download the report",
        "Analyze the content of https://api.example.com/data"
    ]

    for command in commands:
        parser = CommandParser(command)
        assert parser.command == command


def test_preserves_input_text():
    cases = [
        "https://example.com",
        "file:///path/to/file.txt",
        "Hello world",
        "",
    ]

    for command in cases:
        parser = CommandParser(command)
        assert parser.command == command


def test_preserves_unicode_and_emojis():
    unicode_commands = [
        "Command with émojis 🚀",
        "Здравствуй мир",  # Russian
        "こんにちは世界",  # Japanese
        "مرحبا بالعالم",  # Arabic
        "🌍🌎🌏",  # Emojis only
        "café naïve résumé",  # Accented characters
        "Command with\nnewlines",
        "Command with\ttabs",
    ]

    for command in unicode_commands:
        parser = CommandParser(command)
        assert parser.command == command


# =============================================================================
# INTEGRATION TESTS: Lamia class integration with CommandParser
# =============================================================================


class TestLamiaCommandParsingIntegration:
    """Test Lamia's integration with CommandParser."""

    @pytest.fixture
    def lamia(self):
        """Create a Lamia instance for testing."""
        return Lamia("ollama")

    def test_fs_command_parsing(self, lamia):
        """Test that filesystem commands are parsed and dispatched correctly."""
        mock_result = MagicMock()
        mock_result.result_type = "file content"
        lamia._engine.execute = AsyncMock(return_value=mock_result)

        lamia.run("/tmp/file.txt")

        lamia._engine.execute.assert_called_once()
        command = lamia._engine.execute.call_args[0][0]
        assert isinstance(command, FileCommand)
        assert command.action == FileActionType.READ
        assert command.path == "/tmp/file.txt"

    def test_web_command_parsing(self, lamia):
        """Test that web commands are parsed and dispatched correctly."""
        mock_result = MagicMock()
        mock_result.result_type = "page content"
        lamia._engine.execute = AsyncMock(return_value=mock_result)

        lamia.run("https://example.com")

        lamia._engine.execute.assert_called_once()
        command = lamia._engine.execute.call_args[0][0]
        assert isinstance(command, WebCommand)
        assert command.action == WebActionType.NAVIGATE
        assert command.url == "https://example.com"

    def test_llm_command_parsing(self, lamia):
        """Test that LLM commands are parsed and dispatched correctly."""
        mock_result = MagicMock()
        mock_result.result_type = "weather info"
        lamia._engine.execute = AsyncMock(return_value=mock_result)

        lamia.run("What is the weather today?")

        lamia._engine.execute.assert_called_once()
        command = lamia._engine.execute.call_args[0][0]
        assert isinstance(command, LLMCommand)
        assert command.prompt == "What is the weather today?"

    def test_python_code_bypasses_parser(self, lamia):
        """Test that Python code bypasses the command parser and engine."""
        lamia._engine.execute = AsyncMock()

        result = lamia.run("print('Hello World')")
        assert isinstance(result, LamiaResult)
        assert result.result_text == ""

        result = lamia.run("2 + 2")
        assert isinstance(result, LamiaResult)
        assert result.result_text == "4"

        lamia._engine.execute.assert_not_called()