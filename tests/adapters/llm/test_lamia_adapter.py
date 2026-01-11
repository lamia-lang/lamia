"""Comprehensive tests for Lamia LLM adapter."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import aiohttp
from lamia.adapters.llm.lamia_adapter import LamiaAdapter
from lamia.adapters.llm.base import LLMResponse
from lamia import LLMModel


class TestLamiaAdapterClassMethods:
    """Test LamiaAdapter class-level methods."""
    
    def test_name(self):
        """Test provider name."""
        assert LamiaAdapter.name() == "lamia"
    
    def test_env_var_names(self):
        """Test environment variable names."""
        env_vars = LamiaAdapter.env_var_names()
        assert env_vars == ["LAMIA_API_KEY"]
    
    def test_is_remote(self):
        """Test that Lamia adapter is remote."""
        assert LamiaAdapter.is_remote() is True
    
    def test_get_supported_providers(self):
        """Test supported providers."""
        providers = LamiaAdapter.get_supported_providers()
        assert "openai" in providers
        assert "anthropic" in providers
        assert isinstance(providers, set)


class TestLamiaAdapterInitialization:
    """Test LamiaAdapter initialization."""
    
    def test_initialization_with_default_url(self):
        """Test initialization with default API URL."""
        adapter = LamiaAdapter(api_key="test-key")
        
        assert adapter.api_key == "test-key"
        assert adapter.api_url == "http://209.151.237.90:3389"
        assert adapter.session is None
    
    def test_initialization_with_custom_url(self):
        """Test initialization with custom API URL."""
        adapter = LamiaAdapter(api_key="test-key", api_url="http://localhost:8080")
        
        assert adapter.api_key == "test-key"
        assert adapter.api_url == "http://localhost:8080"
        assert adapter.session is None
    
    def test_initialization_stores_api_key(self):
        """Test that API key is stored correctly."""
        adapter = LamiaAdapter(api_key="my-secret-key")
        assert adapter.api_key == "my-secret-key"


class TestLamiaAdapterEndpoints:
    """Test LamiaAdapter endpoint mapping."""
    
    def test_get_endpoint_for_openai(self):
        """Test endpoint mapping for OpenAI."""
        adapter = LamiaAdapter(api_key="test-key", api_url="http://localhost:8080")
        endpoint = adapter._get_endpoint_for_provider("openai")
        assert endpoint == "http://localhost:8080/v1/chat/completions"
    
    def test_get_endpoint_for_anthropic(self):
        """Test endpoint mapping for Anthropic."""
        adapter = LamiaAdapter(api_key="test-key", api_url="http://localhost:8080")
        endpoint = adapter._get_endpoint_for_provider("anthropic")
        assert endpoint == "http://localhost:8080/v1/messages"
    
    def test_get_endpoint_for_unsupported_provider(self):
        """Test endpoint mapping for unsupported provider."""
        adapter = LamiaAdapter(api_key="test-key")
        with pytest.raises(ValueError, match="Unsupported provider by Lamia proxy: unsupported"):
            adapter._get_endpoint_for_provider("unsupported")


class TestLamiaAdapterAsyncInitialize:
    """Test LamiaAdapter async initialization."""
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession')
    async def test_async_initialize_creates_session(self, mock_session_class):
        """Test that async_initialize creates session correctly."""
        mock_session = AsyncMock()
        mock_session_class.return_value = mock_session
        
        adapter = LamiaAdapter(api_key="test-api-key", api_url="http://localhost:8080")
        
        # Verify session is None before initialization
        assert adapter.session is None
        
        # Initialize adapter
        await adapter.async_initialize()
        
        # Verify session was created with correct headers
        mock_session_class.assert_called_once_with(
            headers={
                "Authorization": "Bearer test-api-key",
                "Content-Type": "application/json"
            }
        )
        
        # Verify session is now set
        assert adapter.session is not None
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession')
    async def test_async_initialize_session_already_exists(self, mock_session_class):
        """Test async initialization when session already exists."""
        existing_session = AsyncMock()
        adapter = LamiaAdapter(api_key="test-key")
        adapter.session = existing_session
        
        await adapter.async_initialize()
        
        # Should not create new session
        assert adapter.session == existing_session
        mock_session_class.assert_not_called()


class TestLamiaAdapterPayloadBuilding:
    """Test LamiaAdapter request payload building."""
    
    def test_build_request_payload_openai(self):
        """Test building request payload for OpenAI."""
        adapter = LamiaAdapter(api_key="test-key")
        
        mock_model = Mock(spec=LLMModel)
        mock_model.get_model_name_without_provider.return_value = "gpt-3.5-turbo"
        mock_model.temperature = 0.7
        mock_model.max_tokens = 1000
        mock_model.top_p = 0.9
        mock_model.frequency_penalty = 0.1
        mock_model.presence_penalty = 0.2
        mock_model.seed = 42
        
        payload = adapter._build_request_payload("Hello", mock_model, "openai")
        
        expected = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 0.9,
            "frequency_penalty": 0.1,
            "presence_penalty": 0.2,
            "seed": 42
        }
        
        assert payload == expected
    
    def test_build_request_payload_anthropic(self):
        """Test building request payload for Anthropic."""
        adapter = LamiaAdapter(api_key="test-key")
        
        mock_model = Mock(spec=LLMModel)
        mock_model.get_model_name_without_provider.return_value = "claude-3-sonnet"
        mock_model.temperature = 0.5
        mock_model.max_tokens = 2000
        mock_model.top_p = 0.8
        
        payload = adapter._build_request_payload("Hello", mock_model, "anthropic")
        
        expected = {
            "model": "claude-3-sonnet",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 2000,
            "temperature": 0.5,
            "top_p": 0.8
        }
        
        assert payload == expected
    
    def test_build_request_payload_with_defaults(self):
        """Test building request payload with default values."""
        adapter = LamiaAdapter(api_key="test-key")
        
        mock_model = Mock(spec=LLMModel)
        mock_model.get_model_name_without_provider.return_value = "gpt-3.5-turbo"
        mock_model.temperature = None
        mock_model.max_tokens = None
        mock_model.top_p = None
        mock_model.frequency_penalty = None
        mock_model.presence_penalty = None
        mock_model.seed = None
        
        payload = adapter._build_request_payload("Test", mock_model, "openai")
        
        assert payload["temperature"] == 0.7  # default
        assert payload["max_tokens"] == 1000  # default


class TestLamiaAdapterResponseParsing:
    """Test LamiaAdapter response parsing."""
    
    def test_parse_response_openai(self):
        """Test parsing OpenAI response format."""
        adapter = LamiaAdapter(api_key="test-key")
        
        mock_model = Mock(spec=LLMModel)
        mock_model.name = "openai/gpt-3.5-turbo"
        
        response_data = {
            "choices": [{"message": {"content": "Hello response"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}
        }
        
        result = adapter._parse_response(response_data, "openai", mock_model)
        
        assert isinstance(result, LLMResponse)
        assert result.text == "Hello response"
        assert result.raw_response == response_data
        assert result.model == mock_model
        assert result.usage == {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}
    
    def test_parse_response_anthropic(self):
        """Test parsing Anthropic response format."""
        adapter = LamiaAdapter(api_key="test-key")
        
        mock_model = Mock(spec=LLMModel)
        mock_model.name = "anthropic/claude-3-sonnet"
        
        response_data = {
            "content": [{"text": "Anthropic response"}],
            "usage": {"input_tokens": 10, "output_tokens": 5}
        }
        
        result = adapter._parse_response(response_data, "anthropic", mock_model)
        
        assert isinstance(result, LLMResponse)
        assert result.text == "Anthropic response"
        assert result.raw_response == response_data
        assert result.model == mock_model
        assert result.usage == {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15
        }
    
    def test_parse_response_openai_invalid_format(self):
        """Test parsing invalid OpenAI response format."""
        adapter = LamiaAdapter(api_key="test-key")
        mock_model = Mock(spec=LLMModel)
        
        # Missing choices
        response_data = {"usage": {}}
        
        with pytest.raises(RuntimeError, match="Invalid response format from OpenAI via Lamia"):
            adapter._parse_response(response_data, "openai", mock_model)
    
    def test_parse_response_anthropic_invalid_format(self):
        """Test parsing invalid Anthropic response format."""
        adapter = LamiaAdapter(api_key="test-key")
        mock_model = Mock(spec=LLMModel)
        
        # Missing content
        response_data = {"usage": {}}
        
        with pytest.raises(RuntimeError, match="Invalid response format from Anthropic via Lamia"):
            adapter._parse_response(response_data, "anthropic", mock_model)


class TestLamiaAdapterGeneration:
    """Test LamiaAdapter text generation."""
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession')
    async def test_generate_openai_success(self, mock_session_class):
        """Test successful generation with OpenAI model."""
        mock_session = AsyncMock()
        mock_session_class.return_value = mock_session
        
        # Mock HTTP response
        mock_http_response = AsyncMock()
        mock_http_response.status = 200
        mock_http_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "OpenAI response"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}
        })
        
        # Create async context manager mock
        class MockPostContext:
            def __init__(self, response):
                self.response = response
            
            async def __aenter__(self):
                return self.response
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_session.post = Mock(return_value=MockPostContext(mock_http_response))
        
        adapter = LamiaAdapter(api_key="test-key", api_url="http://localhost:8080")
        await adapter.async_initialize()
        
        # Mock model
        mock_model = Mock(spec=LLMModel)
        mock_model.name = "openai/gpt-3.5-turbo"
        mock_model.get_provider_name.return_value = "openai"
        mock_model.get_model_name_without_provider.return_value = "gpt-3.5-turbo"
        mock_model.temperature = 0.7
        mock_model.max_tokens = 1000
        mock_model.top_p = None
        mock_model.frequency_penalty = None
        mock_model.presence_penalty = None
        mock_model.seed = None
        
        response = await adapter.generate("Hello", mock_model)
        
        assert isinstance(response, LLMResponse)
        assert response.text == "OpenAI response"
        assert response.usage == {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}
        
        # Verify API call
        mock_session.post.assert_called_once_with(
            "http://localhost:8080/v1/chat/completions",
            json={
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": "Hello"}],
                "temperature": 0.7,
                "max_tokens": 1000
            }
        )
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession')
    async def test_generate_anthropic_success(self, mock_session_class):
        """Test successful generation with Anthropic model."""
        mock_session = AsyncMock()
        mock_session_class.return_value = mock_session
        
        # Mock HTTP response
        mock_http_response = AsyncMock()
        mock_http_response.status = 200
        mock_http_response.json = AsyncMock(return_value={
            "content": [{"text": "Anthropic response"}],
            "usage": {"input_tokens": 10, "output_tokens": 5}
        })
        
        # Create async context manager mock
        class MockPostContext:
            def __init__(self, response):
                self.response = response
            
            async def __aenter__(self):
                return self.response
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_session.post = Mock(return_value=MockPostContext(mock_http_response))
        
        adapter = LamiaAdapter(api_key="test-key", api_url="http://localhost:8080")
        await adapter.async_initialize()
        
        # Mock model
        mock_model = Mock(spec=LLMModel)
        mock_model.name = "anthropic/claude-3-sonnet"
        mock_model.get_provider_name.return_value = "anthropic"
        mock_model.get_model_name_without_provider.return_value = "claude-3-sonnet"
        mock_model.temperature = 0.5
        mock_model.max_tokens = 2000
        mock_model.top_p = 0.9
        
        response = await adapter.generate("Hello", mock_model)
        
        assert isinstance(response, LLMResponse)
        assert response.text == "Anthropic response"
        
        # Verify API call
        mock_session.post.assert_called_once_with(
            "http://localhost:8080/v1/messages",
            json={
                "model": "claude-3-sonnet",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 2000,
                "temperature": 0.5,
                "top_p": 0.9
            }
        )
    
    @pytest.mark.asyncio
    async def test_generate_adapter_not_initialized(self):
        """Test generation when adapter is not initialized."""
        adapter = LamiaAdapter(api_key="test-key")
        mock_model = Mock(spec=LLMModel)
        mock_model.name = "openai/gpt-3.5-turbo"
        mock_model.get_provider_name.return_value = "openai"
        
        with pytest.raises(RuntimeError, match="Adapter not initialized"):
            await adapter.generate("Hello", mock_model)


class TestLamiaAdapterErrorHandling:
    """Test LamiaAdapter error handling."""
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession')
    async def test_generate_api_error_401(self, mock_session_class):
        """Test generation with 401 unauthorized error."""
        mock_session = AsyncMock()
        mock_session_class.return_value = mock_session
        
        # Mock HTTP error response
        mock_http_response = AsyncMock()
        mock_http_response.status = 401
        
        class MockPostContext:
            def __init__(self, response):
                self.response = response
            
            async def __aenter__(self):
                return self.response
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_session.post = Mock(return_value=MockPostContext(mock_http_response))
        
        adapter = LamiaAdapter(api_key="test-key")
        await adapter.async_initialize()
        
        mock_model = Mock(spec=LLMModel)
        mock_model.name = "openai/gpt-3.5-turbo"
        mock_model.get_provider_name.return_value = "openai"
        
        with pytest.raises(RuntimeError, match="Invalid Lamia API key"):
            await adapter.generate("Hello", mock_model)
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession')
    async def test_generate_api_error_400(self, mock_session_class):
        """Test generation with 400 bad request error."""
        mock_session = AsyncMock()
        mock_session_class.return_value = mock_session
        
        # Mock HTTP error response
        mock_http_response = AsyncMock()
        mock_http_response.status = 400
        mock_http_response.text = AsyncMock(return_value="Bad request details")
        
        class MockPostContext:
            def __init__(self, response):
                self.response = response
            
            async def __aenter__(self):
                return self.response
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_session.post = Mock(return_value=MockPostContext(mock_http_response))
        
        adapter = LamiaAdapter(api_key="test-key")
        await adapter.async_initialize()
        
        mock_model = Mock(spec=LLMModel)
        mock_model.name = "openai/gpt-3.5-turbo"
        mock_model.get_provider_name.return_value = "openai"
        
        with pytest.raises(RuntimeError, match="Lamia API bad request: Bad request details"):
            await adapter.generate("Hello", mock_model)
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession')
    async def test_generate_api_error_402(self, mock_session_class):
        """Test generation with 402 insufficient credits error."""
        mock_session = AsyncMock()
        mock_session_class.return_value = mock_session
        
        # Mock HTTP error response
        mock_http_response = AsyncMock()
        mock_http_response.status = 402
        
        class MockPostContext:
            def __init__(self, response):
                self.response = response
            
            async def __aenter__(self):
                return self.response
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_session.post = Mock(return_value=MockPostContext(mock_http_response))
        
        adapter = LamiaAdapter(api_key="test-key")
        await adapter.async_initialize()
        
        mock_model = Mock(spec=LLMModel)
        mock_model.name = "openai/gpt-3.5-turbo"
        mock_model.get_provider_name.return_value = "openai"
        
        with pytest.raises(RuntimeError, match="Insufficient credits"):
            await adapter.generate("Hello", mock_model)
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession')
    async def test_generate_client_error(self, mock_session_class):
        """Test generation with aiohttp client error."""
        mock_session = AsyncMock()
        mock_session_class.return_value = mock_session
        
        # Mock aiohttp client error
        mock_session.post = Mock(side_effect=aiohttp.ClientError("Network error"))
        
        adapter = LamiaAdapter(api_key="test-key")
        await adapter.async_initialize()
        
        mock_model = Mock(spec=LLMModel)
        mock_model.name = "openai/gpt-3.5-turbo"
        mock_model.get_provider_name.return_value = "openai"
        
        with pytest.raises(RuntimeError, match="Failed to communicate with Lamia API: Network error"):
            await adapter.generate("Hello", mock_model)


class TestLamiaAdapterGetAvailableModels:
    """Test LamiaAdapter get_available_models method."""
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession')
    async def test_get_available_models_success(self, mock_session_class):
        """Test getting available models successfully."""
        mock_session = AsyncMock()
        mock_session_class.return_value = mock_session
        
        # Mock HTTP response
        mock_http_response = AsyncMock()
        mock_http_response.status = 200
        mock_http_response.json = AsyncMock(return_value={
            "data": [
                {"id": "gpt-3.5-turbo", "aliases": ["gpt35"]},
                {"id": "claude-3-sonnet"},
                {"id": "gpt-4", "aliases": ["gpt4", "gpt-4-latest"]}
            ]
        })
        
        # Create async context manager mock
        class MockGetContext:
            def __init__(self, response):
                self.response = response
            
            async def __aenter__(self):
                return self.response
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_session.get = Mock(return_value=MockGetContext(mock_http_response))
        
        adapter = LamiaAdapter(api_key="test-key", api_url="http://localhost:8080")
        await adapter.async_initialize()
        
        models = await adapter.get_available_models()
        
        expected_models = ["gpt-3.5-turbo", "gpt35", "claude-3-sonnet", "gpt-4", "gpt4", "gpt-4-latest"]
        assert models == expected_models
        
        mock_session.get.assert_called_once_with("http://localhost:8080/v1/models")
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession')
    async def test_get_available_models_no_aliases(self, mock_session_class):
        """Test getting available models without aliases."""
        mock_session = AsyncMock()
        mock_session_class.return_value = mock_session
        
        # Mock HTTP response without aliases
        mock_http_response = AsyncMock()
        mock_http_response.status = 200
        mock_http_response.json = AsyncMock(return_value={
            "data": [
                {"id": "gpt-3.5-turbo"},
                {"id": "claude-3-sonnet"}
            ]
        })
        
        # Create async context manager mock
        class MockGetContext:
            def __init__(self, response):
                self.response = response
            
            async def __aenter__(self):
                return self.response
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_session.get = Mock(return_value=MockGetContext(mock_http_response))
        
        adapter = LamiaAdapter(api_key="test-key")
        await adapter.async_initialize()
        
        models = await adapter.get_available_models()
        
        assert models == ["gpt-3.5-turbo", "claude-3-sonnet"]
    
    @pytest.mark.asyncio
    async def test_get_available_models_not_initialized(self):
        """Test getting models when adapter is not initialized."""
        adapter = LamiaAdapter(api_key="test-key")
        
        with pytest.raises(RuntimeError, match="Adapter not initialized"):
            await adapter.get_available_models()
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession')
    async def test_get_available_models_api_error(self, mock_session_class):
        """Test getting models with API error."""
        mock_session = AsyncMock()
        mock_session_class.return_value = mock_session
        
        # Mock HTTP error response
        mock_http_response = AsyncMock()
        mock_http_response.status = 401
        
        class MockGetContext:
            def __init__(self, response):
                self.response = response
            
            async def __aenter__(self):
                return self.response
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_session.get = Mock(return_value=MockGetContext(mock_http_response))
        
        adapter = LamiaAdapter(api_key="test-key")
        await adapter.async_initialize()
        
        with pytest.raises(RuntimeError, match="Invalid Lamia API key"):
            await adapter.get_available_models()
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession')
    async def test_get_available_models_invalid_response(self, mock_session_class):
        """Test getting models with invalid response format."""
        mock_session = AsyncMock()
        mock_session_class.return_value = mock_session
        
        # Mock invalid HTTP response (missing 'data' field)
        mock_http_response = AsyncMock()
        mock_http_response.status = 200
        mock_http_response.json = AsyncMock(return_value={"error": "Invalid format"})
        
        class MockGetContext:
            def __init__(self, response):
                self.response = response
            
            async def __aenter__(self):
                return self.response
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_session.get = Mock(return_value=MockGetContext(mock_http_response))
        
        adapter = LamiaAdapter(api_key="test-key")
        await adapter.async_initialize()
        
        with pytest.raises(RuntimeError, match="Invalid response format from Lamia API"):
            await adapter.get_available_models()


class TestLamiaAdapterCleanup:
    """Test LamiaAdapter resource cleanup."""
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession')
    async def test_close_with_session(self, mock_session_class):
        """Test cleanup when session exists."""
        mock_session = AsyncMock()
        mock_session_class.return_value = mock_session
        
        adapter = LamiaAdapter(api_key="test-key")
        await adapter.async_initialize()
        await adapter.close()
        
        mock_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_without_session(self):
        """Test cleanup when no session exists."""
        adapter = LamiaAdapter(api_key="test-key")
        
        # Should not raise any errors
        await adapter.close()


class TestLamiaAdapterIntegration:
    """Test LamiaAdapter integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_adapter_as_context_manager(self):
        """Test using adapter as async context manager."""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session
            
            adapter = LamiaAdapter(api_key="test-key")
            
            async with adapter as ctx_adapter:
                assert ctx_adapter is adapter
                assert adapter.session is not None
            
            # Verify cleanup was called
            mock_session.close.assert_called_once()
    
    def test_provider_coverage(self):
        """Test that all supported providers have endpoint mappings."""
        adapter = LamiaAdapter(api_key="test-key")
        
        for provider in LamiaAdapter.get_supported_providers():
            # Should not raise an exception
            endpoint = adapter._get_endpoint_for_provider(provider)
            assert endpoint.startswith(adapter.api_url)
            assert "/v1/" in endpoint