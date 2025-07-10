"""
Tests for the command parser module.
"""

import pytest
from lamia.command_parser import (
    CommandParser,
    get_lamia_command_type, 
    get_command_args
)
from lamia.command_types import CommandType


class TestCommandTypeDetection:
    """Test command type detection."""
    
    def test_fs_commands(self):
        """Test filesystem command detection."""
        fs_commands = [
            "read /tmp/file.txt",
            "list /home/user",
            "copy /src/file.txt /dest/",
            "ls /var/log",
            "mkdir /tmp/newdir",
        ]
        
        for command in fs_commands:
            assert get_lamia_command_type(command) == CommandType.FILESYSTEM
    
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
            assert get_lamia_command_type(command) == CommandType.WEB
    
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
            assert get_lamia_command_type(command) == CommandType.LLM


class TestCommandParsing:
    """Test command argument extraction."""
    
    def test_fs_command_parsing(self):
        """Test filesystem command parsing."""
        # Test basic fs command
        content, kwargs = get_command_args("read /tmp/file.txt")
        assert content == "/tmp/file.txt"
        assert kwargs['operation'] == 'read'
        
        # Test fs command with flags
        content, kwargs = get_command_args("copy /src/file.txt /dest/ --recursive --force")
        assert content == "/src/file.txt"
        assert kwargs['operation'] == 'copy'
        assert kwargs['recursive'] is True
        assert kwargs['force'] is True
    
    def test_web_command_parsing(self):
        """Test web command parsing."""
        # Test URL as command
        content, kwargs = get_command_args("https://example.com")
        assert content == "https://example.com"
        assert kwargs['operation'] == 'get'
        
        # Test web command with operation
        content, kwargs = get_command_args("screenshot https://example.com --full-page")
        assert content == "https://example.com"
        assert kwargs['operation'] == 'screenshot'
        assert kwargs['full-page'] is True
    
    def test_llm_command_parsing(self):
        """Test LLM command parsing."""
        content, kwargs = get_command_args("What is the weather today?")
        assert content == "What is the weather today?"
        assert kwargs == {}


class TestCommandParserClass:
    """Test the CommandParser class."""
    
    def test_fs_command_parsing(self):
        """Test filesystem command parsing with CommandParser."""
        parser = CommandParser("read /tmp/file.txt")
        assert parser.command_type == CommandType.FILESYSTEM
        assert parser.content == "/tmp/file.txt"
        assert parser.kwargs['operation'] == 'read'
        
        # Test with flags
        parser = CommandParser("copy /src/file.txt /dest/ --recursive --force")
        assert parser.command_type == CommandType.FILESYSTEM
        assert parser.content == "/src/file.txt"
        assert parser.kwargs['operation'] == 'copy'
        assert parser.kwargs['recursive'] is True
        assert parser.kwargs['force'] is True
    
    def test_web_command_parsing(self):
        """Test web command parsing with CommandParser."""
        parser = CommandParser("https://example.com")
        assert parser.command_type == CommandType.WEB
        assert parser.content == "https://example.com"
        assert parser.kwargs['operation'] == 'get'
        
        # Test with operation
        parser = CommandParser("screenshot https://example.com --full-page")
        assert parser.command_type == CommandType.WEB
        assert parser.content == "https://example.com"
        assert parser.kwargs['operation'] == 'screenshot'
        assert parser.kwargs['full-page'] is True
    
    def test_llm_command_parsing(self):
        """Test LLM command parsing with CommandParser."""
        parser = CommandParser("What is the weather today?")
        assert parser.command_type == CommandType.LLM
        assert parser.content == "What is the weather today?"
        assert parser.kwargs == {}
    
    def test_get_args_method(self):
        """Test the get_args method."""
        parser = CommandParser("read /tmp/file.txt")
        content, kwargs = parser.get_args()
        assert content == "/tmp/file.txt"
        assert kwargs['operation'] == 'read'


class TestErrorHandling:
    """Test error handling."""
    
    def test_invalid_fs_command(self):
        """Test invalid filesystem command handling."""
        # Invalid commands should fallback to LLM
        content, kwargs = get_command_args("read")  # Missing path
        assert content == "read"
        assert kwargs == {}
    
    def test_invalid_web_command(self):
        """Test invalid web command handling."""
        # Invalid commands should fallback to LLM
        content, kwargs = get_command_args("get")  # Missing URL
        assert content == "get"
        assert kwargs == {} 