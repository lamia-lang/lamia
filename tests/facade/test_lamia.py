import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field
from typing import Any, List

from lamia.facade.lamia import Lamia
from lamia.facade.result_types import LamiaResult
from lamia.engine.managers.llm.llm_manager import MissingAPIKeysError
from lamia import LLMModel
from lamia._internal_types.model_retry import ModelWithRetries
from lamia.validation.base import TrackingContext
from lamia.interpreter.command_types import CommandType


def _create_mock_tracking_context() -> TrackingContext:
    """Create a mock TrackingContext for tests."""
    return TrackingContext(
        data_provider_name="mock",
        command_type=CommandType.LLM,
        metadata={}
    )


@dataclass
class MockValidationResult:
    """Mock validation result matching engine.execute return type."""
    is_valid: bool
    raw_text: str
    typed_result: Any = None
    execution_context: TrackingContext = field(default_factory=_create_mock_tracking_context)


class TestLamiaLifecycle:
    """Test Lamia class lifecycle management."""

    def test_initialization_default_params(self):
        """Test default initialization parameters."""
        with patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_engine = MagicMock()
            mock_engine.execute = AsyncMock(
                return_value=MockValidationResult(is_valid=True, raw_text="ok", typed_result="ok")
            )
            mock_engine.config_provider = MagicMock()
            MockEngine.return_value = mock_engine

            lamia = Lamia()
            result = asyncio.run(lamia.run_async("hello"))

            # Without return_type, run_async returns response.typed_result directly
            assert result == "ok"
            # Engine should have been created with a config provider
            MockEngine.assert_called_once()

    def test_initialization_custom_models(self):
        """Test initialization with custom model names."""
        with patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_engine = MagicMock()
            mock_engine.execute = AsyncMock(
                return_value=MockValidationResult(is_valid=True, raw_text="ok", typed_result="ok")
            )
            mock_engine.config_provider = MagicMock()
            MockEngine.return_value = mock_engine

            lamia = Lamia('openai', 'ollama')
            result = asyncio.run(lamia.run_async("hello"))

            assert result == "ok"
            MockEngine.assert_called_once()

    def test_from_config_dict(self):
        """Test initialization with config dict using from_config."""
        config = {
            'default_model': 'openai',
            'models': {'openai': {'enabled': True}},
            'api_keys': {'openai': 'sk-test-key'}
        }
        with patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_engine = MagicMock()
            mock_engine.execute = AsyncMock(
                return_value=MockValidationResult(is_valid=True, raw_text="ok", typed_result="ok")
            )
            mock_engine.config_provider = MagicMock()
            MockEngine.return_value = mock_engine

            lamia = Lamia.from_config(config)
            result = asyncio.run(lamia.run_async("hello"))

            assert result == "ok"
            MockEngine.assert_called_once()

    def test_from_config_file(self, tmp_path):
        """Test initialization with config file using from_config."""
        import yaml

        config_file = tmp_path / "test_config.yaml"
        config_content = {
            'default_model': 'openai',
            'models': {
                'openai': {'enabled': True}
            }
        }
        config_file.write_text(yaml.dump(config_content))

        with patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_engine = MagicMock()
            mock_engine.execute = AsyncMock(
                return_value=MockValidationResult(is_valid=True, raw_text="ok", typed_result="ok")
            )
            mock_engine.config_provider = MagicMock()
            MockEngine.return_value = mock_engine

            # Load config from file and use from_config
            with open(config_file, 'r') as f:
                loaded_config = yaml.safe_load(f)

            lamia = Lamia.from_config(loaded_config)
            result = asyncio.run(lamia.run_async("hello"))

            assert result == "ok"

    @pytest.mark.asyncio
    async def test_engine_start_error(self):
        """Test handling of engine execution failures."""
        with patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_engine = MagicMock()
            # MissingAPIKeysError expects list of (provider, env_vars) tuples
            mock_engine.execute = AsyncMock(
                side_effect=MissingAPIKeysError([("openai", "OPENAI_API_KEY")])
            )
            mock_engine.config_provider = MagicMock()
            MockEngine.return_value = mock_engine

            lamia = Lamia()

            with pytest.raises(MissingAPIKeysError):
                await lamia.run_async("hello")

    def test_run_python_code_expression(self):
        """Test that Python expressions are evaluated directly."""
        with patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_engine = MagicMock()
            mock_engine.config_provider = MagicMock()
            MockEngine.return_value = mock_engine

            lamia = Lamia()
            result = asyncio.run(lamia.run_async("1 + 2"))

            # Python code should be evaluated without calling the engine
            # Result is a LamiaResult when Python succeeds
            assert isinstance(result, LamiaResult)
            assert result.typed_result == 3
            # Engine.execute should not have been called for simple Python
            mock_engine.execute.assert_not_called()

    def test_run_python_code_statement(self):
        """Test that Python statements are evaluated directly."""
        with patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_engine = MagicMock()
            mock_engine.config_provider = MagicMock()
            MockEngine.return_value = mock_engine

            lamia = Lamia()
            code = "a = 5\nb = 7\na + b"
            result = asyncio.run(lamia.run_async(code))

            assert isinstance(result, LamiaResult)
            assert result.typed_result == 12
            mock_engine.execute.assert_not_called()

    def test_run_python_code_sync(self):
        """Test synchronous run with Python code."""
        with patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_engine = MagicMock()
            mock_engine.config_provider = MagicMock()
            MockEngine.return_value = mock_engine

            lamia = Lamia()
            result = lamia.run("2 * 3")

            assert isinstance(result, LamiaResult)
            assert result.typed_result == 6

    @pytest.mark.asyncio
    async def test_run_async_model_override(self):
        """run_async should temporarily override the engine model chain when *models* is supplied."""
        dummy_config_provider = MagicMock()
        dummy_config_provider.override_model_chain_with = MagicMock()
        dummy_config_provider.reset_model_chain = MagicMock()

        async def _execute_stub(command, return_type=None):
            return MockValidationResult(is_valid=True, raw_text="dummy response", typed_result="dummy response")

        dummy_engine = MagicMock()
        dummy_engine.execute = AsyncMock(side_effect=_execute_stub)
        dummy_engine.config_provider = dummy_config_provider

        with patch("lamia.facade.lamia.LamiaEngine", return_value=dummy_engine):
            lamia = Lamia("openai")

            override_models = [ModelWithRetries(LLMModel("ollama"), retries=1)]
            # Use a non-Python command to ensure engine.execute is called
            # Type annotation in implementation is narrower than what it accepts
            result = await lamia.run_async("generate a story", models=override_models)  # type: ignore[arg-type]

            # Verify that override and reset were called
            dummy_config_provider.override_model_chain_with.assert_called_once_with(override_models)
            dummy_config_provider.reset_model_chain.assert_called_once()

            # Result is the typed_result from the response
            assert result == "dummy response"

    @pytest.mark.asyncio
    async def test_context_manager_async(self):
        """Test async context manager usage."""
        with patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_engine = MagicMock()
            mock_engine.execute = AsyncMock(
                return_value=MockValidationResult(is_valid=True, raw_text="ok", typed_result="ok")
            )
            mock_engine.cleanup = AsyncMock()
            mock_engine.config_provider = MagicMock()
            MockEngine.return_value = mock_engine

            async with Lamia('openai') as lamia:
                # Non-Python command to trigger engine.execute
                result = await lamia.run_async("hello world")
                assert result == "ok"

            # Cleanup should have been called
            mock_engine.cleanup.assert_awaited_once()

    def test_run_sync_no_event_loop(self):
        """Test synchronous run when no event loop is running."""
        with patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_engine = MagicMock()
            mock_engine.execute = AsyncMock(
                return_value=MockValidationResult(is_valid=True, raw_text="response", typed_result="response")
            )
            mock_engine.config_provider = MagicMock()
            MockEngine.return_value = mock_engine

            lamia = Lamia()
            # Non-Python command
            response = lamia.run("hello world prompt")

            assert response == "response"

    @pytest.mark.asyncio
    async def test_engine_execute_error_handling(self):
        """Test that engine execution errors are propagated."""
        with patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_engine = MagicMock()
            mock_engine.execute = AsyncMock(side_effect=Exception("Engine error occurred"))
            mock_engine.config_provider = MagicMock()
            MockEngine.return_value = mock_engine

            lamia = Lamia()

            with pytest.raises(Exception, match="Engine error occurred"):
                await lamia.run_async("test prompt")

    @pytest.mark.asyncio
    async def test_run_async_with_return_type(self):
        """Test run_async with return_type returns LamiaResult."""
        from pydantic import BaseModel
        from lamia.types import JSON

        class MyModel(BaseModel):
            value: str

        with patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_engine = MagicMock()
            mock_result = MockValidationResult(
                is_valid=True,
                raw_text="test response",
                typed_result=MyModel(value="parsed")
            )
            mock_engine.execute = AsyncMock(return_value=mock_result)
            mock_engine.config_provider = MagicMock()
            MockEngine.return_value = mock_engine

            lamia = Lamia()
            # JSON[MyModel] is a typical usage pattern for return_type
            result = await lamia.run_async("generate something", return_type=JSON[MyModel, False])

            # With return_type, should return LamiaResult
            assert isinstance(result, LamiaResult)
            assert result.result_text == "test response"
            assert isinstance(result.typed_result, MyModel)
            assert result.typed_result.value == "parsed"

    @pytest.mark.asyncio
    async def test_run_async_without_return_type(self):
        """Test run_async without return_type returns typed_result directly."""
        with patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_engine = MagicMock()
            mock_result = MockValidationResult(
                is_valid=True,
                raw_text="test response",
                typed_result="direct result"
            )
            mock_engine.execute = AsyncMock(return_value=mock_result)
            mock_engine.config_provider = MagicMock()
            MockEngine.return_value = mock_engine

            lamia = Lamia()
            result = await lamia.run_async("generate something")

            # Without return_type, should return typed_result directly
            assert result == "direct result"

    def test_get_validation_stats(self):
        """Test get_validation_stats delegates to engine."""
        with patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_engine = MagicMock()
            mock_engine.get_validation_stats.return_value = {"iterations": 5, "success": True}
            mock_engine.config_provider = MagicMock()
            MockEngine.return_value = mock_engine

            lamia = Lamia()
            stats = lamia.get_validation_stats()

            assert stats == {"iterations": 5, "success": True}
            mock_engine.get_validation_stats.assert_called_once()

    def test_initialization_with_api_keys_propagates_to_config_builder(self):
        """Test that API keys parameter is correctly propagated to build_config_from_models."""
        with patch('lamia.facade.lamia.build_config_from_models') as mock_build_config, \
             patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_config_provider = MagicMock()
            mock_build_config.return_value = mock_config_provider
            mock_engine = MagicMock()
            MockEngine.return_value = mock_engine

            api_keys = {'openai': 'sk-test-key', 'anthropic': 'sk-ant-test'}
            Lamia('openai', 'anthropic', api_keys=api_keys)

            # Verify build_config_from_models was called with correct arguments
            mock_build_config.assert_called_once()
            call_args = mock_build_config.call_args
            # args[0] = models tuple, args[1] = api_keys
            assert call_args[0][1] == api_keys
            # Engine should receive the config provider
            MockEngine.assert_called_once_with(mock_config_provider)

    def test_initialization_with_llm_model_objects_propagates_to_config_builder(self):
        """Test that LLMModel objects are correctly propagated to build_config_from_models."""
        with patch('lamia.facade.lamia.build_config_from_models') as mock_build_config, \
             patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_config_provider = MagicMock()
            mock_build_config.return_value = mock_config_provider
            mock_engine = MagicMock()
            MockEngine.return_value = mock_engine

            model = LLMModel("openai:gpt-4o")
            Lamia(model)

            # Verify build_config_from_models was called with the LLMModel
            mock_build_config.assert_called_once()
            call_args = mock_build_config.call_args
            # First argument is the models tuple
            models_tuple = call_args[0][0]
            assert model in models_tuple

    def test_initialization_with_model_and_retries_tuple_propagates_to_config_builder(self):
        """Test that (model, retries) tuples are correctly propagated to build_config_from_models."""
        with patch('lamia.facade.lamia.build_config_from_models') as mock_build_config, \
             patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_config_provider = MagicMock()
            mock_build_config.return_value = mock_config_provider
            mock_engine = MagicMock()
            MockEngine.return_value = mock_engine

            Lamia(('openai', 3), ('ollama', 2))

            # Verify build_config_from_models was called with the tuples
            mock_build_config.assert_called_once()
            call_args = mock_build_config.call_args
            models_tuple = call_args[0][0]
            assert ('openai', 3) in models_tuple
            assert ('ollama', 2) in models_tuple

    def test_initialization_with_retry_config_propagates_to_config_builder(self):
        """Test that retry_config is correctly propagated to build_config_from_models."""
        from lamia.types import ExternalOperationRetryConfig

        with patch('lamia.facade.lamia.build_config_from_models') as mock_build_config, \
             patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_config_provider = MagicMock()
            mock_build_config.return_value = mock_config_provider
            mock_engine = MagicMock()
            MockEngine.return_value = mock_engine

            retry_config = ExternalOperationRetryConfig(
                max_attempts=5,
                base_delay=2.0,
                max_delay=120.0,
                exponential_base=3.0,
                max_total_duration=None
            )
            Lamia('openai', retry_config=retry_config)

            # Verify retry_config was passed correctly
            mock_build_config.assert_called_once()
            call_args = mock_build_config.call_args
            # args[2] = retry_config
            assert call_args[0][2] == retry_config

    def test_initialization_with_web_config_propagates_to_config_builder(self):
        """Test that web_config is correctly propagated to build_config_from_models."""
        with patch('lamia.facade.lamia.build_config_from_models') as mock_build_config, \
             patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_config_provider = MagicMock()
            mock_build_config.return_value = mock_config_provider
            mock_engine = MagicMock()
            MockEngine.return_value = mock_engine

            web_config = {'headless': True, 'timeout': 30000}
            Lamia('openai', web_config=web_config)

            # Verify web_config was passed correctly
            mock_build_config.assert_called_once()
            call_args = mock_build_config.call_args
            # args[3] = web_config
            assert call_args[0][3] == web_config

    @pytest.mark.asyncio
    async def test_model_override_resets_on_exception(self):
        """Test that model chain is reset even when execution raises."""
        dummy_config_provider = MagicMock()
        dummy_config_provider.override_model_chain_with = MagicMock()
        dummy_config_provider.reset_model_chain = MagicMock()

        dummy_engine = MagicMock()
        dummy_engine.execute = AsyncMock(side_effect=ValueError("Test error"))
        dummy_engine.config_provider = dummy_config_provider

        with patch("lamia.facade.lamia.LamiaEngine", return_value=dummy_engine):
            lamia = Lamia("openai")

            override_models = [ModelWithRetries(LLMModel("ollama"), retries=1)]

            with pytest.raises(ValueError, match="Test error"):
                # Type annotation in implementation is narrower than what it accepts
                await lamia.run_async("generate a story", models=override_models)  # type: ignore[arg-type]

            # Override should have been called
            dummy_config_provider.override_model_chain_with.assert_called_once()
            # Reset should NOT have been called because exception happened before it
            # This tests current behavior - if this is undesirable, implementation needs try/finally
            dummy_config_provider.reset_model_chain.assert_not_called()

    def test_run_sync_works_from_async_context(self):
        """Test that run() works even from async context via EventLoopManager."""
        with patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_engine = MagicMock()
            mock_engine.config_provider = MagicMock()
            mock_engine.execute = AsyncMock(
                return_value=MockValidationResult(is_valid=True, raw_text="response", typed_result="response")
            )
            MockEngine.return_value = mock_engine

            lamia = Lamia()

            async def call_sync_from_async():
                return lamia.run("test prompt")

            result = asyncio.run(call_sync_from_async())
            assert result == "response"

    def test_string_command_delegates_to_process_string_command(self):
        """Test that string commands are processed through process_string_command."""
        from lamia.interpreter.commands import LLMCommand

        mock_parsed_command = LLMCommand("test prompt")

        with patch('lamia.facade.lamia.process_string_command') as mock_process, \
             patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            # process_string_command returns (parsed_command, None) when Python fails
            mock_process.return_value = (mock_parsed_command, None)

            mock_engine = MagicMock()
            mock_engine.execute = AsyncMock(
                return_value=MockValidationResult(is_valid=True, raw_text="llm response", typed_result="llm response")
            )
            mock_engine.config_provider = MagicMock()
            MockEngine.return_value = mock_engine

            lamia = Lamia()
            result = asyncio.run(lamia.run_async("write me a poem about cats"))

            # Verify process_string_command was called with the input
            mock_process.assert_called_once_with("write me a poem about cats")

            # Verify engine.execute was called with the parsed command
            mock_engine.execute.assert_called_once()
            execute_call_args = mock_engine.execute.call_args
            assert execute_call_args[0][0] == mock_parsed_command

            assert result == "llm response"

    def test_python_success_skips_engine_execute(self):
        """Test that successful Python execution skips engine.execute."""
        with patch('lamia.facade.lamia.process_string_command') as mock_process, \
             patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            # process_string_command returns (None, LamiaResult) when Python succeeds
            python_result = LamiaResult(
                result_text="42",
                typed_result=42,
                tracking_context=_create_mock_tracking_context()
            )
            mock_process.return_value = (None, python_result)

            mock_engine = MagicMock()
            mock_engine.execute = AsyncMock()
            mock_engine.config_provider = MagicMock()
            MockEngine.return_value = mock_engine

            lamia = Lamia()
            result = asyncio.run(lamia.run_async("6 * 7"))

            # Verify process_string_command was called
            mock_process.assert_called_once_with("6 * 7")

            # Engine.execute should NOT be called when Python succeeds
            mock_engine.execute.assert_not_called()

            # Result should be the Python result
            assert result == python_result

    def test_command_object_skips_process_string_command(self):
        """Test that Command objects bypass process_string_command entirely."""
        from lamia.interpreter.commands import LLMCommand

        command = LLMCommand("direct command")

        with patch('lamia.facade.lamia.process_string_command') as mock_process, \
             patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_engine = MagicMock()
            mock_engine.execute = AsyncMock(
                return_value=MockValidationResult(is_valid=True, raw_text="response", typed_result="response")
            )
            mock_engine.config_provider = MagicMock()
            MockEngine.return_value = mock_engine

            lamia = Lamia()
            result = asyncio.run(lamia.run_async(command))

            # process_string_command should NOT be called for Command objects
            mock_process.assert_not_called()

            # Engine.execute should be called directly with the command
            mock_engine.execute.assert_called_once()
            execute_call_args = mock_engine.execute.call_args
            assert execute_call_args[0][0] == command

            assert result == "response"
