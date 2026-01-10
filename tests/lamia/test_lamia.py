import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from lamia.facade.lamia import Lamia
from lamia.engine.managers.llm.llm_manager import MissingAPIKeysError
from lamia import LLMModel  # Added for model override test
from lamia._internal_types.model_retry import ModelWithRetries  # Added for model override test


class TestLamiaLifecycle:
    """Test Lamia class lifecycle management"""

    def test_initialization_default_params(self):
        """Test default initialization parameters"""
        with patch('lamia.lamia.LamiaEngine') as MockEngine:
            mock_engine = MockEngine.return_value
            mock_engine.start = AsyncMock()
            mock_engine.generate = AsyncMock(return_value=type("Resp", (), {"text": "ok"})())
            lamia = Lamia()
            # Should be able to call run_async and get the mocked response
            result = asyncio.run(lamia.run_async("hello"))
            assert result == "ok"
            # Default model should be 'ollama'
            assert lamia._config_dict["default_model"] == "ollama"

    def test_initialization_custom_params(self):
        """Test initialization with custom parameters"""
        with patch('lamia.lamia.LamiaEngine') as MockEngine:
            mock_engine = MockEngine.return_value
            mock_engine.start = AsyncMock()
            mock_engine.generate = AsyncMock(return_value=type("Resp", (), {"text": "ok"})())
            lamia = Lamia('openai', 'ollama')
            result = asyncio.run(lamia.run_async("hello"))
            assert result == "ok"
            assert lamia._config_dict['default_model'] == 'openai'
            assert 'openai' in lamia._config_dict['models']
            assert 'ollama' in lamia._config_dict['models']

    def test_config_from_dict(self):
        """Test initialization with config dict"""
        config = {
            'default_model': 'test_model',
            'models': {'test_model': {'enabled': True}},
            'api_keys': {'test': 'key'}
        }
        with patch('lamia.lamia.LamiaEngine') as MockEngine:
            mock_engine = MockEngine.return_value
            mock_engine.start = AsyncMock()
            mock_engine.generate = AsyncMock(return_value=type("Resp", (), {"text": "ok"})())
            lamia = Lamia(config=config)
            assert lamia._config_dict == config
            result = asyncio.run(lamia.run_async("hello"))
            assert result == "ok"

    def test_config_from_file(self, tmp_path):
        """Test initialization with config file"""
        config_file = tmp_path / "test_config.yaml"
        config_content = """
default_model: test_model
models:
  test_model:
    enabled: true
"""
        config_file.write_text(config_content)
        with patch('lamia.lamia.LamiaEngine') as MockEngine:
            mock_engine = MockEngine.return_value
            mock_engine.start = AsyncMock()
            mock_engine.generate = AsyncMock(return_value=type("Resp", (), {"text": "ok"})())
            lamia = Lamia(config=str(config_file))
            assert lamia._config_dict['default_model'] == 'test_model'
            result = asyncio.run(lamia.run_async("hello"))
            assert result == "ok"

    def test_status_reporting(self):
        """Test status reporting (config dict)"""
        with patch('lamia.lamia.LamiaEngine') as MockEngine:
            mock_engine = MockEngine.return_value
            mock_engine.start = AsyncMock()
            mock_engine.generate = AsyncMock(return_value=type("Resp", (), {"text": "ok"})())
            lamia = Lamia('openai')
            # Check config dict
            assert lamia._config_dict['default_model'] == 'openai'
            assert 'openai' in lamia._config_dict['models']

    @pytest.mark.asyncio
    async def test_manual_start_stop(self):
        """Test manual engine start/stop"""
        with patch('lamia.lamia.LamiaEngine') as MockEngine:
            mock_engine = AsyncMock()
            mock_engine.start.return_value = True
            mock_engine.stop.return_value = True
            MockEngine.return_value = mock_engine
            lamia = Lamia()
            # Start
            await lamia._ensure_initialized()
            assert mock_engine.start.await_count == 1
            # Stop (call directly for coverage)
            await mock_engine.stop()
            assert mock_engine.stop.await_count == 1

    @pytest.mark.asyncio
    async def test_start_failure_handling(self):
        """Test handling of engine start failures"""
        with patch('lamia.lamia.LamiaEngine') as MockEngine:
            mock_engine = AsyncMock()
            mock_engine.start.return_value = False
            MockEngine.return_value = mock_engine
            lamia = Lamia()
            # Should raise RuntimeError on failed start
            with pytest.raises(RuntimeError):
                await lamia._ensure_initialized()

    @pytest.mark.asyncio
    async def test_start_exception_handling(self):
        """Test handling of exceptions during start"""
        with patch('lamia.lamia.LamiaEngine') as MockEngine:
            mock_engine = AsyncMock()
            mock_engine.start.side_effect = MissingAPIKeysError("Missing API keys")
            MockEngine.return_value = mock_engine
            lamia = Lamia()
            with pytest.raises(MissingAPIKeysError):
                await lamia._ensure_initialized()

    def test_run_python_code_expression(self):
        """Test run_python_code with a Python expression"""
        lamia = Lamia()
        success, result = lamia.run_python_code("1 + 2")
        assert success is True
        assert result == 3

    def test_run_python_code_statement(self):
        """Test run_python_code with a Python statement"""
        lamia = Lamia()
        code = "a = 5\nb = 7\na + b"
        success, result = lamia.run_python_code(code)
        assert success is True
        assert result == 12

    def test_run_python_code_invalid(self):
        """Test run_python_code with invalid code"""
        lamia = Lamia()
        success, result = lamia.run_python_code("this is not code")
        assert success is False
        assert isinstance(result, Exception)

    def test_run_method_python_code(self):
        """Test run method with Python code"""
        lamia = Lamia()
        result = lamia.run("2 * 3")
        assert result == "6"

    @pytest.mark.asyncio
    async def test_run_async_method_python_code(self):
        """Test run_async method with Python code"""
        lamia = Lamia()
        result = await lamia.run_async("2 * 3")
        assert result == "6"

    @pytest.mark.asyncio
    async def test_run_async_model_override(self):
        """run_async should temporarily override the engine model chain when *models* is supplied."""

        # Prepare a dummy config provider that tracks overrides
        dummy_config_provider = MagicMock()
        dummy_config_provider.override_model_chain_with = MagicMock()
        dummy_config_provider.reset_model_chain = MagicMock()

        # Stub LamiaEngine.execute to return a simple ValidationResult
        async def _execute_stub(command_type, content):
            from lamia.validation.base import ValidationResult
            return ValidationResult(is_valid=True, raw_text="dummy response")

        dummy_engine = MagicMock()
        dummy_engine.execute = AsyncMock(side_effect=_execute_stub)
        dummy_engine.config_provider = dummy_config_provider

        # Patch LamiaEngine so that Lamia uses our dummy engine
        with patch("lamia.lamia.LamiaEngine", return_value=dummy_engine):
            lamia = Lamia("openai")

            override_models = [ModelWithRetries(LLMModel("ollama"), retries=1)]

            result = await lamia.run_async("hello", models=override_models)

            # Verify that override and reset were called
            dummy_config_provider.override_model_chain_with.assert_called_once_with(override_models)
            dummy_config_provider.reset_model_chain.assert_called_once()

            # Ensure the response is propagated correctly
            assert result.result_text == "dummy response"

    @pytest.mark.asyncio
    async def test_context_manager_async(self):
        """Test async context manager usage"""
        with patch('lamia.lamia.LamiaEngine') as MockEngine:
            mock_engine = AsyncMock()
            mock_engine.start.return_value = True
            mock_engine.generate.return_value = type("Resp", (), {"text": "ok"})()
            MockEngine.return_value = mock_engine
            async with Lamia('openai') as lamia:
                result = await lamia.run_async("hello")
                assert result == "ok"

    def test_context_manager_sync(self):
        """Test sync context manager usage"""
        with patch('lamia.lamia.LamiaEngine') as MockEngine:
            mock_engine = MagicMock()
            mock_engine.start.return_value = True
            mock_engine.generate.return_value = type("Resp", (), {"text": "ok"})()
            MockEngine.return_value = mock_engine
            with Lamia('openai') as lamia:
                result = lamia.run("hello")
                assert result == "ok"

    @pytest.mark.asyncio
    async def test_run_with_validators(self):
        """Test run with custom validators"""
        def failing_validator(text):
            return False
        
        def passing_validator(text):
            return True
        
        with patch('lamia.lamia.LamiaEngine') as mock_engine_class:
            mock_engine = AsyncMock()
            mock_engine.start.return_value = True
            mock_response = MagicMock()
            mock_response.text = "Test response"
            mock_engine.generate.return_value = mock_response
            mock_engine_class.return_value = mock_engine
            
            # Test with failing validator
            lamia = Lamia(validators=[failing_validator])
            
            with pytest.raises(ValueError, match="Validator.*failed"):
                await lamia.run_async("test prompt")
            
            # Test with passing validator
            lamia = Lamia(validators=[passing_validator])
            response = await lamia.run_async("test prompt")
            assert response == "Test response"

    @pytest.mark.asyncio
    async def test_run_skip_validators(self):
        """Test run with skip_validators=True"""
        def failing_validator(text):
            return False
        
        with patch('lamia.lamia.LamiaEngine') as mock_engine_class:
            mock_engine = AsyncMock()
            mock_engine.start.return_value = True
            mock_response = MagicMock()
            mock_response.text = "Test response"
            mock_engine.generate.return_value = mock_response
            mock_engine_class.return_value = mock_engine
            
            lamia = Lamia(validators=[failing_validator])
            
            # Should succeed even with failing validator when skipped
            response = await lamia.run_async("test prompt", skip_validators=True)
            assert response == "Test response"

    def test_run_sync_no_event_loop(self):
        """Test synchronous run when no event loop is running"""
        with patch('lamia.lamia.LamiaEngine') as mock_engine_class:
            mock_engine = AsyncMock()
            mock_engine.start.return_value = True
            mock_response = MagicMock()
            mock_response.text = "Test response"
            mock_engine.generate.return_value = mock_response
            mock_engine_class.return_value = mock_engine
            
            lamia = Lamia()
            
            # This should work without any async context
            response = lamia.run("test prompt")
            assert response == "Test response"

    def test_run_sync_with_existing_loop(self):
        """Test synchronous run when event loop is already running"""
        with patch('lamia.lamia.LamiaEngine') as mock_engine_class:
            mock_engine = AsyncMock()
            mock_engine.start.return_value = True
            mock_response = MagicMock()
            mock_response.text = "Test response"
            mock_engine.generate.return_value = mock_response
            mock_engine_class.return_value = mock_engine
            
            lamia = Lamia()
            
            # This should work even when called from within async context
            response = lamia.run("test prompt")
            assert response == "Test response"

    def test_validator_with_validate_method(self):
        """Test validator that has a validate method"""
        class CustomValidator:
            def validate(self, text):
                return "good" in text.lower()
        
        with patch('lamia.lamia.LamiaEngine') as mock_engine_class:
            mock_engine = AsyncMock()
            mock_engine.start.return_value = True
            mock_response = MagicMock()
            mock_response.text = "This is a good response"
            mock_engine.generate.return_value = mock_response
            mock_engine_class.return_value = mock_engine
            
            lamia = Lamia(validators=[CustomValidator()])
            response = lamia.run("test prompt")
            assert response == "This is a good response"

    @pytest.mark.asyncio
    async def test_engine_error_reset(self):
        """Test that engine errors reset the state for retry"""
        with patch('lamia.lamia.LamiaEngine') as mock_engine_class:
            mock_engine = AsyncMock()
            mock_engine.start.return_value = True
            mock_engine.generate.side_effect = Exception("Engine error occurred")
            mock_engine_class.return_value = mock_engine
            
            lamia = Lamia()
            
            with pytest.raises(Exception, match="Engine error occurred"):
                await lamia.run_async("test prompt")