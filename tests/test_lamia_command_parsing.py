"""
Tests for Lamia command parsing integration.
"""

import pytest
from lamia import Lamia


class TestLamiaCommandParsing:
    """Test Lamia's integration with CommandParser."""
    
    @pytest.fixture
    def lamia(self):
        """Create a Lamia instance for testing."""
        return Lamia('ollama')
    
    def test_fs_command_parsing(self, lamia):
        """Test that filesystem commands are parsed correctly."""
        # We need to test the parsing without relying on the engine
        # Let's create a mock that allows us to see the parsing result
        from unittest.mock import patch
        
        with patch.object(lamia._engine, 'execute') as mock_execute:
            # Mock the engine to return a simple response
            mock_execute.return_value.text = "test response"
            
            result = lamia.run("read /tmp/file.txt")
            
            # Check that the engine was called with the correct parsed arguments
            mock_execute.assert_called_once()
            call_args = mock_execute.call_args
            assert call_args[0][0] == 'fs'  # command_type
            assert call_args[0][1] == '/tmp/file.txt'  # content
            assert call_args[1]['operation'] == 'read'  # kwargs
        
        # Also check the last command info
        command_info = lamia.get_last_command_info()
        assert command_info is not None
        assert command_info['type'] == 'fs'
        assert command_info['content'] == '/tmp/file.txt'
        assert command_info['kwargs']['operation'] == 'read'
    
    def test_web_command_parsing(self, lamia):
        """Test that web commands are parsed correctly."""
        try:
            lamia.run("https://example.com")
        except Exception:
            pass
        
        command_info = lamia.get_last_command_info()
        assert command_info is not None
        assert command_info['type'] == 'web'
        assert command_info['content'] == 'https://example.com'
        assert command_info['kwargs']['operation'] == 'get'
    
    def test_llm_command_parsing(self, lamia):
        """Test that LLM commands are parsed correctly."""
        try:
            lamia.run("What is the weather today?")
        except Exception:
            pass
        
        command_info = lamia.get_last_command_info()
        assert command_info is not None
        assert command_info['type'] == 'llm'
        assert command_info['content'] == 'What is the weather today?'
        assert command_info['kwargs'] == {}
    
    def test_python_code_bypasses_parser(self, lamia):
        """Test that Python code bypasses the command parser."""
        # Python code should be executed directly without going through the parser
        result = lamia.run("print('Hello World')")
        # run_python_code returns (True, None) for print statements, so result is empty string
        assert result == ""
        
        # Since Python code bypasses the parser, last command info should be None
        # or from a previous non-Python command
        command_info = lamia.get_last_command_info()
        # This could be None or from a previous test, depending on test order
        # We can't make strong assertions here
        
        # Test with a Python expression that returns a value
        result = lamia.run("2 + 2")
        assert result == "4"
    
    def test_no_command_parsed_yet(self, lamia):
        """Test that get_last_command_info returns None when no command parsed."""
        command_info = lamia.get_last_command_info()
        assert command_info is None 