"""Tests for CommandParser."""

import pytest
from lamia.interpreter.command_parser import CommandParser
from lamia.interpreter.command_types import CommandType
from lamia.interpreter.commands import Command, LLMCommand, WebCommand, FileCommand, WebActionType, FileActionType


class TestCommandParserInitialization:
    """Test CommandParser initialization."""
    
    def test_initialization_with_simple_command(self):
        """Test initialization with simple command."""
        parser = CommandParser("test command")
        
        assert parser.command == "test command"
        assert parser._parsed_command is not None
        assert parser._return_type is None
    
    def test_initialization_with_return_type(self):
        """Test initialization with return type specified."""
        parser = CommandParser("test command -> string")
        
        assert parser.command == "test command -> string"
        assert parser._parsed_command is not None
        assert parser._return_type == " string"
    
    def test_initialization_triggers_parsing(self):
        """Test that initialization triggers command parsing."""
        parser = CommandParser("https://example.com")
        
        # Should automatically parse and create WebCommand
        assert isinstance(parser.parsed_command, WebCommand)
        assert parser.parsed_command.action == WebActionType.NAVIGATE
        assert parser.parsed_command.url == "https://example.com"


class TestCommandParserReturnTypeHandling:
    """Test return type parsing."""
    
    def test_split_command_and_return_type_with_return_type(self):
        """Test splitting command with return type."""
        parser = CommandParser("dummy")  # Initialize with dummy to access method
        
        content, return_type = parser._split_command_and_return_type()
        
        assert content == "dummy"
        assert return_type is None
    
    def test_split_command_and_return_type_with_arrow(self):
        """Test splitting command with arrow return type."""
        parser = CommandParser("get data -> list")
        
        assert parser.return_type == " list"
        # Check that command content is correctly extracted
        content, return_type = parser._split_command_and_return_type()
        assert content == "get data "
        assert return_type == " list"
    
    def test_split_command_and_return_type_multiple_arrows(self):
        """Test splitting command with multiple arrows (only first split used)."""
        parser = CommandParser("step1 -> step2 -> final")
        
        # Only first arrow is used for return type
        assert parser.return_type == " step2 -> final"
        content, return_type = parser._split_command_and_return_type()
        assert content == "step1 "
        assert return_type == " step2 -> final"
    
    def test_return_type_property(self):
        """Test return_type property access."""
        parser1 = CommandParser("simple command")
        parser2 = CommandParser("command -> int")
        
        assert parser1.return_type is None
        assert parser2.return_type == " int"


class TestCommandParserCommandTypeDetection:
    """Test command type determination."""
    
    def test_determine_command_type_http_url(self):
        """Test HTTP URL detection."""
        parser = CommandParser("dummy")
        parser.command = "http://example.com"
        
        command_type = parser._determine_command_type()
        
        assert command_type == CommandType.WEB
    
    def test_determine_command_type_https_url(self):
        """Test HTTPS URL detection."""
        parser = CommandParser("dummy")
        parser.command = "https://secure.example.com"
        
        command_type = parser._determine_command_type()
        
        assert command_type == CommandType.WEB
    
    def test_determine_command_type_file_uri(self):
        """Test file:// URI detection."""
        parser = CommandParser("dummy")
        parser.command = "file:///path/to/file.txt"
        
        command_type = parser._determine_command_type()
        
        assert command_type == CommandType.FILESYSTEM
    
    def test_determine_command_type_file_path(self):
        """Test file path detection."""
        parser = CommandParser("dummy")
        parser.command = "/path/to/file.txt"
        
        command_type = parser._determine_command_type()
        
        assert command_type == CommandType.FILESYSTEM
    
    def test_determine_command_type_relative_path(self):
        """Test relative file path detection."""
        parser = CommandParser("dummy")
        parser.command = "relative/path/file.txt"
        
        command_type = parser._determine_command_type()
        
        assert command_type == CommandType.FILESYSTEM
    
    def test_determine_command_type_plain_text(self):
        """Test plain text defaults to LLM."""
        parser = CommandParser("dummy")
        parser.command = "analyze this data"
        
        command_type = parser._determine_command_type()
        
        assert command_type == CommandType.LLM
    
    def test_determine_command_type_question(self):
        """Test question defaults to LLM."""
        parser = CommandParser("dummy")
        parser.command = "What is the weather like?"
        
        command_type = parser._determine_command_type()
        
        assert command_type == CommandType.LLM


