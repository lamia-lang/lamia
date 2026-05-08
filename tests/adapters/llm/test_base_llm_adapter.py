"""Tests for base LLM adapter."""

import pytest
from abc import ABC
from unittest.mock import Mock
from lamia.adapters.llm.base import BaseLLMAdapter, LLMResponse, sanitize_api_error
from lamia.errors import LLMProviderError, LLMErrorType
from lamia import LLMModel


class TestLLMResponse:
    """Test LLMResponse dataclass."""
    
    def test_llm_response_creation(self):
        """Test creating LLMResponse with all fields."""
        response = LLMResponse(
            text="Hello world",
            raw_response={"test": "data"},
            usage={"input_tokens": 10, "output_tokens": 5},
            model="test-model"
        )
        
        assert response.text == "Hello world"
        assert response.raw_response == {"test": "data"}
        assert response.usage == {"input_tokens": 10, "output_tokens": 5}
        assert response.model == "test-model"
    
    def test_llm_response_equality(self):
        """Test LLMResponse equality comparison."""
        response1 = LLMResponse(
            text="test",
            raw_response=None,
            usage={},
            model="model"
        )
        response2 = LLMResponse(
            text="test",
            raw_response=None,
            usage={},
            model="model"
        )
        
        assert response1 == response2
    
    def test_llm_response_different_values(self):
        """Test LLMResponse with different values are not equal."""
        response1 = LLMResponse(
            text="test1",
            raw_response=None,
            usage={},
            model="model"
        )
        response2 = LLMResponse(
            text="test2",
            raw_response=None,
            usage={},
            model="model"
        )
        
        assert response1 != response2


class ConcreteAdapter(BaseLLMAdapter):
    """Concrete implementation for testing."""
    
    @classmethod
    def name(cls) -> str:
        return "test"
    
    @classmethod
    def is_remote(cls) -> bool:
        return True
    
    async def generate(self, prompt: str, model: LLMModel, response_model=None) -> LLMResponse:
        return LLMResponse(
            text=f"Response to: {prompt}",
            raw_response={"prompt": prompt},
            usage={"input_tokens": 10, "output_tokens": 5},
            model=model.name
        )
    
    async def close(self) -> None:
        pass


