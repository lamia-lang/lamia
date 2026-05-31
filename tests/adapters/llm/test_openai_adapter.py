"""Tests for OpenAI LLM adapter."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import aiohttp
from pydantic import BaseModel
from lamia.adapters.llm.openai_adapter import OpenAIAdapter, OPENAI_AVAILABLE
from lamia.adapters.llm.base import LLMResponse
from lamia import LLMModel


class TestOpenAIAdapterClassMethods:
    """Test OpenAIAdapter class-level methods."""
    
    def test_name(self):
        """Test provider name."""
        assert OpenAIAdapter.name() == "openai"
    
    def test_env_var_names(self):
        """Test environment variable names."""
        env_vars = OpenAIAdapter.env_var_names()
        assert env_vars == ["OPENAI_API_KEY"]
    
    def test_is_remote(self):
        """Test that OpenAI adapter is remote."""
        assert OpenAIAdapter.is_remote() is True


class TestOpenAIAdapterInitialization:
    """Test OpenAIAdapter initialization."""
    
    @patch('lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE', True)
    @patch('lamia.adapters.llm.openai_adapter.AsyncOpenAI')
    def test_initialization_with_sdk(self, mock_openai):
        """Test initialization when OpenAI SDK is available."""
        mock_client = AsyncMock()
        mock_openai.return_value = mock_client
        
        adapter = OpenAIAdapter(api_key="test-key")
        
        assert adapter.api_key == "test-key"
        assert adapter._use_sdk is True
        assert adapter.client == mock_client
        assert adapter.session is None
        mock_openai.assert_called_once_with(api_key="test-key")
    
    @patch('lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE', False)
    def test_initialization_without_sdk(self):
        """Test initialization when OpenAI SDK is not available."""
        adapter = OpenAIAdapter(api_key="test-key")
        
        assert adapter.api_key == "test-key"
        assert adapter._use_sdk is False
        assert adapter.client is None
        assert adapter.session is None  # Created in async_initialize
    
    def test_initialization_stores_api_key(self):
        """Test that API key is stored correctly."""
        adapter = OpenAIAdapter(api_key="my-secret-key")
        assert adapter.api_key == "my-secret-key"


class TestOpenAIAdapterAsyncInitialize:
    """Test OpenAIAdapter async_initialize method."""
    
    @pytest.mark.asyncio
    @patch('lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE', True)
    @patch('lamia.adapters.llm.openai_adapter.AsyncOpenAI')
    async def test_async_initialize_with_sdk_existing_client(self, mock_openai):
        """Test async initialization when using SDK with existing client."""
        mock_client = AsyncMock()
        mock_openai.return_value = mock_client
        
        adapter = OpenAIAdapter(api_key="test-key")
        await adapter.async_initialize()
        
        # Client should remain the same
        assert adapter.client == mock_client
    
    @pytest.mark.asyncio
    @patch('lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE', False)
    @patch('aiohttp.ClientSession')
    async def test_async_initialize_without_sdk(self, mock_session_class):
        """Test async initialization when not using SDK."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        adapter = OpenAIAdapter(api_key="test-key")
        
        await adapter.async_initialize()
        
        assert adapter.session == mock_session
        mock_session_class.assert_called_once_with(
            headers={
                "Authorization": "Bearer test-key",
                "Content-Type": "application/json"
            }
        )
    
    @pytest.mark.asyncio
    @patch('lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE', False)
    @patch('aiohttp.ClientSession')
    async def test_async_initialize_session_already_exists(self, mock_session_class):
        """Test async initialization when session already exists."""
        existing_session = Mock()
        adapter = OpenAIAdapter(api_key="test-key")
        adapter.session = existing_session
        
        await adapter.async_initialize()
        
        # Should not create new session
        assert adapter.session == existing_session
        mock_session_class.assert_not_called()


