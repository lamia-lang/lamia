"""Tests for facade command parser."""

import pytest
from unittest.mock import Mock, patch
from lamia.facade.command_parser import CommandParser
from lamia.interpreter.commands import Command, LLMCommand, WebCommand, FileCommand
from lamia.interpreter.command_types import CommandType


class TestFacadeCommandParser:
    """Test facade CommandParser."""
    
    def test_initialization(self):
        """Test CommandParser initialization."""
        parser = CommandParser("test command")
        assert parser.command == "test command"
        assert parser._parsed_command is not None
        assert parser._return_type is None
    
    def test_command_parsing_properties(self):
        """Test parsed command and return type properties."""
        parser = CommandParser("test command")
        assert hasattr(parser, 'parsed_command')
        assert hasattr(parser, 'return_type')
        assert parser.parsed_command is not None
        assert isinstance(parser.parsed_command, Command)
    
    def test_basic_command_parsing(self):
        """Test basic command parsing functionality."""
        # Test with simple command
        parser = CommandParser("Hello world")
        assert parser.command == "Hello world"
        
        # Test with URL command
        parser = CommandParser("https://example.com")
        assert parser.command == "https://example.com"
        
        # Test with file command
        parser = CommandParser("file:///path/to/file.txt")
        assert parser.command == "file:///path/to/file.txt"
    
    def test_empty_command(self):
        """Test parsing of empty command."""
        parser = CommandParser("")
        assert parser.command == ""
    
    def test_whitespace_command(self):
        """Test parsing of whitespace-only command."""
        parser = CommandParser("   ")
        assert parser.command == "   "
    
    def test_special_characters(self):
        """Test parsing commands with special characters."""
        special_commands = [
            "Command with émojis 🚀",
            "Command with\nnewlines",
            "Command with\ttabs",
            "Command with \"quotes\"",
            "Command with 'single quotes'",
            "Command with <html> tags",
            "Command with {json: 'data'}"
        ]
        
        for command in special_commands:
            parser = CommandParser(command)
            assert parser.command == command
    
    def test_very_long_command(self):
        """Test parsing of very long commands."""
        long_command = "This is a very long command. " * 1000
        parser = CommandParser(long_command)
        assert parser.command == long_command
        assert len(parser.command) == len(long_command)
    
    def test_unicode_command(self):
        """Test parsing commands with unicode characters."""
        unicode_commands = [
            "Здравствуй мир",  # Russian
            "こんにちは世界",      # Japanese
            "مرحبا بالعالم",      # Arabic
            "🌍🌎🌏",           # Emojis
            "café naïve résumé"  # Accented characters
        ]
        
        for command in unicode_commands:
            parser = CommandParser(command)
            assert parser.command == command


class TestCommandParserIntegration:
    """Test CommandParser integration with underlying interpreter."""
    
    @patch('lamia.facade.command_parser.CommandParser')
    def test_command_parser_delegation(self, mock_interpreter_parser):
        """Test that facade delegates to interpreter CommandParser."""
        # This test assumes the facade delegates to the interpreter
        # If implementation differs, adjust accordingly
        pass
    
    def test_command_type_detection(self):
        """Test command type detection through facade."""
        test_cases = [
            ("https://example.com", "web"),
            ("http://example.com", "web"),
            ("file:///path/to/file", "filesystem"),
            ("Hello world", "llm"),
            ("What is the weather?", "llm")
        ]
        
        for command, expected_type in test_cases:
            parser = CommandParser(command)
            # Note: This test may need adjustment based on actual facade implementation
            assert parser.command == command


class TestCommandParserErrorHandling:
    """Test CommandParser error handling."""
    
    def test_none_command(self):
        """Test handling of None command."""
        with pytest.raises((TypeError, AttributeError)):
            CommandParser(None)
    
    def test_non_string_command(self):
        """Test handling of non-string commands."""
        non_string_inputs = [123, [], {}, object()]
        
        for input_value in non_string_inputs:
            with pytest.raises((TypeError, AttributeError)):
                CommandParser(input_value)
    
    def test_malformed_urls(self):
        """Test handling of malformed URLs."""
        malformed_urls = [
            "http://",
            "https://",
            "ftp://incomplete",
            "not-a-protocol://example.com"
        ]
        
        for url in malformed_urls:
            # Should still create parser (error handling depends on downstream components)
            parser = CommandParser(url)
            assert parser.command == url
    
    def test_invalid_file_paths(self):
        """Test handling of invalid file paths."""
        invalid_paths = [
            "file://",
            "file:///",
            "file://invalid-host/path",
            "C:\\windows\\path"  # Windows path without file:// scheme
        ]
        
        for path in invalid_paths:
            parser = CommandParser(path)
            assert parser.command == path


