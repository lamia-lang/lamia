import pytest
from unittest.mock import AsyncMock, MagicMock
from lamia.adapters.llm.strategy import ValidationStrategy, RetryConfig
from lamia.validation.base import ValidationResult

class DummyLLMResponse:
    def __init__(self, text):
        self.text = text

@pytest.mark.asyncio
async def test_execute_with_retries_success_first_try():
    adapter = MagicMock()
    adapter.generate = AsyncMock(return_value=DummyLLMResponse("valid response"))
    adapter.has_context_memory = True

    validator = MagicMock()
    validator.validate = AsyncMock(return_value=ValidationResult(is_valid=True, validated_text="valid response"))
    validator.initial_hint = "Initial hint"

    config = RetryConfig(max_retries=2, fallback_models=None, validators=[])
    strategy = ValidationStrategy(config, validator_registry={})
    strategy.validators = [validator]

    result = await strategy.execute_with_retries(adapter, "prompt", create_adapter_fn=lambda x: None)
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

    config = RetryConfig(max_retries=2, fallback_models=["fallback"], validators=[])
    strategy = ValidationStrategy(config, validator_registry={})
    strategy.validators = [validator]

    def create_adapter_fn(model_name):
        return adapter2 if model_name == "fallback" else adapter1

    result = await strategy.execute_with_retries(adapter1, "prompt", create_adapter_fn)
    assert result.text == "good response"
    assert adapter1.generate.await_count == 1
    assert adapter2.generate.await_count == 1

@pytest.mark.asyncio
async def test_execute_with_retries_all_fail():
    adapter = MagicMock()
    adapter.generate = AsyncMock(return_value=DummyLLMResponse("bad response"))
    adapter.has_context_memory = True

    validator = MagicMock()
    validator.validate = AsyncMock(return_value=ValidationResult(is_valid=False, error_message="fail", hint="fix this"))
    validator.initial_hint = "Initial hint"

    config = RetryConfig(max_retries=2, fallback_models=None, validators=[])
    strategy = ValidationStrategy(config, validator_registry={})
    strategy.validators = [validator]

    with pytest.raises(RuntimeError) as excinfo:
        await strategy.execute_with_retries(adapter, "prompt", create_adapter_fn=lambda x: None)
    assert "All 2 attempts failed" in str(excinfo.value)

@pytest.mark.asyncio
async def test_execute_with_retries_initial_hint_in_prompt():
    adapter = MagicMock()
    adapter.generate = AsyncMock(return_value=DummyLLMResponse("valid response"))
    adapter.has_context_memory = True

    validator = MagicMock()
    validator.validate = AsyncMock(return_value=ValidationResult(is_valid=True, validated_text="valid response"))
    validator.initial_hint = "Initial hint"

    config = RetryConfig(max_retries=1, fallback_models=None, validators=[])
    strategy = ValidationStrategy(config, validator_registry={})
    strategy.validators = [validator]

    await strategy.execute_with_retries(adapter, "prompt", create_adapter_fn=lambda x: None)
    sent_prompt = adapter.generate.call_args[0][0]
    assert "Initial hint" in sent_prompt 