class TestCommandParserWebCommandParsing:
    """Test web command parsing."""
    
    def test_parse_web_command_http_url(self):
        """Test parsing HTTP URL as web command."""
        parser = CommandParser("http://example.com")
        
        assert isinstance(parser.parsed_command, WebCommand)
        assert parser.parsed_command.action == WebActionType.NAVIGATE
        assert parser.parsed_command.url == "http://example.com"
    
    def test_parse_web_command_https_url(self):
        """Test parsing HTTPS URL as web command."""
        parser = CommandParser("https://secure.example.com")
        
        assert isinstance(parser.parsed_command, WebCommand)
        assert parser.parsed_command.action == WebActionType.NAVIGATE
        assert parser.parsed_command.url == "https://secure.example.com"
    
    def test_parse_web_command_with_return_type(self):
        """Test parsing web command with return type."""
        parser = CommandParser("https://api.example.com -> json")
        
        assert isinstance(parser.parsed_command, WebCommand)
        assert parser.parsed_command.action == WebActionType.NAVIGATE
        assert parser.parsed_command.url == "https://api.example.com "  # Note: includes space from split
        assert parser.return_type == " json"
    
    def test_parse_web_command_complex_url(self):
        """Test parsing complex URL as web command."""
        complex_url = "https://example.com/path/to/resource?param=value&other=data#section"
        parser = CommandParser(complex_url)
        
        assert isinstance(parser.parsed_command, WebCommand)
        assert parser.parsed_command.action == WebActionType.NAVIGATE
        assert parser.parsed_command.url == complex_url


class TestCommandParserFileCommandParsing:
    """Test file command parsing."""
    
    def test_parse_file_command_absolute_path(self):
        """Test parsing absolute file path as file command."""
        parser = CommandParser("/path/to/file.txt")
        
        assert isinstance(parser.parsed_command, FileCommand)
        assert parser.parsed_command.action == FileActionType.READ
        assert parser.parsed_command.path == "/path/to/file.txt"
    
    def test_parse_file_command_relative_path(self):
        """Test parsing relative file path as file command."""
        parser = CommandParser("data/input.csv")
        
        assert isinstance(parser.parsed_command, FileCommand)
        assert parser.parsed_command.action == FileActionType.READ
        assert parser.parsed_command.path == "data/input.csv"
    
    def test_parse_file_command_file_uri(self):
        """Test parsing file:// URI as file command."""
        parser = CommandParser("file:///home/user/document.pdf")
        
        assert isinstance(parser.parsed_command, FileCommand)
        assert parser.parsed_command.action == FileActionType.READ
        assert parser.parsed_command.path == "file:///home/user/document.pdf"
    
    def test_parse_file_command_with_return_type(self):
        """Test parsing file command with return type."""
        parser = CommandParser("/data/config.json -> dict")
        
        assert isinstance(parser.parsed_command, FileCommand)
        assert parser.parsed_command.action == FileActionType.READ
        assert parser.parsed_command.path == "/data/config.json "  # Note: includes space from split
        assert parser.return_type == " dict"


