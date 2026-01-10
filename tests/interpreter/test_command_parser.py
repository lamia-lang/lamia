"""
Tests for the command parser module.
"""

import pytest
# Updated: CommandParser now exposes parsed data directly — helper functions removed.
from lamia.interpreter.command_parser import CommandParser
from lamia.interpreter.command_types import CommandType


class TestCommandTypeDetection:
    """Test command type detection."""
    
    def test_fs_commands(self):
        """Test filesystem command detection."""
        fs_commands = [
            "file:///tmp/file.txt",
            "file:///home/user/",
            "file:///src/file.txt",
            "file:///var/log/syslog",
            "file:///tmp/newdir/",
        ]
        
        for command in fs_commands:
            assert CommandParser(command).command_type == CommandType.FILESYSTEM
    
    def test_web_commands(self):
        """Test web command detection."""
        web_commands = [
            "https://example.com",
            "http://localhost:8080",
            "get https://api.example.com/data",
            "screenshot https://example.com",
            "fetch https://example.com --timeout 30",
        ]
        
        for command in web_commands:
            assert CommandParser(command).command_type == CommandType.WEB
    
    def test_llm_commands(self):
        """Test LLM command detection (default)."""
        llm_commands = [
            "What is the weather today?",
            "Explain quantum computing",
            "Write a Python function to sort a list",
            "Hello world",
            "/etc/passwd",  # Path without operation defaults to LLM
            "C:\\Windows\\System32",  # Windows path without operation defaults to LLM
        ]
        
        for command in llm_commands:
            assert CommandParser(command).command_type == CommandType.LLM


class TestCommandParsing:
    """Test command argument extraction."""
    
    def test_fs_command_parsing(self):
        """Test filesystem command parsing."""
        # Updated: filesystem commands must use the "file://" scheme and kwargs are empty.
        parser = CommandParser("file:///tmp/file.txt")
        assert parser.command_type == CommandType.FILESYSTEM
        assert parser.content == "file:///tmp/file.txt"
        assert parser.kwargs == {}
    
    def test_web_command_parsing(self):
        """Test web command parsing."""
        # URL as command
        parser = CommandParser("https://example.com")
        assert parser.command_type == CommandType.WEB
        assert parser.content == "https://example.com"
        assert parser.kwargs == {}
    
    def test_llm_command_parsing(self):
        """Test LLM command parsing."""
        parser = CommandParser("What is the weather today?")
        assert parser.command_type == CommandType.LLM
        assert parser.content == "What is the weather today?"
        assert parser.kwargs == {}
    
    def test_get_args_method(self):
        """Test the get_args method."""
        parser = CommandParser("file:///tmp/file.txt")
        content, kwargs = parser.get_args()
        assert content == "file:///tmp/file.txt"
        assert kwargs == {}


class TestErrorHandling:
    """Test error handling."""
    
    def test_invalid_fs_command(self):
        """Test invalid filesystem command handling."""
        # Invalid filesystem-like commands should fallback to LLM
        parser = CommandParser("read")
        assert parser.command_type == CommandType.LLM
        assert parser.kwargs == {}
    
    def test_invalid_web_command(self):
        """Test invalid web command handling."""
        # Invalid commands should fallback to LLM
        parser = CommandParser("get")
        assert parser.command_type == CommandType.LLM
        assert parser.kwargs == {} 