class TestBaseLLMAdapter:
    """Test BaseLLMAdapter base class."""
    
    def test_base_adapter_is_abstract(self):
        """Test that BaseLLMAdapter is abstract."""
        assert ABC in BaseLLMAdapter.__bases__
        
        # Cannot instantiate abstract class
        with pytest.raises(TypeError):
            BaseLLMAdapter()
    
    def test_concrete_adapter_creation(self):
        """Test creating concrete adapter implementation."""
        adapter = ConcreteAdapter()
        
        assert adapter.name() == "test"
        assert adapter.is_remote() is True
    
    def test_default_env_var_names(self):
        """Test default environment variable name generation."""
        env_vars = ConcreteAdapter.env_var_names()
        
        assert env_vars == ["TEST_API_KEY"]
    
    def test_custom_env_var_names(self):
        """Test custom environment variable names."""
        
        class CustomAdapter(ConcreteAdapter):
            @classmethod
            def env_var_names(cls) -> list[str]:
                return ["CUSTOM_KEY", "CUSTOM_TOKEN", "CUSTOM_API_KEY"]
        
        env_vars = CustomAdapter.env_var_names()
        assert env_vars == ["CUSTOM_KEY", "CUSTOM_TOKEN", "CUSTOM_API_KEY"]
    
    def test_default_has_context_memory(self):
        """Test default context memory property."""
        adapter = ConcreteAdapter()
        
        assert adapter.has_context_memory is False
    
    def test_custom_has_context_memory(self):
        """Test custom context memory property."""
        
        class ContextAdapter(ConcreteAdapter):
            @property
            def has_context_memory(self) -> bool:
                return True
        
        adapter = ContextAdapter()
        assert adapter.has_context_memory is True
    
    @pytest.mark.asyncio
    async def test_default_async_initialize(self):
        """Test default async initialization does nothing."""
        adapter = ConcreteAdapter()
        
        # Should not raise any errors
        await adapter.async_initialize()
    
    @pytest.mark.asyncio
    async def test_custom_async_initialize(self):
        """Test custom async initialization."""
        
        class InitAdapter(ConcreteAdapter):
            def __init__(self):
                self.initialized = False
            
            async def async_initialize(self) -> None:
                self.initialized = True
        
        adapter = InitAdapter()
        assert adapter.initialized is False
        
        await adapter.async_initialize()
        assert adapter.initialized is True
    
    @pytest.mark.asyncio
    async def test_generate_method(self):
        """Test generate method with mock model."""
        adapter = ConcreteAdapter()
        mock_model = Mock(spec=LLMModel)
        mock_model.name = "test-model"
        
        response = await adapter.generate("Hello", mock_model)
        
        assert isinstance(response, LLMResponse)
        assert response.text == "Response to: Hello"
        assert response.raw_response == {"prompt": "Hello"}
        assert response.usage == {"input_tokens": 10, "output_tokens": 5}
        assert response.model == "test-model"
    
    @pytest.mark.asyncio
    async def test_context_manager_protocol(self):
        """Test adapter as async context manager."""
        
        class LifecycleAdapter(ConcreteAdapter):
            def __init__(self):
                self.initialized = False
                self.closed = False
            
            async def async_initialize(self) -> None:
                self.initialized = True
            
            async def close(self) -> None:
                self.closed = True
        
        adapter = LifecycleAdapter()
        assert adapter.initialized is False
        assert adapter.closed is False
        
        async with adapter as ctx_adapter:
            assert ctx_adapter is adapter
            assert adapter.initialized is True
            assert adapter.closed is False
        
        assert adapter.closed is True
    
    @pytest.mark.asyncio
    async def test_context_manager_exception_handling(self):
        """Test context manager cleanup on exception."""
        
        class ExceptionAdapter(ConcreteAdapter):
            def __init__(self):
                self.closed = False
            
            async def close(self) -> None:
                self.closed = True
        
        adapter = ExceptionAdapter()
        
        with pytest.raises(ValueError):
            async with adapter:
                raise ValueError("Test exception")
        
        # Should still be cleaned up
        assert adapter.closed is True


class TestBaseLLMAdapterAbstractMethods:
    """Test that abstract methods must be implemented."""
    
    def test_missing_name_method(self):
        """Test that missing name method prevents instantiation."""
        
        class BadAdapter(BaseLLMAdapter):
            @classmethod
            def is_remote(cls) -> bool:
                return True
            
            async def generate(self, prompt: str, model: LLMModel, response_model=None) -> LLMResponse:
                pass
            
            async def close(self) -> None:
                pass
        
        with pytest.raises(TypeError, match="Can't instantiate abstract class.*name"):
            BadAdapter()
    
    def test_missing_is_remote_method(self):
        """Test that missing is_remote method prevents instantiation."""
        
        class BadAdapter(BaseLLMAdapter):
            @classmethod
            def name(cls) -> str:
                return "bad"
            
            async def generate(self, prompt: str, model: LLMModel, response_model=None) -> LLMResponse:
                pass
            
            async def close(self) -> None:
                pass
        
        with pytest.raises(TypeError, match="Can't instantiate abstract class.*is_remote"):
            BadAdapter()
    
    def test_missing_generate_method(self):
        """Test that missing generate method prevents instantiation."""
        
        class BadAdapter(BaseLLMAdapter):
            @classmethod
            def name(cls) -> str:
                return "bad"
            
            @classmethod
            def is_remote(cls) -> bool:
                return True
            
            async def close(self) -> None:
                pass
        
        with pytest.raises(TypeError, match="Can't instantiate abstract class.*generate"):
            BadAdapter()
    
    def test_missing_close_method(self):
        """Test that missing close method prevents instantiation."""
        
        class BadAdapter(BaseLLMAdapter):
            @classmethod
            def name(cls) -> str:
                return "bad"
            
            @classmethod
            def is_remote(cls) -> bool:
                return True
            
            async def generate(self, prompt: str, model: LLMModel, response_model=None) -> LLMResponse:
                pass
        
        with pytest.raises(TypeError, match="Can't instantiate abstract class.*close"):
            BadAdapter()