class TestCommandParserLLMCommandParsing:
    """Test LLM command parsing."""
    
    def test_parse_llm_command_plain_text(self):
        """Test parsing plain text as LLM command."""
        parser = CommandParser("Analyze this data and provide insights")
        
        assert isinstance(parser.parsed_command, LLMCommand)
        assert parser.parsed_command.prompt == "Analyze this data and provide insights"
    
    def test_parse_llm_command_question(self):
        """Test parsing question as LLM command."""
        parser = CommandParser("What are the key trends in this dataset?")
        
        assert isinstance(parser.parsed_command, LLMCommand)
        assert parser.parsed_command.prompt == "What are the key trends in this dataset?"
    
    def test_parse_llm_command_with_return_type(self):
        """Test parsing LLM command with return type."""
        parser = CommandParser("Summarize the main points -> list")
        
        assert isinstance(parser.parsed_command, LLMCommand)
        assert parser.parsed_command.prompt == "Summarize the main points "  # Note: includes space from split
        assert parser.return_type == " list"
    
    def test_parse_llm_command_complex_instruction(self):
        """Test parsing complex instruction as LLM command."""
        instruction = "Compare the performance metrics between Q1 and Q2, focusing on revenue growth"
        parser = CommandParser(instruction)
        
        assert isinstance(parser.parsed_command, LLMCommand)
        assert parser.parsed_command.prompt == instruction


class TestCommandParserFallbackBehavior:
    """Test fallback behavior when parsing fails."""
    
    def test_web_command_fallback_to_llm(self):
        """Test web command parsing fallback to LLM on error."""
        # Create a parser and manually set up a scenario where web parsing would fail
        parser = CommandParser("dummy")
        parser.command = "https://example.com"
        
        # Mock the web command parsing to raise ValueError
        original_method = parser._parse_web_command
        def failing_parse_web_command(content):
            raise ValueError("Web parsing failed")
        parser._parse_web_command = failing_parse_web_command
        
        # Re-parse with the failing method
        parser._parse()
        
        # Should fallback to LLM command
        assert isinstance(parser.parsed_command, LLMCommand)
        assert parser.parsed_command.prompt == "https://example.com"
        
        # Restore original method
        parser._parse_web_command = original_method
    
    def test_file_command_fallback_to_llm(self):
        """Test file command parsing fallback to LLM on error."""
        # Create a parser and manually set up a scenario where file parsing would fail
        parser = CommandParser("dummy")
        parser.command = "/path/to/file.txt"
        
        # Mock the file command parsing to raise ValueError
        original_method = parser._parse_file_command
        def failing_parse_file_command(content):
            raise ValueError("File parsing failed")
        parser._parse_file_command = failing_parse_file_command
        
        # Re-parse with the failing method
        parser._parse()
        
        # Should fallback to LLM command
        assert isinstance(parser.parsed_command, LLMCommand)
        assert parser.parsed_command.prompt == "/path/to/file.txt"
        
        # Restore original method
        parser._parse_file_command = original_method


class TestCommandParserEdgeCases:
    """Test edge cases and special inputs."""
    
    def test_empty_command(self):
        """Test parsing empty command."""
        parser = CommandParser("")
        
        assert isinstance(parser.parsed_command, LLMCommand)
        assert parser.parsed_command.prompt == ""
        assert parser.return_type is None
    
    def test_whitespace_only_command(self):
        """Test parsing whitespace-only command."""
        parser = CommandParser("   ")
        
        assert isinstance(parser.parsed_command, LLMCommand)
        assert parser.parsed_command.prompt == "   "
    
    def test_command_with_only_return_type_arrow(self):
        """Test parsing command with only return type arrow."""
        parser = CommandParser(" -> string")
        
        assert parser.parsed_command.prompt == " "  # prompt before arrow
        assert parser.return_type == " string"
    
    def test_url_like_but_not_url(self):
        """Test parsing URL-like text that's not actually a URL."""
        parser = CommandParser("search for http://example patterns")
        
        # Current implementation treats any string with / as file path
        assert isinstance(parser.parsed_command, FileCommand)
        assert parser.parsed_command.path == "search for http://example patterns"
    
    def test_path_like_but_not_path(self):
        """Test parsing path-like text that's not actually a path."""
        parser = CommandParser("find files with / in the name")
        
        # Current implementation treats any string with / as file path
        assert isinstance(parser.parsed_command, FileCommand)
        assert parser.parsed_command.path == "find files with / in the name"
    
    def test_command_with_special_characters(self):
        """Test parsing command with special characters (no slash)."""
        command = "Process data: items = [1, 2, 3]; filter(lambda x: x > 1)"
        parser = CommandParser(command)
        
        assert isinstance(parser.parsed_command, LLMCommand)
        assert parser.parsed_command.prompt == command


