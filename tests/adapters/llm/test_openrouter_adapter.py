"""Tests for OpenRouter adapter."""

import pytest
from unittest.mock import AsyncMock, MagicMock
import aiohttp

from lamia.adapters.llm.openrouter_adapter import (
    OpenRouterAdapter,
    OPENROUTER_API_URL,
)
from lamia import LLMModel
from lamia.errors import ExternalOperationRateLimitError, ExternalOperationTransientError


class TestOpenRouterAdapterClassMethods:
    """Test OpenRouterAdapter class-level methods."""

    def test_name(self):
        assert OpenRouterAdapter.name() == "openrouter"

    def test_env_var_names(self):
        assert OpenRouterAdapter.env_var_names() == ["OPENROUTER_API_KEY"]

    def test_is_remote(self):
        assert OpenRouterAdapter.is_remote() is True

    @pytest.mark.asyncio
    async def test_models_without_key_handles_unavailable(self):
        models = await OpenRouterAdapter.models()
        assert isinstance(models, list)


class TestOpenRouterAdapterInit:
    """Test OpenRouterAdapter initialization."""

    def test_defaults_with_key(self):
        adapter = OpenRouterAdapter(api_key="sk-or-test")
        assert adapter.api_key == "sk-or-test"
        assert adapter.session is None
        assert adapter.api_url == OPENROUTER_API_URL

    def test_defaults_without_key(self):
        adapter = OpenRouterAdapter()
        assert adapter.api_key == ""
        assert adapter.api_url == OPENROUTER_API_URL


class TestOpenRouterAdapterGenerate:
    """Test generate() requests."""

    @pytest.mark.asyncio
    async def test_generate_byok(self):
        model = LLMModel("openrouter:cohere/north-mini-code:free")

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "Hello!"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock(spec=aiohttp.ClientSession)
        mock_session.post = MagicMock(return_value=mock_response)

        adapter = OpenRouterAdapter(api_key="sk-or-test", api_url="https://proxy.test/v1")
        adapter.session = mock_session

        result = await adapter.generate("Hi", model)
        assert result.text == "Hello!"
        assert result.usage["prompt_tokens"] == 10
        assert result.usage["total_tokens"] == 15

        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert call_args[0][0] == "https://proxy.test/v1/chat/completions"
        headers = call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer sk-or-test"

        await adapter.close()

    @pytest.mark.asyncio
    async def test_generate_free_without_key(self):
        model = LLMModel("openrouter:cohere/north-mini-code:free")

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "Free response"}}],
            "usage": {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock(spec=aiohttp.ClientSession)
        mock_session.post = MagicMock(return_value=mock_response)

        adapter = OpenRouterAdapter(api_key="", api_url="https://proxy.test/v1")
        adapter.session = mock_session

        result = await adapter.generate("Hi", model)
        assert result.text == "Free response"
        call_args = mock_session.post.call_args
        assert call_args[0][0] == "https://proxy.test/v1/chat/completions"
        headers = call_args[1]["headers"]
        assert "Authorization" not in headers

        await adapter.close()

    @pytest.mark.asyncio
    async def test_generate_non_free_without_key_is_forwarded(self):
        """Paid models without a key are forwarded; proxy decides policy."""
        model = LLMModel("openrouter:meta-llama/llama-3.3-70b-instruct")

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "forwarded"}}],
            "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock(spec=aiohttp.ClientSession)
        mock_session.post = MagicMock(return_value=mock_response)

        adapter = OpenRouterAdapter(api_key="", api_url="https://proxy.test/v1")
        adapter.session = mock_session

        result = await adapter.generate("Hi", model)
        assert result.text == "forwarded"
        call_args = mock_session.post.call_args
        assert call_args[0][0] == "https://proxy.test/v1/chat/completions"
        assert "Authorization" not in call_args[1]["headers"]

        await adapter.close()

    @pytest.mark.asyncio
    async def test_generate_byok_allows_paid_models(self):
        """BYOK allows any model, not just :free."""
        model = LLMModel("openrouter:meta-llama/llama-3.3-70b-instruct")

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "Paid response"}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock(spec=aiohttp.ClientSession)
        mock_session.post = MagicMock(return_value=mock_response)

        adapter = OpenRouterAdapter(api_key="sk-or-test", api_url="https://proxy.test/v1")
        adapter.session = mock_session

        result = await adapter.generate("Hi", model)
        assert result.text == "Paid response"
        call_args = mock_session.post.call_args
        payload = call_args[1]["json"]
        assert payload["model"] == "meta-llama/llama-3.3-70b-instruct"

        await adapter.close()

    @pytest.mark.asyncio
    async def test_generate_rate_limit_429(self):
        model = LLMModel("openrouter:cohere/north-mini-code:free")

        mock_response = MagicMock()
        mock_response.status = 429
        mock_response.text = AsyncMock(return_value="Rate limit exceeded")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock(spec=aiohttp.ClientSession)
        mock_session.post = MagicMock(return_value=mock_response)

        adapter = OpenRouterAdapter(api_key="sk-or-test")
        adapter.session = mock_session

        with pytest.raises(ExternalOperationRateLimitError):
            await adapter.generate("Hi", model)

        await adapter.close()

    @pytest.mark.asyncio
    async def test_generate_connection_error(self):
        model = LLMModel("openrouter:cohere/north-mini-code:free")

        mock_session = MagicMock(spec=aiohttp.ClientSession)
        mock_session.post = MagicMock(side_effect=aiohttp.ClientError("connection failed"))

        adapter = OpenRouterAdapter(api_key="sk-or-test")
        adapter.session = mock_session

        with pytest.raises(ExternalOperationTransientError):
            await adapter.generate("Hi", model)

        await adapter.close()

class TestOpenRouterAdapterLifecycle:
    """Test adapter lifecycle methods."""

    @pytest.mark.asyncio
    async def test_close(self):
        adapter = OpenRouterAdapter(api_key="sk-or-test")
        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_session.closed = False
        adapter.session = mock_session

        await adapter.close()
        mock_session.close.assert_called_once()
        assert adapter.session is None

    @pytest.mark.asyncio
    async def test_close_no_session(self):
        adapter = OpenRouterAdapter(api_key="sk-or-test")
        await adapter.close()
