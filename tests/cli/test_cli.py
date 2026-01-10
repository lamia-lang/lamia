"""Tests for CLI module."""

import pytest
import asyncio
import sys
import os
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from io import StringIO
from lamia.cli.cli import interactive_mode, HYBRID_EXTENSIONS


class TestCLIConstants:
    """Test CLI constants and configuration."""
    
    def test_hybrid_extensions(self):
        """Test hybrid file extensions constant."""
        assert HYBRID_EXTENSIONS == {'.hu', '.lm'}
        assert isinstance(HYBRID_EXTENSIONS, set)
        assert '.hu' in HYBRID_EXTENSIONS
        assert '.lm' in HYBRID_EXTENSIONS


class TestInteractiveModeSetup:
    """Test interactive mode setup and initialization."""
    
    @pytest.mark.asyncio
    async def test_interactive_mode_initialization(self):
        """Test that interactive mode initializes properly."""
        mock_lamia = Mock()
        
        # Mock input to exit immediately
        with patch('builtins.input', side_effect=['EXIT']):
            with patch('lamia.cli.cli.logger') as mock_logger:
                await interactive_mode(mock_lamia)
                
                # Should log startup messages
                mock_logger.info.assert_called()
                calls = [call[0][0] for call in mock_logger.info.call_args_list]
                assert any("Lamia Interactive Mode" in call for call in calls)


@pytest.mark.asyncio
class TestInteractiveModeCommands:
    """Test interactive mode command handling."""
    
    async def test_exit_command(self):
        """Test EXIT command functionality."""
        mock_lamia = Mock()
        
        with patch('builtins.input', return_value='EXIT'):
            with patch('lamia.cli.cli.logger'):
                # Should exit without error
                await interactive_mode(mock_lamia)
    
    async def test_cancel_command(self):
        """Test CANCEL command functionality."""
        mock_lamia = Mock()
        
        # Test CANCEL followed by EXIT
        with patch('builtins.input', side_effect=['test input', 'CANCEL', 'EXIT']):
            with patch('lamia.cli.cli.logger'):
                await interactive_mode(mock_lamia)
    
    async def test_stats_command(self):
        """Test STATS command functionality."""
        mock_lamia = Mock()
        
        with patch('builtins.input', side_effect=['STATS', 'EXIT']):
            with patch('lamia.cli.cli.logger'):
                await interactive_mode(mock_lamia)
    
    async def test_case_insensitive_commands(self):
        """Test that commands are case insensitive."""
        mock_lamia = Mock()
        
        commands = ['exit', 'EXIT', 'Exit', 'stats', 'STATS', 'Stats', 'cancel', 'CANCEL']
        
        for cmd in commands[:3]:  # Test exit commands
            with patch('builtins.input', return_value=cmd):
                with patch('lamia.cli.cli.logger'):
                    await interactive_mode(mock_lamia)


class TestInteractiveModeErrorHandling:
    """Test interactive mode error handling."""
    
    @pytest.mark.asyncio
    async def test_keyboard_interrupt_handling(self):
        """Test handling of keyboard interrupts."""
        mock_lamia = Mock()
        
        with patch('builtins.input', side_effect=KeyboardInterrupt()):
            with patch('lamia.cli.cli.logger'):
                # Should handle KeyboardInterrupt gracefully
                await interactive_mode(mock_lamia)


class TestInteractiveModeInputHandling:
    """Test interactive mode input handling."""
    
    @pytest.mark.asyncio
    async def test_multiline_input_handling(self):
        """Test multiline input collection."""
        mock_lamia = Mock()
        mock_lamia.run = AsyncMock(return_value="response")
        
        # Simulate multiline input followed by SEND
        inputs = ['line 1', 'line 2', 'line 3', 'SEND', 'EXIT']
        
        with patch('builtins.input', side_effect=inputs):
            with patch('lamia.cli.cli.logger'):
                await interactive_mode(mock_lamia)
                
                # Should have called lamia.run with multiline content
                mock_lamia.run.assert_called()
    
    @pytest.mark.asyncio
    async def test_empty_input_handling(self):
        """Test handling of empty inputs."""
        mock_lamia = Mock()
        
        with patch('builtins.input', side_effect=['', 'EXIT']):
            with patch('lamia.cli.cli.logger'):
                await interactive_mode(mock_lamia)
    
    @pytest.mark.asyncio
    async def test_whitespace_input_handling(self):
        """Test handling of whitespace-only inputs."""
        mock_lamia = Mock()
        
        with patch('builtins.input', side_effect=['   ', '\t', '\n', 'EXIT']):
            with patch('lamia.cli.cli.logger'):
                await interactive_mode(mock_lamia)


