"""Tests for OpenAI LLM adapter."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import aiohttp
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


class TestOpenAIAdapterImplementationBugs:
    """Test cases that expose implementation bugs in OpenAI adapter."""
    
    @pytest.mark.asyncio
    @patch('lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE', True)
    async def test_generate_with_sdk_implementation_bugs(self):
        """Test generation with SDK - expects to fail due to implementation bugs."""
        with patch('lamia.adapters.llm.openai_adapter.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock the response structure
            mock_response = Mock()
            mock_choice = Mock()
            mock_choice.message.content = "Hello! How can I help you?"
            mock_response.choices = [mock_choice]
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 8
            mock_response.usage.total_tokens = 18
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            adapter = OpenAIAdapter(api_key="test-key")
            
            # Mock model
            mock_model = Mock(spec=LLMModel)
            mock_model.name = "gpt-3.5-turbo"
            mock_model.temperature = 0.7
            mock_model.max_tokens = 1000
            mock_model.top_p = 1.0
            mock_model.top_k = None
            mock_model.frequency_penalty = None
            mock_model.presence_penalty = None
            mock_model.seed = None
            
            # This will fail due to undefined 'self.model' (should be 'model.name')
            with pytest.raises(AttributeError, match="'OpenAIAdapter' object has no attribute 'model'"):
                await adapter.generate("Hello", mock_model)
    
    @pytest.mark.asyncio
    @patch('lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE', False)
    @patch('aiohttp.ClientSession')
    async def test_generate_with_http_implementation_bugs(self, mock_session_class):
        """Test generation with HTTP - expects to fail due to implementation bugs."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        # Mock HTTP response
        mock_http_response = AsyncMock()
        mock_http_response.status = 200
        mock_http_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "HTTP response text"}}],
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
        
        mock_session.post.return_value = MockPostContext(mock_http_response)
        
        adapter = OpenAIAdapter(api_key="test-key")
        await adapter.async_initialize()
        
        # Mock model
        mock_model = Mock(spec=LLMModel)
        mock_model.name = "gpt-3.5-turbo"
        mock_model.temperature = 0.5
        mock_model.max_tokens = 500
        mock_model.top_p = 0.9
        mock_model.top_k = None
        mock_model.frequency_penalty = None
        mock_model.presence_penalty = None
        mock_model.seed = None
        mock_model.stop_sequences = None
        
        # This will fail due to multiple implementation bugs
        with pytest.raises((AttributeError, NameError)):
            await adapter.generate("Test prompt", mock_model)


class TestOpenAIAdapterGetAvailableModels:
    """Test OpenAI adapter get_available_models method."""
    
    @pytest.mark.asyncio
    @patch('lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE', True)
    async def test_get_available_models_with_sdk(self):
        """Test getting available models with SDK."""
        with patch('lamia.adapters.llm.openai_adapter.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock models response
            mock_model1 = Mock()
            mock_model1.id = "gpt-3.5-turbo"
            mock_model2 = Mock()
            mock_model2.id = "gpt-4"
            
            mock_models_response = Mock()
            mock_models_response.data = [mock_model1, mock_model2]
            
            mock_client.models.list = AsyncMock(return_value=mock_models_response)
            
            adapter = OpenAIAdapter(api_key="test-key")
            
            models = await adapter.get_available_models()
            
            assert models == ["gpt-3.5-turbo", "gpt-4"]
            mock_client.models.list.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE', False)
    @patch('aiohttp.ClientSession')
    async def test_get_available_models_with_http(self, mock_session_class):
        """Test getting available models with HTTP."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        # Mock HTTP response
        mock_http_response = AsyncMock()
        mock_http_response.status = 200
        mock_http_response.json = AsyncMock(return_value={
            "data": [
                {"id": "gpt-3.5-turbo"},
                {"id": "gpt-4"}
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
        
        mock_session.get.return_value = MockGetContext(mock_http_response)
        
        adapter = OpenAIAdapter(api_key="test-key")
        await adapter.async_initialize()
        
        models = await adapter.get_available_models()
        
        assert models == ["gpt-3.5-turbo", "gpt-4"]
        mock_session.get.assert_called_once_with("https://api.openai.com/v1/models")


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
