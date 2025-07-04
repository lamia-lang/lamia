import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import os

from lamia.engine.engine import LamiaEngine
from lamia.adapters.llm.base import LLMResponse
import lamia.adapters.llm.strategy as strategy


@pytest.mark.asyncio
async def test_generate_calls_execute_with_retries_once():
    """Ensure LamiaEngine.generate delegates to ValidationStrategy.execute_with_retries when validation is enabled."""

    config = {
        "default_model": "openai",
        "models": {"openai": {"enabled": True}},
        "validation": {
            "enabled": True,
            "max_retries": 2,
            "fallback_models": [],
            "validators": [{"type": "html"}],
        },
    }

    dummy_response = LLMResponse(
        text="Validated response",
        raw_response=None,
        usage={},
        model="openai",
    )

    # Stub adapter returned by create_adapter_from_config
    stub_adapter = MagicMock()
    stub_adapter.initialize = AsyncMock()
    stub_adapter.close = AsyncMock()
    stub_adapter.has_context_memory = True

    # Ensure OPENAI_API_KEY is present to bypass API key checks
    os.environ.setdefault("OPENAI_API_KEY", "dummy")

    with patch("lamia.engine.llm_manager.create_adapter_from_config", return_value=stub_adapter), \
         patch("lamia.engine.engine.create_adapter_from_config", return_value=stub_adapter):
        with patch.object(
            strategy.ValidationStrategy,
            "execute_with_retries",
            new=AsyncMock(return_value=dummy_response),
        ) as mock_execute:
            engine = LamiaEngine(config)
            await engine.start()

            response = await engine.generate("Hello, Lamia!")

            # ValidationStrategy.execute_with_retries should have been awaited exactly once
            mock_execute.assert_awaited_once()
            assert response == dummy_response

            await engine.stop()


@pytest.mark.asyncio
async def test_generate_propagates_errors_from_execute_with_retries():
    """If ValidationStrategy.execute_with_retries raises, LamiaEngine.generate should propagate the error."""

    config = {
        "default_model": "openai",
        "models": {"openai": {"enabled": True}},
        "validation": {
            "enabled": True,
            "max_retries": 2,
            "fallback_models": [],
            "validators": [{"type": "html"}],
        },
    }

    stub_adapter = MagicMock()
    stub_adapter.initialize = AsyncMock()
    stub_adapter.close = AsyncMock()
    stub_adapter.has_context_memory = True

    # Ensure OPENAI_API_KEY is present to bypass API key checks
    os.environ.setdefault("OPENAI_API_KEY", "dummy")

    with patch("lamia.engine.llm_manager.create_adapter_from_config", return_value=stub_adapter), \
         patch("lamia.engine.engine.create_adapter_from_config", return_value=stub_adapter):
        with patch.object(
            strategy.ValidationStrategy,
            "execute_with_retries",
            new=AsyncMock(side_effect=RuntimeError("Boom")),
        ) as mock_execute:
            engine = LamiaEngine(config)
            await engine.start()

            with pytest.raises(RuntimeError):
                await engine.generate("This will fail")

            mock_execute.assert_awaited_once()
            await engine.stop() 