import pytest
from unittest.mock import AsyncMock, MagicMock
from lamia.engine.validation_strategies.llm_validation_strategy import ValidationStrategy, RetryConfig, FallbackModel
from lamia.validation.base import ValidationResult

class DummyLLMResponse:
    def __init__(self, text):
        self.text = text

@pytest.mark.asyncio
async def test_execute_with_retries_success_first_try():
    adapter = MagicMock()
    adapter.generate = AsyncMock(return_value=DummyLLMResponse("valid response"))
    adapter.has_context_memory = True

    # Stub manager that just returns our adapter
    manager = MagicMock()
    manager.get_primary_adapter = AsyncMock(return_value=adapter)
    manager.create_adapter_from_config = AsyncMock()  # never called here

    validator = MagicMock()
    validator.validate = AsyncMock(return_value=ValidationResult(is_valid=True, validated_text="valid response"))
    validator.initial_hint = "Initial hint"

    config = RetryConfig(max_retries_primary=2, fallback_models=[], validators=[])
    strategy = ValidationStrategy(config, validator_registry={})
    strategy.validators = [validator]

    result = await strategy.execute_with_retries(manager, "prompt")
    assert isinstance(result, DummyLLMResponse)
    assert result.text == "valid response"
    adapter.generate.assert_awaited_once()

@pytest.mark.asyncio
async def test_execute_with_retries_fallback_success():
    adapter1 = MagicMock()
    adapter1.generate = AsyncMock(return_value=DummyLLMResponse("bad response"))
    adapter1.has_context_memory = True

    adapter2 = MagicMock()
    adapter2.generate = AsyncMock(return_value=DummyLLMResponse("good response"))
    adapter2.has_context_memory = True

    validator = MagicMock()
    validator.validate = AsyncMock(side_effect=[
        ValidationResult(is_valid=False, error_message="fail", hint="fix this"),
        ValidationResult(is_valid=True, validated_text="good response")
    ])
    validator.initial_hint = "Initial hint"

    config = RetryConfig(
        max_retries_primary=2,
        fallback_models=[FallbackModel(name="fallback", max_retries=1)],
        validators=[],
    )
    strategy = ValidationStrategy(config, validator_registry={})
    strategy.validators = [validator]

    # Stub manager to switch adapters
    async def create_adapter_fn(model_name):
        return adapter2 if model_name == "fallback" else adapter1

    manager = MagicMock()
    manager.get_primary_adapter = AsyncMock(return_value=adapter1)
    manager.create_adapter_from_config = AsyncMock(side_effect=create_adapter_fn)

    result = await strategy.execute_with_retries(manager, "prompt")
    assert result.text == "good response"
    assert adapter1.generate.await_count == 1
    assert adapter2.generate.await_count == 1

@pytest.mark.asyncio
async def test_execute_with_retries_all_fail():
    adapter = MagicMock()
    adapter.generate = AsyncMock(return_value=DummyLLMResponse("bad response"))
    adapter.has_context_memory = True

    manager = MagicMock()
    manager.get_primary_adapter = AsyncMock(return_value=adapter)
    manager.create_adapter_from_config = AsyncMock()

    validator = MagicMock()
    validator.validate = AsyncMock(return_value=ValidationResult(is_valid=False, error_message="fail", hint="fix this"))
    validator.initial_hint = "Initial hint"

    config = RetryConfig(max_retries_primary=2, fallback_models=[], validators=[])
    strategy = ValidationStrategy(config, validator_registry={})
    strategy.validators = [validator]

    with pytest.raises(RuntimeError) as excinfo:
        await strategy.execute_with_retries(manager, "prompt")
    assert "All 2 attempts failed" in str(excinfo.value)

@pytest.mark.asyncio
async def test_execute_with_retries_initial_hint_in_prompt():
    adapter = MagicMock()
    adapter.generate = AsyncMock(return_value=DummyLLMResponse("valid response"))
    adapter.has_context_memory = True

    manager = MagicMock()
    manager.get_primary_adapter = AsyncMock(return_value=adapter)
    manager.create_adapter_from_config = AsyncMock()

    validator = MagicMock()
    validator.validate = AsyncMock(return_value=ValidationResult(is_valid=True, validated_text="valid response"))
    validator.initial_hint = "Initial hint"

    config = RetryConfig(max_retries_primary=1, fallback_models=[], validators=[])
    strategy = ValidationStrategy(config, validator_registry={})
    strategy.validators = [validator]

    await strategy.execute_with_retries(manager, "prompt")
    sent_prompt = adapter.generate.call_args[0][0]
    assert "Initial hint" in sent_prompt 