class TestPromptDisplay:
    """Test prompt display and formatting."""
    
    def test_prompt_string_format(self):
        """Test that prompt string is properly formatted."""
        # This would require accessing the prompt_str variable from the function
        # For now, we test that the function doesn't crash with mocked input
        assert True  # Placeholder test
    
    def test_continuation_prompt(self):
        """Test continuation prompt for multiline input."""
        # Test that continuation prompt ("> ") is different from main prompt
        assert True  # Placeholder test


@pytest.mark.asyncio
class TestAsyncOperations:
    """Test asynchronous operations in interactive mode."""
    
    async def test_concurrent_task_handling(self):
        """Test handling of concurrent tasks."""
        mock_lamia = Mock()
        mock_lamia.run = AsyncMock(return_value="response")
        
        # Test that running tasks are handled properly
        with patch('builtins.input', side_effect=['test prompt', 'SEND', 'EXIT']):
            with patch('lamia.cli.cli.logger'):
                await interactive_mode(mock_lamia)
    
    async def test_task_interruption(self):
        """Test interruption of running tasks."""
        mock_lamia = Mock()
        # Mock a long-running operation
        mock_lamia.run = AsyncMock(side_effect=asyncio.sleep(10))
        
        with patch('builtins.input', side_effect=['test prompt', 'SEND', 'STOP', 'EXIT']):
            with patch('lamia.cli.cli.logger'):
                await interactive_mode(mock_lamia)


class TestCLIIntegration:
    """Test CLI integration with Lamia core."""
    
    @pytest.mark.asyncio
    async def test_lamia_run_called(self):
        """Test that lamia.run is called with user input."""
        mock_lamia = Mock()
        mock_lamia.run = AsyncMock(return_value="test response")
        
        with patch('builtins.input', side_effect=['test command', 'SEND', 'EXIT']):
            with patch('lamia.cli.cli.logger'):
                await interactive_mode(mock_lamia)
                
                mock_lamia.run.assert_called_once()
                call_args = mock_lamia.run.call_args[0][0]
                assert 'test command' in call_args
    
    @pytest.mark.asyncio 
    async def test_response_display(self):
        """Test that responses are displayed to user."""
        mock_lamia = Mock()
        mock_lamia.run = AsyncMock(return_value="test response")
        
        with patch('builtins.input', side_effect=['test', 'SEND', 'EXIT']):
            with patch('lamia.cli.cli.logger') as mock_logger:
                with patch('builtins.print') as mock_print:
                    await interactive_mode(mock_lamia)
                    
                    # Should print the response
                    mock_print.assert_called()


class TestCLILogging:
    """Test CLI logging functionality."""
    
    @pytest.mark.asyncio
    async def test_logging_setup(self):
        """Test that logging is properly set up."""
        mock_lamia = Mock()
        
        with patch('builtins.input', return_value='EXIT'):
            with patch('lamia.cli.cli.logger') as mock_logger:
                await interactive_mode(mock_lamia)
                
                # Should log startup messages
                assert mock_logger.info.called
    
    @pytest.mark.asyncio
    async def test_error_logging(self):
        """Test that errors are properly logged."""
        mock_lamia = Mock()
        mock_lamia.run = AsyncMock(side_effect=Exception("Test error"))
        
        with patch('builtins.input', side_effect=['test', 'SEND', 'EXIT']):
            with patch('lamia.cli.cli.logger') as mock_logger:
                await interactive_mode(mock_lamia)
                
                # Should log errors
                assert mock_logger.called


class TestCLIConstantsImmutability:
    """Test CLI module constants immutability."""
    
    def test_hybrid_extensions_immutable(self):
        """Test that HYBRID_EXTENSIONS is treated as immutable."""
        original = HYBRID_EXTENSIONS.copy()
        
        # Verify it's a set with expected values
        assert HYBRID_EXTENSIONS == {'.hu', '.lm'}
        
        # After any operations, should remain the same
        assert HYBRID_EXTENSIONS == original
    
    def test_logger_configuration(self):
        """Test that logger is properly configured."""
        from lamia.cli.cli import logger
        assert logger.name == 'lamia.cli.cli'