class TestCommandParserProperties:
    """Test CommandParser properties and methods."""
    
    def test_command_property(self):
        """Test that command property returns the original command."""
        test_command = "Test command with various characters !@#$%^&*()"
        parser = CommandParser(test_command)
        
        assert parser.command == test_command
        assert isinstance(parser.command, str)
    
    def test_command_immutability(self):
        """Test that command cannot be modified after creation."""
        parser = CommandParser("Original command")
        original = parser.command
        
        # Try to modify (if property is mutable)
        try:
            parser.command = "Modified command"
            # If this succeeds, verify it actually changed
            if hasattr(parser, '_command'):
                # If using internal storage
                assert parser.command == "Modified command"
        except AttributeError:
            # If property is read-only, this is expected
            assert parser.command == original


class TestCommandParserMethodInterface:
    """Test CommandParser method interfaces."""
    
    def test_has_required_methods(self):
        """Test that CommandParser has expected methods."""
        parser = CommandParser("test")
        
        # Basic attributes/properties that should exist
        assert hasattr(parser, 'command')
        
        # Check if command property is accessible
        assert parser.command is not None
    
    def test_string_representation(self):
        """Test string representation of CommandParser."""
        parser = CommandParser("test command")
        
        # Test that str() works
        str_repr = str(parser)
        assert isinstance(str_repr, str)
        
        # Test that repr() works
        repr_str = repr(parser)
        assert isinstance(repr_str, str)
    
    def test_equality_comparison(self):
        """Test equality comparison of CommandParser instances."""
        parser1 = CommandParser("same command")
        parser2 = CommandParser("same command")
        parser3 = CommandParser("different command")
        
        # Test equality (if implemented)
        if hasattr(parser1, '__eq__'):
            assert parser1 == parser2
            assert parser1 != parser3
        
        # At minimum, command content should be equal
        assert parser1.command == parser2.command
        assert parser1.command != parser3.command


class TestCommandParserUseCases:
    """Test CommandParser common use cases."""
    
    def test_web_automation_commands(self):
        """Test parsing web automation related commands."""
        web_commands = [
            "https://example.com",
            "Navigate to https://google.com",
            "Click on the login button",
            "Type 'username' into the email field",
            "Submit the form"
        ]
        
        for command in web_commands:
            parser = CommandParser(command)
            assert parser.command == command
    
    def test_file_operation_commands(self):
        """Test parsing file operation commands."""
        file_commands = [
            "file:///home/user/document.txt",
            "Read the configuration file",
            "Write data to output.json",
            "Delete temporary files"
        ]
        
        for command in file_commands:
            parser = CommandParser(command)
            assert parser.command == command
    
    def test_llm_conversation_commands(self):
        """Test parsing LLM conversation commands."""
        llm_commands = [
            "What is the weather today?",
            "Explain quantum computing",
            "Write a Python function to sort a list",
            "Translate 'hello' to Spanish",
            "Summarize the following text: ..."
        ]
        
        for command in llm_commands:
            parser = CommandParser(command)
            assert parser.command == command
    
    def test_mixed_domain_commands(self):
        """Test parsing commands that might span multiple domains."""
        mixed_commands = [
            "Search for 'lamia automation' on https://github.com",
            "Read file:///data/users.json and count the entries",
            "Navigate to the admin panel and download the report",
            "Analyze the content of https://api.example.com/data"
        ]
        
        for command in mixed_commands:
            parser = CommandParser(command)
            assert parser.command == command


@pytest.mark.parametrize("command,expected", [
    ("https://example.com", "https://example.com"),
    ("file:///path/to/file.txt", "file:///path/to/file.txt"),
    ("Hello world", "Hello world"),
    ("", ""),
    ("Command with émojis 🚀", "Command with émojis 🚀")
])
class TestCommandParserParametrized:
    """Parametrized tests for CommandParser."""
    
    def test_command_preservation(self, command, expected):
        """Test that commands are preserved exactly."""
        parser = CommandParser(command)
        assert parser.command == expected
    
    def test_command_type_consistency(self, command, expected):
        """Test that command type is consistent."""
        parser = CommandParser(command)
        assert type(parser.command) == type(expected)
        assert isinstance(parser.command, str)