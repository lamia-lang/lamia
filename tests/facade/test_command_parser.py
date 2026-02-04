from lamia.facade.command_parser import CommandParser
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