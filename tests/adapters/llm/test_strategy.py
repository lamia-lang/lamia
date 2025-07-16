# Adapted tests for the new LLMManager architecture.

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from lamia.engine.managers.llm.llm_manager import LLMManager
from lamia.engine.config_provider import ConfigProvider
from lamia.engine.validation_strategies.llm_validation_strategy import LLMValidationStrategy
from lamia._internal_types.model_retry import ModelWithRetries
from lamia import LLMModel
from lamia.validation.base import ValidationResult


class DummyLLMResponse:
    """Simple stand-in for an adapter response object."""

    def __init__(self, text: str):
        self.text = text


def _build_manager(primary_retries: int = 2, fallback_retries: int | None = None):
    """Helper that returns a ready-to-use LLMManager instance with mocked internals."""

    # Build model chain (always use the builtin openai provider so that ProviderRegistry recognises it).
    chain: list[ModelWithRetries] = [
        ModelWithRetries(model=LLMModel(name="openai:gpt-3.5-turbo"), retries=primary_retries)
    ]
    if fallback_retries is not None:
        chain.append(ModelWithRetries(model=LLMModel(name="openai:gpt-3.5-turbo"), retries=fallback_retries))

    config_dict = {
        "model_chain": chain,
        # Provide a dummy API key so that the key-presence check passes.
        "api_keys": {"openai": "dummy"},
        # Validation section can stay empty – we inject validators manually.
        "validation": {}
    }

    config_provider = ConfigProvider(config_dict)

    # Prepare validation strategy stub (exposes both required methods).
    validation_strategy = LLMValidationStrategy({})
    validation_strategy.get_initial_hints = MagicMock(return_value=["Initial hint"])

    manager = LLMManager(config_provider, validation_strategy)

    return manager, validation_strategy


@pytest.mark.asyncio
async def test_execute_with_retries_success_first_try():
    manager, validation_strategy = _build_manager(primary_retries=2)

    # Mock adapter that succeeds immediately.
    adapter = MagicMock()
    adapter.generate = AsyncMock(return_value=DummyLLMResponse("valid response"))
    adapter.has_context_memory = True

    # Validation passes on first attempt.
    validation_strategy.validate = AsyncMock(return_value=ValidationResult(is_valid=True, validated_text="valid response"))

    with patch.object(manager, "create_adapter_from_config", AsyncMock(return_value=adapter)):
        result = await manager.execute_with_retries("prompt")

    assert result.is_valid
    assert result.validated_text == "valid response"
    adapter.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_with_retries_fallback_success():
    # Primary model allowed 1 retry so that it fails quickly.
    manager, validation_strategy = _build_manager(primary_retries=1, fallback_retries=1)

    adapter_primary = MagicMock()
    adapter_primary.generate = AsyncMock(return_value=DummyLLMResponse("bad response"))
    adapter_primary.has_context_memory = True

    adapter_fallback = MagicMock()
    adapter_fallback.generate = AsyncMock(return_value=DummyLLMResponse("good response"))
    adapter_fallback.has_context_memory = True

    # Validation: first answer invalid, second valid.
    validation_strategy.validate = AsyncMock(side_effect=[
        ValidationResult(is_valid=False, error_message="fail", hint="fix this"),
        ValidationResult(is_valid=True, validated_text="good response"),
    ])

    # create_adapter_from_config should return primary on first call, fallback on second.
    async def _create_adapter_side_effect(*args, **kwargs):
        # Determine whether we're dealing with the primary or the fallback by call count.
        if _create_adapter_side_effect.counter == 0:
            _create_adapter_side_effect.counter += 1
            return adapter_primary
        return adapter_fallback

    _create_adapter_side_effect.counter = 0

    with patch.object(manager, "create_adapter_from_config", AsyncMock(side_effect=_create_adapter_side_effect)):
        result = await manager.execute_with_retries("prompt")

    assert result.is_valid
    assert result.validated_text == "good response"
    assert adapter_primary.generate.await_count >= 1
    assert adapter_fallback.generate.await_count >= 1


@pytest.mark.asyncio
async def test_execute_with_retries_all_fail():
    manager, validation_strategy = _build_manager(primary_retries=1)

    adapter = MagicMock()
    adapter.generate = AsyncMock(return_value=DummyLLMResponse("bad response"))
    adapter.has_context_memory = True

    # Validation always fails.
    validation_strategy.validate = AsyncMock(return_value=ValidationResult(is_valid=False, error_message="fail", hint="fix this"))

    with patch.object(manager, "create_adapter_from_config", AsyncMock(return_value=adapter)):
        with pytest.raises(RuntimeError):
            await manager.execute_with_retries("prompt")


@pytest.mark.asyncio
async def test_execute_with_retries_initial_hint_in_prompt():
    manager, validation_strategy = _build_manager(primary_retries=1)

    captured_prompt = {}

    async def _generate(prompt: str, *args, **kwargs):
        captured_prompt["value"] = prompt
        return DummyLLMResponse("valid response")

    adapter = MagicMock()
    adapter.generate = AsyncMock(side_effect=_generate)
    adapter.has_context_memory = True

    validation_strategy.validate = AsyncMock(return_value=ValidationResult(is_valid=True, validated_text="valid response"))

    with patch.object(manager, "create_adapter_from_config", AsyncMock(return_value=adapter)):
        await manager.execute_with_retries("prompt")

    assert "Initial hint" in captured_prompt.get("value", "") 