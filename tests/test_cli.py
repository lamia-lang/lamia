import pytest
import asyncio
import sys
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock, patch, call
from io import StringIO
from lamia.cli import main
from lamia.engine.managers.llm.llm_manager import MissingAPIKeysError


class TestCLILifecycle:
    """Test CLI lifecycle management and error handling"""

    def setup_method(self):
        """Setup for each test method"""
        # Reset sys.argv to default state
        self.original_argv = sys.argv.copy()
        
    def teardown_method(self):
        """Cleanup after each test method"""
        # Restore original sys.argv
        sys.argv = self.original_argv

    def create_test_config(self, content):
        """Create a temporary config file"""
        config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        config_file.write(content)
        config_file.close()
        return config_file.name

    @patch('lamia.cli.LamiaEngine')
    @patch('sys.stderr', new_callable=StringIO)
    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_successful_startup_and_shutdown(self, mock_stdout, mock_stderr, mock_engine_class):
        """Test successful CLI startup and shutdown"""
        # Setup mocks
        mock_engine = AsyncMock()
        mock_engine.start.return_value = True
        mock_engine_class.return_value = mock_engine
        
        # Create test config
        config_content = """
default_model: test_model
models:
  test_model:
    enabled: true
"""
        config_file = self.create_test_config(config_content)
        
        try:
            # Mock interactive mode to exit immediately
            with patch('lamia.cli.interactive_mode') as mock_interactive:
                mock_interactive.return_value = asyncio.create_task(asyncio.sleep(0))
                
                # Set up sys.argv
                sys.argv = ['lamia', '--config', config_file]
                
                # This should exit with code 0 but we'll catch the SystemExit
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code == 0
                
                # Check that startup and shutdown messages were printed
                stdout_content = mock_stdout.getvalue()
                assert "Starting Lamia engine..." in stdout_content
                assert "✅ Lamia engine started successfully" in stdout_content
                assert "Shutting down Lamia engine..." in stdout_content
                assert "✅ Engine stopped successfully" in stdout_content
                
                # Verify engine was started and stopped
                mock_engine.start.assert_called_once()
                mock_engine.stop.assert_called_once()
                
        finally:
            os.unlink(config_file)

    @patch('lamia.cli.LamiaEngine')
    @patch('sys.stderr', new_callable=StringIO)
    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_missing_api_keys_error(self, mock_stdout, mock_stderr, mock_engine_class):
        """Test CLI handling of missing API keys"""
        # Setup mocks
        mock_engine = AsyncMock()
        mock_engine.start.side_effect = MissingAPIKeysError("Missing OpenAI API key")
        mock_engine_class.return_value = mock_engine
        
        # Create test config
        config_content = """
default_model: openai
models:
  openai:
    enabled: true
"""
        config_file = self.create_test_config(config_content)
        
        try:
            # Set up sys.argv
            sys.argv = ['lamia', '--config', config_file]
            
            # This should exit with code 1
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            assert exc_info.value.code == 1
            
            # Check error message was printed
            stderr_content = mock_stderr.getvalue()
            assert "❌ Missing API Keys: Missing OpenAI API key" in stderr_content
            assert "Please check your .env file or config.yaml for required API keys." in stderr_content
            
        finally:
            os.unlink(config_file)

    @patch('lamia.cli.LamiaEngine')
    @patch('sys.stderr', new_callable=StringIO)
    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_engine_startup_failure(self, mock_stdout, mock_stderr, mock_engine_class):
        """Test CLI handling of engine startup failure"""
        # Setup mocks
        mock_engine = AsyncMock()
        mock_engine.start.return_value = False  # Startup fails
        mock_engine_class.return_value = mock_engine
        
        # Create test config
        config_content = """
default_model: test_model
models:
  test_model:
    enabled: true
"""
        config_file = self.create_test_config(config_content)
        
        try:
            # Set up sys.argv
            sys.argv = ['lamia', '--config', config_file]
            
            # This should exit with code 1
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            assert exc_info.value.code == 1
            
            # Check error message was printed
            stderr_content = mock_stderr.getvalue()
            assert "❌ Error: Failed to start the Lamia engine" in stderr_content
            
        finally:
            os.unlink(config_file)

    @patch('lamia.cli.scaffold.create_minimal_config')
    @patch('lamia.cli.scaffold.create_env_file')
    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_init_command(self, mock_stdout, mock_create_env, mock_create_config):
        """Test CLI init command"""
        mock_create_config.return_value = True
        mock_create_env.return_value = True
        
        # Set up sys.argv for init command
        sys.argv = ['lamia', 'init']
        
        # The init command should not raise SystemExit in this flow
        main()
        
        stdout_content = mock_stdout.getvalue()
        assert "Created config.yaml" in stdout_content
        assert "Created .env file with dummy API keys." in stdout_content 