class TestBaseLLMAdapterModels:
    """Test BaseLLMAdapter models default implementation."""

    @pytest.mark.asyncio
    async def test_default_list_models_returns_empty(self):
        """Test that the default models returns an empty list."""
        result = await ConcreteAdapter.models(api_key="test-key")
        assert result == []

    @pytest.mark.asyncio
    async def test_default_list_models_no_key(self):
        """Test that the default models works with empty key."""
        result = await ConcreteAdapter.models()
        assert result == []


class TestSanitizeApiError:
    """Test sanitize_api_error redacts credentials from error messages."""

    def test_openai_invalid_key_message(self):
        msg = "Incorrect API key provided: sk-abc123xyz. You can find your API key at https://platform.openai.com/account/api-keys."
        result = sanitize_api_error(msg)
        assert "sk-abc123xyz" not in result
        assert "[REDACTED]" in result

    def test_bearer_token_redacted(self):
        msg = "Authorization failed for Bearer sk-supersecret"
        result = sanitize_api_error(msg)
        assert "sk-supersecret" not in result
        assert "[REDACTED]" in result

    def test_x_api_key_with_sk_prefix_redacted(self):
        msg = "Invalid x-api-key: sk-mySecretKey123"
        result = sanitize_api_error(msg)
        assert "sk-mySecretKey123" not in result
        assert "[REDACTED]" in result

    def test_x_api_key_without_sk_prefix_unchanged(self):
        msg = "Invalid x-api-key: mysecretkey123"
        assert sanitize_api_error(msg) == msg

    def test_api_key_query_param_redacted(self):
        msg = "Request failed: api_key=sk-real-key-value is invalid"
        result = sanitize_api_error(msg)
        assert "sk-real-key-value" not in result
        assert "[REDACTED]" in result

    def test_multiple_keys_in_one_message(self):
        msg = "Keys: sk-firstkey123 and sk-secondkey456 are both invalid"
        result = sanitize_api_error(msg)
        assert "sk-firstkey123" not in result
        assert "sk-secondkey456" not in result
        assert result.count("[REDACTED]") == 2

    def test_multi_dash_key_redacted(self):
        msg = "Incorrect API key provided: sk-ant-api03-abcdefghijk."
        result = sanitize_api_error(msg)
        assert "sk-ant-api03-abcdefghijk" not in result
        assert "[REDACTED]" in result

    def test_proj_key_redacted(self):
        msg = "Invalid key sk-proj-T3BlbkFJabcdefghijk"
        result = sanitize_api_error(msg)
        assert "sk-proj-T3BlbkFJabcdefghijk" not in result
        assert "[REDACTED]" in result

    def test_api_redacted_key_fully_replaced(self):
        msg = "Incorrect API key provided: sk-dgdfg***************fdsf."
        result = sanitize_api_error(msg)
        assert "sk-dgdfg" not in result
        assert "[REDACTED]" in result

    def test_safe_message_unchanged(self):
        msg = "Connection timeout after 30 seconds"
        assert sanitize_api_error(msg) == msg

    def test_rate_limit_message_unchanged(self):
        msg = "Too many requests, rate limit exceeded"
        assert sanitize_api_error(msg) == msg

    def test_empty_string(self):
        assert sanitize_api_error("") == ""


