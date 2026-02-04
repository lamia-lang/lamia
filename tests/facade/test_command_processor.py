from unittest.mock import Mock, patch

from lamia.facade.command_processor import process_string_command
from lamia.facade.result_types import LamiaResult
from lamia.interpreter.commands import LLMCommand


@patch('lamia.facade.command_processor.run_python_code')
def test_process_string_command_python_success(mock_run_python):
    mock_run_python.return_value = 42

    command, result = process_string_command("2 + 2")

    assert command is None
    assert isinstance(result, LamiaResult)
    assert result.typed_result == 42
    assert result.result_text == "42"
    assert result.tracking_context.data_provider_name == "python"


@patch('lamia.facade.command_processor.run_python_code')
@patch('lamia.facade.command_processor.CommandParser')
def test_process_string_command_python_syntax_error_fallback(mock_parser, mock_run_python):
    mock_run_python.side_effect = SyntaxError("invalid syntax")
    mock_command = LLMCommand("test")
    mock_parser_instance = Mock()
    mock_parser_instance.parsed_command = mock_command
    mock_parser.return_value = mock_parser_instance

    command, result = process_string_command("invalid python $$")

    assert command == mock_command
    assert result is None
    mock_parser.assert_called_once_with("invalid python $$")


@patch('lamia.facade.command_processor.run_python_code')
@patch('lamia.facade.command_processor.CommandParser')
def test_process_string_command_python_runtime_error_fallback(mock_parser, mock_run_python):
    mock_run_python.side_effect = Exception("division by zero")
    mock_command = LLMCommand("test")
    mock_parser_instance = Mock()
    mock_parser_instance.parsed_command = mock_command
    mock_parser.return_value = mock_parser_instance

    command, result = process_string_command("1 / 0")

    assert command == mock_command
    assert result is None


@patch('lamia.facade.command_processor.run_python_code')
def test_process_string_command_python_none_result(mock_run_python):
    mock_run_python.return_value = None

    command, result = process_string_command("print('hello')")

    assert command is None
    assert isinstance(result, LamiaResult)
    assert result.typed_result is None
    assert result.result_text == ""