class TestOpenAIAdapterCleanup:
    """Test OpenAIAdapter resource cleanup."""
    
    @pytest.mark.asyncio
    @patch('lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE', True)
    async def test_close_with_sdk(self):
        """Test cleanup when using SDK."""
        with patch('lamia.adapters.llm.openai_adapter.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            adapter = OpenAIAdapter(api_key="test-key")
            await adapter.close()
            
            mock_client.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE', False)
    @patch('aiohttp.ClientSession')
    async def test_close_with_http(self, mock_session_class):
        """Test cleanup when using HTTP client."""
        mock_session = Mock()
        mock_session.close = AsyncMock()
        mock_session_class.return_value = mock_session
        
        adapter = OpenAIAdapter(api_key="test-key")
        await adapter.async_initialize()
        await adapter.close()
        
        mock_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_with_none_resources(self):
        """Test cleanup when resources are None."""
        adapter = OpenAIAdapter(api_key="test-key")
        adapter.client = None
        adapter.session = None
        
        # Should not raise any errors
        await adapter.close()


class TestOpenAIAdapterConstants:
    """Test OpenAI adapter constants."""
    
    def test_api_url_constant(self):
        """Test that API URL constant is correct."""
        assert OpenAIAdapter.API_URL == "https://api.openai.com/v1/chat/completions"


class TestOpenAIAdapterGeneration:
    """Test OpenAI adapter generation."""
    
    @pytest.mark.asyncio
    @patch('lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE', True)
    async def test_generate_with_sdk_success(self):
        """Test successful generation with SDK."""
        with patch('lamia.adapters.llm.openai_adapter.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            mock_response = Mock()
            mock_choice = Mock()
            mock_choice.message.content = "Hello! How can I help you?"
            mock_response.choices = [mock_choice]
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 8
            mock_response.usage.total_tokens = 18
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            adapter = OpenAIAdapter(api_key="test-key")
            
            mock_model = Mock(spec=LLMModel)
            mock_model.name = "gpt-3.5-turbo"
            mock_model.get_model_name_without_provider = Mock(return_value="gpt-3.5-turbo")
            mock_model.temperature = 0.7
            mock_model.max_tokens = 1000
            mock_model.top_p = 1.0
            mock_model.top_k = None
            mock_model.frequency_penalty = None
            mock_model.presence_penalty = None
            mock_model.seed = None
            
            response = await adapter.generate("Hello", mock_model)
            
            assert isinstance(response, LLMResponse)
            assert response.text == "Hello! How can I help you?"
            assert response.model == "gpt-3.5-turbo"
            assert response.usage == {
                "prompt_tokens": 10,
                "completion_tokens": 8,
                "total_tokens": 18
            }

    @pytest.mark.asyncio
    @patch('lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE', True)
    async def test_generate_with_sdk_error_sanitized(self):
        """SDK errors should be surfaced with API keys fully redacted."""
        with patch('lamia.adapters.llm.openai_adapter.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            class MockSdkError(Exception):
                def __init__(self, message: str, status_code: int):
                    super().__init__(message)
                    self.status_code = status_code
            mock_client.chat.completions.create = AsyncMock(
                side_effect=MockSdkError(
                    "Incorrect API key provided: sk-dsfsd*******fsdf.",
                    status_code=401,
                )
            )

            adapter = OpenAIAdapter(api_key="test-key")

            mock_model = Mock(spec=LLMModel)
            mock_model.name = "gpt-4o"
            mock_model.get_model_name_without_provider = Mock(return_value="gpt-4o")
            mock_model.temperature = 0.7
            mock_model.max_tokens = 1000
            mock_model.top_p = 1.0
            mock_model.top_k = None
            mock_model.frequency_penalty = None
            mock_model.presence_penalty = None
            mock_model.seed = None

            from lamia.errors import ExternalOperationPermanentError
            with pytest.raises(ExternalOperationPermanentError) as exc:
                await adapter.generate("Hello", mock_model)

            msg = str(exc.value)
            assert "sk-dsfsd*******fsdf" not in msg
            assert "[REDACTED]" in msg
    
    @pytest.mark.asyncio
    @patch('lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE', False)
    @patch('aiohttp.ClientSession')
    async def test_generate_with_http_success(self, mock_session_class):
        """Test successful generation with HTTP fallback."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_http_response = AsyncMock()
        mock_http_response.status = 200
        mock_http_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "HTTP response text"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}
        })
        
        class MockPostContext:
            def __init__(self, response):
                self.response = response
            
            async def __aenter__(self):
                return self.response
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_session.post.return_value = MockPostContext(mock_http_response)
        
        adapter = OpenAIAdapter(api_key="test-key")
        await adapter.async_initialize()
        
        mock_model = Mock(spec=LLMModel)
        mock_model.name = "gpt-3.5-turbo"
        mock_model.get_model_name_without_provider = Mock(return_value="gpt-3.5-turbo")
        mock_model.temperature = 0.5
        mock_model.max_tokens = 500
        mock_model.top_p = 0.9
        mock_model.top_k = None
        mock_model.frequency_penalty = None
        mock_model.presence_penalty = None
        mock_model.seed = None
        
        response = await adapter.generate("Test prompt", mock_model)
        
        assert isinstance(response, LLMResponse)
        assert response.text == "HTTP response text"
        assert response.model == "gpt-3.5-turbo"
        assert response.usage == {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}


class TestOpenAIAdapterModels:
    """Test OpenAI adapter models classmethod."""

    @pytest.mark.asyncio
    @patch('lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE', False)
    async def test_list_models_success(self):
        """Test listing models via HTTP."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "data": [
                {"id": "gpt-3.5-turbo"},
                {"id": "gpt-4"}
            ]
        })

        class MockGetContext:
            def __init__(self, resp):
                self.resp = resp
            async def __aenter__(self):
                return self.resp
            async def __aexit__(self, *a):
                return None

        mock_session = Mock()
        mock_session.get = Mock(return_value=MockGetContext(mock_response))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            models = await OpenAIAdapter.models(api_key="test-key")

        assert len(models) == 2
        assert models[0]["id"] == "gpt-3.5-turbo"
        assert models[1]["id"] == "gpt-4"

    @pytest.mark.asyncio
    @patch('lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE', False)
    async def test_list_models_api_error(self):
        """Test models with API error status."""
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value="Unauthorized")

        class MockGetContext:
            def __init__(self, resp):
                self.resp = resp
            async def __aenter__(self):
                return self.resp
            async def __aexit__(self, *a):
                return None

        mock_session = Mock()
        mock_session.get = Mock(return_value=MockGetContext(mock_response))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            with pytest.raises(RuntimeError, match="OpenAI API error"):
                await OpenAIAdapter.models(api_key="bad-key")

    @pytest.mark.asyncio
    @patch('lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE', False)
    async def test_list_models_network_error(self):
        """Test models raises on network failure."""
        mock_session = Mock()
        mock_session.get = Mock(side_effect=aiohttp.ClientError("Connection refused"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            with pytest.raises(RuntimeError, match="Failed to fetch OpenAI models"):
                await OpenAIAdapter.models(api_key="test-key")

    def test_models_url_constant(self):
        """Test that MODELS_URL constant is correct."""
        assert OpenAIAdapter.MODELS_URL == "https://api.openai.com/v1/models"

    @pytest.mark.asyncio
    @patch('lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE', True)
    @patch('lamia.adapters.llm.openai_adapter.AsyncOpenAI')
    async def test_models_uses_sdk_when_available(self, mock_openai_cls):
        """Test models uses OpenAI SDK path when available."""
        mock_client = AsyncMock()
        mock_model = Mock()
        mock_model.model_dump.return_value = {"id": "gpt-4o", "owned_by": "openai"}
        mock_response = Mock()
        mock_response.data = [mock_model]
        mock_client.models.list = AsyncMock(return_value=mock_response)
        mock_openai_cls.return_value = mock_client

        models = await OpenAIAdapter.models(api_key="test-key")

        mock_openai_cls.assert_called_once_with(api_key="test-key")
        mock_client.models.list.assert_called_once()
        mock_client.close.assert_called_once()
        assert models == [{"id": "gpt-4o", "owned_by": "openai"}]


class TestOpenAIAdapterIntegration:
    """Test OpenAI adapter integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_adapter_routing_logic(self):
        """Test that adapter correctly routes between SDK and HTTP."""
        # Test with SDK available
        with patch('lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE', True):
            with patch('lamia.adapters.llm.openai_adapter.AsyncOpenAI'):
                adapter = OpenAIAdapter(api_key="test-key")
                assert adapter._use_sdk is True
        
        # Test with SDK not available
        with patch('lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE', False):
            adapter = OpenAIAdapter(api_key="test-key")
            assert adapter._use_sdk is False
    
    @pytest.mark.asyncio
    async def test_adapter_as_context_manager(self):
        """Test using adapter as async context manager."""
        with patch('lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE', True):
            with patch('lamia.adapters.llm.openai_adapter.AsyncOpenAI') as mock_openai:
                mock_client = AsyncMock()
                mock_openai.return_value = mock_client
                
                adapter = OpenAIAdapter(api_key="test-key")
                
                async with adapter as ctx_adapter:
                    assert ctx_adapter is adapter
                
                # Verify cleanup was called
                mock_client.close.assert_called_once()


class TestOpenAIAdapterStructuredOutput:
    """Test structured output with response_model."""

    @pytest.mark.asyncio
    @patch('lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE', True)
    async def test_generate_with_response_model_sdk(self):
        """SDK path sends response_format with JSON schema when response_model is provided."""
        with patch('lamia.adapters.llm.openai_adapter.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client

            mock_response = Mock()
            mock_choice = Mock()
            mock_choice.message.content = '{"ticker": "AAPL"}'
            mock_response.choices = [mock_choice]
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 5
            mock_response.usage.total_tokens = 15
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            adapter = OpenAIAdapter(api_key="test-key")

            class StockQuote(BaseModel):
                ticker: str

            mock_model = Mock(spec=LLMModel)
            mock_model.name = "gpt-4o"
            mock_model.get_model_name_without_provider = Mock(return_value="gpt-4o")
            mock_model.temperature = 0.7
            mock_model.max_tokens = 1000
            mock_model.top_p = 1.0
            mock_model.top_k = None
            mock_model.frequency_penalty = None
            mock_model.presence_penalty = None
            mock_model.seed = None

            response = await adapter.generate("Get AAPL", mock_model, response_model=StockQuote)

            assert response.text == '{"ticker": "AAPL"}'
            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert "response_format" in call_kwargs
            rf = call_kwargs["response_format"]
            assert rf["type"] == "json_schema"
            assert rf["json_schema"]["name"] == "StockQuote"
            assert rf["json_schema"]["strict"] is True
            assert "ticker" in rf["json_schema"]["schema"]["properties"]

    @pytest.mark.asyncio
    @patch('lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE', True)
    async def test_generate_without_response_model_no_format(self):
        """SDK path should NOT include response_format when response_model is None."""
        with patch('lamia.adapters.llm.openai_adapter.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client

            mock_response = Mock()
            mock_choice = Mock()
            mock_choice.message.content = "plain text"
            mock_response.choices = [mock_choice]
            mock_response.usage.prompt_tokens = 5
            mock_response.usage.completion_tokens = 3
            mock_response.usage.total_tokens = 8
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            adapter = OpenAIAdapter(api_key="test-key")

            mock_model = Mock(spec=LLMModel)
            mock_model.name = "gpt-4o"
            mock_model.get_model_name_without_provider = Mock(return_value="gpt-4o")
            mock_model.temperature = 0.7
            mock_model.max_tokens = 1000
            mock_model.top_p = 1.0
            mock_model.top_k = None
            mock_model.frequency_penalty = None
            mock_model.presence_penalty = None
            mock_model.seed = None

            response = await adapter.generate("Hello", mock_model)

            assert response.text == "plain text"
            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert "response_format" not in call_kwargs