class TestLLMProviderError:
    def test_invalid_key_classified_as_auth(self):
        exc = RuntimeError("Error code: 401 - {'error': {'message': 'Incorrect API key provided: sk-abc123'}}")
        pe = LLMProviderError.from_exception(exc)
        assert pe.error_type == LLMErrorType.AUTH
        assert "sk-abc123" not in pe.sanitized_detail
        assert pe.user_message == "Authentication failed: invalid API key. Update your API key in settings."

    def test_rate_limit_classified(self):
        exc = RuntimeError("OpenAI API error (429): rate limit exceeded")
        pe = LLMProviderError.from_exception(exc)
        assert pe.error_type == LLMErrorType.RATE_LIMIT
        assert pe.user_message == "Rate limit reached. Please retry in a moment."
        assert pe.status_code == 429

    def test_quota_classified(self):
        exc = RuntimeError("Error code: 402 - insufficient credits")
        pe = LLMProviderError.from_exception(exc)
        assert pe.error_type == LLMErrorType.QUOTA
        assert pe.status_code == 402

    def test_timeout_classified(self):
        exc = RuntimeError("Request timed out after 30 seconds")
        pe = LLMProviderError.from_exception(exc)
        assert pe.error_type == LLMErrorType.TIMEOUT

    def test_network_classified(self):
        exc = RuntimeError("Connection refused to api.openai.com")
        pe = LLMProviderError.from_exception(exc)
        assert pe.error_type == LLMErrorType.NETWORK

    def test_generic_provider_error_extracts_message(self):
        exc = RuntimeError("OpenAI API error: {'error': {'message': 'Model is overloaded, try again'}}")
        pe = LLMProviderError.from_exception(exc)
        assert pe.error_type == LLMErrorType.PROVIDER
        assert pe.user_message == "Model is overloaded, try again"

    def test_empty_error_gives_fallback(self):
        exc = RuntimeError("")
        pe = LLMProviderError.from_exception(exc)
        assert pe.error_type == LLMErrorType.PROVIDER
        assert pe.user_message == "Provider request failed."

    def test_custom_adapter_raw_error_works(self):
        exc = RuntimeError("claude-max-api error (status 500): Internal Server Error")
        pe = LLMProviderError.from_exception(exc)
        assert pe.error_type == LLMErrorType.PROVIDER
        assert pe.status_code == 500


class TestBaseLLMAdapterVariants:
    """Test different adapter variants and configurations."""
    
    def test_local_adapter(self):
        """Test local adapter implementation."""
        
        class LocalAdapter(ConcreteAdapter):
            @classmethod
            def is_remote(cls) -> bool:
                return False
        
        adapter = LocalAdapter()
        assert adapter.is_remote() is False
        assert adapter.name() == "test"
    
    def test_adapter_with_complex_env_vars(self):
        """Test adapter with multiple environment variable options."""
        
        class MultiEnvAdapter(ConcreteAdapter):
            @classmethod
            def name(cls) -> str:
                return "multi-env"
            
            @classmethod
            def env_var_names(cls) -> list[str]:
                return ["MULTI_ENV_API_KEY", "LEGACY_KEY", "FALLBACK_TOKEN"]
        
        env_vars = MultiEnvAdapter.env_var_names()
        assert env_vars == ["MULTI_ENV_API_KEY", "LEGACY_KEY", "FALLBACK_TOKEN"]
    
    @pytest.mark.asyncio
    async def test_adapter_with_complex_generate(self):
        """Test adapter with complex generation logic."""
        
        class ComplexAdapter(ConcreteAdapter):
            async def generate(self, prompt: str, model: LLMModel, response_model=None) -> LLMResponse:
                # Simulate processing
                processed_prompt = prompt.upper()
                
                return LLMResponse(
                    text=f"PROCESSED: {processed_prompt}",
                    raw_response={
                        "original_prompt": prompt,
                        "processed_prompt": processed_prompt,
                        "model_params": {
                            "temperature": getattr(model, 'temperature', 0.7),
                            "max_tokens": getattr(model, 'max_tokens', 1000)
                        }
                    },
                    usage={
                        "input_tokens": len(prompt.split()),
                        "output_tokens": len(processed_prompt.split()) + 1
                    },
                    model=getattr(model, 'name', 'unknown')
                )
        
        adapter = ComplexAdapter()
        mock_model = Mock(spec=LLMModel)
        mock_model.name = "complex-model"
        mock_model.temperature = 0.5
        mock_model.max_tokens = 2000
        
        response = await adapter.generate("hello world", mock_model)
        
        assert response.text == "PROCESSED: HELLO WORLD"
        assert response.raw_response["original_prompt"] == "hello world"
        assert response.raw_response["processed_prompt"] == "HELLO WORLD"
        assert response.raw_response["model_params"]["temperature"] == 0.5
        assert response.raw_response["model_params"]["max_tokens"] == 2000
        assert response.usage["input_tokens"] == 2  # "hello world" split
        assert response.usage["output_tokens"] == 3  # "HELLO WORLD" split + 1
        assert response.model == "complex-model"