import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from lamia.engine.engine import LamiaEngine
from lamia.adapters.llm.base import LLMResponse

class DummyLLMResponse(LLMResponse):
    """Lightweight LLMResponse that keeps the original constructor contract so **dict unpacking works."""

    def __init__(
        self,
        text: str,
        model: str,
        raw_response=None,
        usage: dict | None = None,
        *,
        is_valid: bool = True,
        error_message: str | None = None,
        **extra,
    ):
        super().__init__(text=text, raw_response=raw_response, usage=usage or {}, model=model)
        # allow extra fields like validation_result without breaking constructor signature
        # retain if provided by caller
        self.validation_result = extra.get(
            "validation_result",
            {
                "is_valid": is_valid,
                "error_message": error_message,
            },
        )


def make_stub_adapter(model_name: str, reply_text: str, *, is_valid: bool = True, error_message: str | None = None):
    """Return a stub adapter whose generate() yields a deterministic DummyLLMResponse."""
    adapter = MagicMock()
    adapter.has_context_memory = True
    adapter.initialize = AsyncMock()
    adapter.close = AsyncMock()
    adapter.model = model_name
    adapter.generate = AsyncMock(return_value=DummyLLMResponse(reply_text, model_name, is_valid, error_message))
    return adapter


@pytest.fixture(autouse=True)
def _dummy_api_key(monkeypatch):
    """Ensure a fake OPENAI_API_KEY is always present to bypass key checks."""
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

@pytest.mark.asyncio
async def test_single_model():
    config = {
        "default_model": "openai",
        "models": {"openai": {"enabled": True}},
        "validation": {
            "enabled": True,
            "max_retries": 1,
            "fallback_models": [],
            "validators": [{"type": "html"}],
        },
    }

    openai_adapter = make_stub_adapter("openai", "<html><body>ok</body></html>")

    with patch(
        "lamia.engine.llm_manager.create_adapter_from_config", return_value=openai_adapter
    ), patch(
        "lamia.engine.engine.create_adapter_from_config", return_value=openai_adapter
    ):
        engine = LamiaEngine(config)
        await engine.start()
        response = await engine.generate("Hello, world!")

        assert isinstance(response.text, str)
        assert response.model == "openai"
        assert response.validation_result["is_valid"] is True

        await engine.stop()

@pytest.mark.asyncio
async def test_fallback_adapter_is_used_on_failure():
    """If the primary adapter errors, engine should switch to the fallback model."""

    config = {
        "default_model": "openai",
        "models": {"openai": {"enabled": True}, "ollama": {"enabled": True}},
        "validation": {
            "enabled": True,
            "max_retries": 2,
            "fallback_models": ["ollama"],
            "validators": [{"type": "html"}],
        },
    }

    # Primary adapter returns invalid HTML (fails validation), fallback returns valid HTML
    openai_adapter = make_stub_adapter("openai", "not html", is_valid=False, error_message="Invalid HTML")

    ollama_adapter = make_stub_adapter("ollama", "<html><body>fallback</body></html>")

    def adapter_factory(config_manager, override_model=None):
        model = override_model or config_manager.get_default_model()
        return openai_adapter if model == "openai" else ollama_adapter

    with patch(
        "lamia.engine.llm_manager.create_adapter_from_config", side_effect=adapter_factory
    ), patch(
        "lamia.engine.engine.create_adapter_from_config", side_effect=lambda cm, override_model=None: adapter_factory(cm, override_model)
    ):
        engine = LamiaEngine(config)
        await engine.start()

        result = await engine.generate("Trigger fallback")

        # Fallback adapter should be used
        assert result.model == "ollama"
        assert result.validation_result["is_valid"] is True

        # Primary adapter tried once, fallback once
        openai_adapter.generate.assert_awaited_once()
        ollama_adapter.generate.assert_awaited_once()

        await engine.stop()

@pytest.mark.asyncio
async def test_custom_validator_success():
    """Simulate a python-code validator that passes."""
    config = {
        "default_model": "openai",
        "models": {"openai": {"enabled": True}},
        "validation": {
            "enabled": True,
            "max_retries": 1,
            "fallback_models": [],
            "validators": [
                {"type": "code_python", "language": "python", "strict": True}
            ],
        },
    }

    adapter = make_stub_adapter("openai", "def foo():\n    return 1")

    with patch("lamia.engine.llm_manager.create_adapter_from_config", return_value=adapter), \
         patch("lamia.engine.engine.create_adapter_from_config", return_value=adapter):
        engine = LamiaEngine(config)
        await engine.start()
        resp = await engine.generate("Prompt irrelevant here")

        assert "def foo():" in resp.text
        assert resp.validation_result["is_valid"] is True

        await engine.stop()


@pytest.mark.asyncio
async def test_validator_failure_raises():
    config = {
        "default_model": "openai",
        "models": {"openai": {"enabled": True}},
        "validation": {
            "enabled": True,
            "max_retries": 1,
            "fallback_models": [],
            "validators": [{"type": "html"}],
        },
    }

    adapter = make_stub_adapter(
        "openai",
        "not html",  # Intentionally invalid HTML
        is_valid=False,
        error_message="Invalid HTML",
    )

    with patch("lamia.engine.llm_manager.create_adapter_from_config", return_value=adapter), \
         patch("lamia.engine.engine.create_adapter_from_config", return_value=adapter):
        engine = LamiaEngine(config)
        await engine.start()

        with pytest.raises(RuntimeError):
            await engine.generate("Prompt irrelevant here")

        await engine.stop()