class TestCommandParserPropertyAccess:
    """Test property access methods."""
    
    def test_parsed_command_property(self):
        """Test parsed_command property access."""
        parser = CommandParser("test command")
        
        command = parser.parsed_command
        
        assert isinstance(command, LLMCommand)
        assert command.prompt == "test command"
    
    def test_parsed_command_property_immutable(self):
        """Test that parsed_command property returns the same object."""
        parser = CommandParser("https://example.com")
        
        command1 = parser.parsed_command
        command2 = parser.parsed_command
        
        assert command1 is command2
    
    def test_return_type_property_none(self):
        """Test return_type property when no return type specified."""
        parser = CommandParser("simple command")
        
        assert parser.return_type is None
    
    def test_return_type_property_with_value(self):
        """Test return_type property when return type specified."""
        parser = CommandParser("command -> list")
        
        assert parser.return_type == " list"


class TestCommandParserIntegration:
    """Test integration scenarios."""
    
    def test_complete_workflow_web_command(self):
        """Test complete workflow for web command parsing."""
        url = "https://api.github.com/repos/user/repo"
        parser = CommandParser(f"{url} -> json")
        
        # Verify complete parsing workflow
        assert parser.command == f"{url} -> json"
        assert parser.return_type == " json"
        assert isinstance(parser.parsed_command, WebCommand)
        assert parser.parsed_command.action == WebActionType.NAVIGATE
        assert parser.parsed_command.url == f"{url} "
        
        # Verify command type detection worked correctly
        parser_for_type_check = CommandParser("dummy")
        parser_for_type_check.command = url
        assert parser_for_type_check._determine_command_type() == CommandType.WEB
    
    def test_complete_workflow_file_command(self):
        """Test complete workflow for file command parsing."""
        path = "/etc/config/settings.yaml"
        parser = CommandParser(f"{path} -> dict")
        
        # Verify complete parsing workflow
        assert parser.command == f"{path} -> dict"
        assert parser.return_type == " dict"
        assert isinstance(parser.parsed_command, FileCommand)
        assert parser.parsed_command.action == FileActionType.READ
        assert parser.parsed_command.path == f"{path} "
        
        # Verify command type detection worked correctly
        parser_for_type_check = CommandParser("dummy")
        parser_for_type_check.command = path
        assert parser_for_type_check._determine_command_type() == CommandType.FILESYSTEM
    
    def test_complete_workflow_llm_command(self):
        """Test complete workflow for LLM command parsing."""
        instruction = "Analyze the user behavior patterns and suggest improvements"
        parser = CommandParser(f"{instruction} -> report")
        
        # Verify complete parsing workflow
        assert parser.command == f"{instruction} -> report"
        assert parser.return_type == " report"
        assert isinstance(parser.parsed_command, LLMCommand)
        assert parser.parsed_command.prompt == f"{instruction} "
        
        # Verify command type detection worked correctly
        parser_for_type_check = CommandParser("dummy")
        parser_for_type_check.command = instruction
        assert parser_for_type_check._determine_command_type() == CommandType.LLM
    
    def test_realistic_command_variations(self):
        """Test realistic variations of different command types."""
        test_cases = [
            # Web commands
            ("http://localhost:8080/api/data", WebCommand),
            ("https://example.com/search?q=python", WebCommand),
            
            # File commands  
            ("./config/database.json", FileCommand),
            ("file:///Users/user/Desktop/data.csv", FileCommand),
            ("/var/log/application.log", FileCommand),
            
            # LLM commands
            ("What is the current status?", LLMCommand),
            ("Optimize this algorithm for better performance", LLMCommand),
            ("Extract key insights from the quarterly report", LLMCommand),
        ]
        
        for command_str, expected_type in test_cases:
            parser = CommandParser(command_str)
            assert isinstance(parser.parsed_command, expected_type), f"Failed for: {command_str}" 