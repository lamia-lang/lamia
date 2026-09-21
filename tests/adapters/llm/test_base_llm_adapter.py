"""Tests for base LLM adapter."""

import pytest
from abc import ABC
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Annotated, Dict, FrozenSet, List, Literal, Optional, Set, Tuple
from unittest.mock import Mock, patch
from uuid import UUID

import annotated_types as at
from pydantic import (
    AnyUrl,
    AwareDatetime,
    Base64Str,
    BaseModel,
    ByteSize,
    Field,
    FiniteFloat,
    FutureDate,
    IPvAnyAddress,
    Json,
    NaiveDatetime,
    NegativeFloat,
    NegativeInt,
    NonNegativeFloat,
    NonNegativeInt,
    NonPositiveFloat,
    NonPositiveInt,
    PastDate,
    PositiveFloat,
    PositiveInt,
    SecretStr,
    StrictInt,
    StrictStr,
    StringConstraints,
    conbytes,
    condecimal,
    confloat,
    confrozenset,
    conint,
    conlist,
    conset,
    constr,
)

from lamia.adapters.llm.base import (
    BaseLLMAdapter,
    LLMResponse,
    _pydantic_constraint_keywords,
    has_value_constraints,
    make_strict_schema,
    sanitize_api_error,
    strip_for_anthropic,
)
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
    
    def test_default_generate_exists(self):
        """Test that generate() is a non-abstract default implementation."""

        class MinimalAdapter(BaseLLMAdapter):
            API_URL = "http://test.example/v1/completions"

            @classmethod
            def name(cls) -> str:
                return "minimal"

            @classmethod
            def is_remote(cls) -> bool:
                return True

            async def close(self) -> None:
                pass

        adapter = MinimalAdapter()
        assert hasattr(adapter, 'generate')
        assert callable(adapter.generate)
    
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


class TestStripForAnthropic:
    """Test strip_for_anthropic removes only Anthropic-rejected keywords."""

    def test_strips_numeric_constraints(self):
        class M(BaseModel):
            score: float = Field(ge=0.0, le=1.0)
            count: int = Field(gt=0, lt=100)

        schema = make_strict_schema(M)
        stripped = strip_for_anthropic(schema)

        assert "minimum" not in stripped["properties"]["score"]
        assert "maximum" not in stripped["properties"]["score"]
        assert "exclusiveMinimum" not in stripped["properties"]["count"]
        assert "exclusiveMaximum" not in stripped["properties"]["count"]

    def test_strips_string_constraints(self):
        class M(BaseModel):
            name: str = Field(min_length=3, max_length=50)

        stripped = strip_for_anthropic(make_strict_schema(M))
        assert "minLength" not in stripped["properties"]["name"]
        assert "maxLength" not in stripped["properties"]["name"]

    def test_preserves_pattern(self):
        class M(BaseModel):
            code: str = Field(pattern=r"^[A-Z]{3}$")

        stripped = strip_for_anthropic(make_strict_schema(M))
        assert stripped["properties"]["code"]["pattern"] == "^[A-Z]{3}$"

    def test_strips_multiple_of(self):
        class M(BaseModel):
            step: int = Field(multiple_of=5)

        stripped = strip_for_anthropic(make_strict_schema(M))
        assert "multipleOf" not in stripped["properties"]["step"]

    def test_strips_list_constraints(self):
        class M(BaseModel):
            tags: List[str] = Field(min_length=1, max_length=10)

        stripped = strip_for_anthropic(make_strict_schema(M))
        assert "minItems" not in stripped["properties"]["tags"]
        assert "maxItems" not in stripped["properties"]["tags"]

    def test_recurses_nested_models(self):
        class Inner(BaseModel):
            rating: float = Field(ge=1, le=5)

        class Outer(BaseModel):
            item: Inner

        stripped = strip_for_anthropic(make_strict_schema(Outer))
        inner = stripped["properties"]["item"]["properties"]["rating"]
        assert "minimum" not in inner
        assert "maximum" not in inner

    def test_does_not_modify_original(self):
        class M(BaseModel):
            val: int = Field(ge=0)

        schema = make_strict_schema(M)
        strip_for_anthropic(schema)
        assert "minimum" in schema["properties"]["val"]

    def test_preserves_non_constraint_keys(self):
        class M(BaseModel):
            name: str = Field(description="A name", min_length=1)

        stripped = strip_for_anthropic(make_strict_schema(M))
        props = stripped["properties"]["name"]
        assert props["description"] == "A name"
        assert props["type"] == "string"
        assert "minLength" not in props

    def test_preserves_additional_properties_false(self):
        class M(BaseModel):
            x: int = Field(ge=0)

        stripped = strip_for_anthropic(make_strict_schema(M))
        assert stripped["additionalProperties"] is False

    def test_no_change_when_no_constraints(self):
        class M(BaseModel):
            name: str = Field(description="A name")

        schema = make_strict_schema(M)
        stripped = strip_for_anthropic(schema)
        assert stripped["properties"]["name"] == schema["properties"]["name"]


class TestHasValueConstraints:
    """Test has_value_constraints against every constraint form the docs describe."""

    def test_false_when_no_constraints(self):
        class M(BaseModel):
            name: str = Field(description="A name")
            count: int

        assert has_value_constraints(M) is False

    # ─── String constraints ──────────────────────────────────────────────

    def test_detects_min_length(self):
        class M(BaseModel):
            name: str = Field(min_length=3)

        assert has_value_constraints(M) is True

    def test_detects_max_length(self):
        class M(BaseModel):
            name: str = Field(max_length=100)

        assert has_value_constraints(M) is True

    def test_detects_pattern(self):
        class M(BaseModel):
            code: str = Field(pattern=r"^[A-Z]{3}")

        assert has_value_constraints(M) is True

    def test_detects_constr(self):
        class M(BaseModel):
            sku: constr(min_length=18, max_length=20)

        assert has_value_constraints(M) is True

    def test_detects_combined_string_constraints(self):
        class M(BaseModel):
            code: str = Field(min_length=3, pattern=r"^abc")

        assert has_value_constraints(M) is True

    # ─── Numeric constraints ─────────────────────────────────────────────

    def test_detects_gt(self):
        class M(BaseModel):
            count: int = Field(gt=0)

        assert has_value_constraints(M) is True

    def test_detects_ge(self):
        class M(BaseModel):
            score: float = Field(ge=0.0)

        assert has_value_constraints(M) is True

    def test_detects_lt(self):
        class M(BaseModel):
            count: int = Field(lt=100)

        assert has_value_constraints(M) is True

    def test_detects_le(self):
        class M(BaseModel):
            percentage: float = Field(le=100)

        assert has_value_constraints(M) is True

    def test_detects_multiple_of(self):
        class M(BaseModel):
            step: int = Field(multiple_of=5)

        assert has_value_constraints(M) is True

    # ─── Collection constraints ──────────────────────────────────────────

    def test_detects_list_constraints(self):
        class M(BaseModel):
            tags: List[str] = Field(min_length=1, max_length=5)

        assert has_value_constraints(M) is True

    def test_detects_dict_size_constraints(self):
        class M(BaseModel):
            counts: Dict[str, int] = Field(min_length=1, max_length=4)

        assert has_value_constraints(M) is True

    def test_detects_unique_items(self):
        class M(BaseModel):
            ids: Set[int]

        assert has_value_constraints(M) is True

    # ─── Type-derived constraints ────────────────────────────────────────

    def test_detects_enum_field(self):
        class Priority(str, Enum):
            LOW = "low"
            HIGH = "high"

        class M(BaseModel):
            priority: Priority

        assert has_value_constraints(M) is True

    def test_detects_literal_field(self):
        class M(BaseModel):
            mode: Literal["fast", "slow"]

        assert has_value_constraints(M) is True

    def test_detects_datetime_format(self):
        class M(BaseModel):
            created_at: datetime

        assert has_value_constraints(M) is True

    def test_detects_uuid_format(self):
        class M(BaseModel):
            identifier: UUID

        assert has_value_constraints(M) is True

    # ─── Optional, nested and recursive models ───────────────────────────

    def test_detects_decimal_digit_constraints(self):
        class M(BaseModel):
            amount: Decimal = Field(max_digits=5, decimal_places=2)

        assert has_value_constraints(M) is True

    def test_detects_decimal_digit_constraints_in_nested_model(self):
        class Inner(BaseModel):
            amount: Decimal = Field(max_digits=3, decimal_places=1)

        class Outer(BaseModel):
            entries: List[Inner]

        assert has_value_constraints(Outer) is True

    def test_detects_constraint_on_optional_field(self):
        class M(BaseModel):
            score: Optional[float] = Field(default=None, ge=0.0, le=1.0)

        assert has_value_constraints(M) is True

    def test_false_for_unconstrained_optional_field(self):
        class M(BaseModel):
            name: str
            phone: Optional[str] = Field(default=None, description="Phone")

        assert has_value_constraints(M) is False

    def test_detects_constraint_in_nested_model(self):
        class Inner(BaseModel):
            confidence: float = Field(ge=0.0, le=1.0)

        class Outer(BaseModel):
            results: List[Inner]

        assert has_value_constraints(Outer) is True

    def test_false_for_unconstrained_nested_model(self):
        class Inner(BaseModel):
            label: str

        class Outer(BaseModel):
            results: List[Inner]
            note: str

        assert has_value_constraints(Outer) is False

    def test_detects_constraint_in_self_referential_model(self):
        class Node(BaseModel):
            label: str = Field(max_length=20)
            children: List["Node"] = []

        Node.model_rebuild()
        assert has_value_constraints(Node) is True

    def test_handles_self_referential_model_without_constraints(self):
        class Node(BaseModel):
            label: str
            children: List["Node"] = []

        Node.model_rebuild()
        assert has_value_constraints(Node) is False

    # ─── Fail-open behaviour ─────────────────────────────────────────────

    def test_assumes_constraints_when_keyword_mapping_unreadable(self):
        class M(BaseModel):
            name: str

        with patch(
            "lamia.adapters.llm.base._pydantic_constraint_keywords",
            return_value=frozenset(),
        ):
            assert has_value_constraints(M) is True

    def test_assumes_constraints_when_schema_generation_fails(self):
        class M(BaseModel):
            name: str

        with patch.object(M, "model_json_schema", side_effect=RuntimeError("boom")):
            assert has_value_constraints(M) is True

    def test_assumes_constraints_when_ref_is_unresolvable(self):
        class Inner(BaseModel):
            label: str

        class Outer(BaseModel):
            inner: Inner

        broken = Outer.model_json_schema()
        broken.pop("$defs")
        with patch.object(Outer, "model_json_schema", return_value=broken):
            assert has_value_constraints(Outer) is True


def _model_with(annotation, field=None):
    """Build a single-field model so one annotation can be checked in isolation."""
    namespace = {"__annotations__": {"value": annotation}}
    if field is not None:
        namespace["value"] = field
    return type("Generated", (BaseModel,), namespace)


def _schema_keywords(model):
    """Collect every key appearing anywhere in the model's JSON schema."""
    found = set()

    def walk(node):
        if isinstance(node, dict):
            found.update(node.keys())
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(model.model_json_schema())
    return found


# One model per detectable keyword, so the suite fails if a keyword stops
# being reachable or a new one is added without coverage.
KEYWORD_MODELS = {
    "minimum": _model_with(float, Field(ge=0.0)),
    "maximum": _model_with(float, Field(le=1.0)),
    "exclusiveMinimum": _model_with(int, Field(gt=0)),
    "exclusiveMaximum": _model_with(int, Field(lt=100)),
    "multipleOf": _model_with(int, Field(multiple_of=5)),
    "minLength": _model_with(str, Field(min_length=3)),
    "maxLength": _model_with(str, Field(max_length=50)),
    "pattern": _model_with(str, Field(pattern=r"^[A-Z]+$")),
    "minItems": _model_with(List[int], Field(min_length=1)),
    "maxItems": _model_with(List[int], Field(max_length=5)),
    "minProperties": _model_with(Dict[str, int], Field(min_length=1)),
    "maxProperties": _model_with(Dict[str, int], Field(max_length=4)),
    "uniqueItems": _model_with(Set[int]),
    "format": _model_with(datetime),
    "enum": _model_with(Literal["a", "b"]),
    "const": _model_with(Literal["only"]),
}


class TestConstraintKeywordCoverage:
    """Every keyword the detector looks for is reachable from a real model."""

    def test_no_keyword_lacks_a_model(self):
        assert set(KEYWORD_MODELS) == set(_pydantic_constraint_keywords())

    @pytest.mark.parametrize("keyword", sorted(KEYWORD_MODELS))
    def test_model_emits_its_keyword(self, keyword):
        assert keyword in _schema_keywords(KEYWORD_MODELS[keyword])

    @pytest.mark.parametrize("keyword", sorted(KEYWORD_MODELS))
    def test_keyword_is_detected(self, keyword):
        assert has_value_constraints(KEYWORD_MODELS[keyword]) is True


class TestHasValueConstraintsAcrossPydanticTypes:
    """Constrained-type aliases, annotated-types metadata and format-bearing types."""

    @pytest.mark.parametrize("annotation", [
        conint(gt=1),
        confloat(ge=0.5),
        constr(min_length=2),
        conbytes(min_length=2),
        conlist(int, min_length=1),
        conset(int, min_length=1),
        confrozenset(int, min_length=1),
        condecimal(gt=Decimal(0)),
    ], ids=["conint", "confloat", "constr", "conbytes",
            "conlist", "conset", "confrozenset", "condecimal"])
    def test_detects_constrained_type_aliases(self, annotation):
        assert has_value_constraints(_model_with(annotation)) is True

    @pytest.mark.parametrize("annotation", [
        Annotated[List[int], at.Len(1, 3)],
        Annotated[int, at.Interval(gt=0, le=5)],
        Annotated[int, at.MultipleOf(4)],
        Annotated[str, at.MinLen(2)],
        Annotated[str, at.MaxLen(9)],
    ], ids=["Len", "Interval", "MultipleOf", "MinLen", "MaxLen"])
    def test_detects_annotated_types_metadata(self, annotation):
        assert has_value_constraints(_model_with(annotation)) is True

    @pytest.mark.parametrize("annotation", [
        datetime, date, time, timedelta, UUID, AnyUrl, IPvAnyAddress, Path,
    ], ids=["datetime", "date", "time", "timedelta",
            "UUID", "AnyUrl", "IPvAnyAddress", "Path"])
    def test_detects_format_bearing_types(self, annotation):
        assert has_value_constraints(_model_with(annotation)) is True

    @pytest.mark.parametrize("annotation", [
        FrozenSet[int], Set[str], Tuple[int, str],
    ], ids=["FrozenSet", "Set", "Tuple"])
    def test_detects_collection_shape_constraints(self, annotation):
        assert has_value_constraints(_model_with(annotation)) is True

    def test_detects_bytes_length_constraints(self):
        assert has_value_constraints(_model_with(bytes, Field(min_length=1, max_length=4))) is True

    def test_detects_decimal_digit_limits(self):
        assert has_value_constraints(_model_with(Decimal, Field(max_digits=5, decimal_places=2))) is True

    def test_detects_enum_subclass(self):
        class Priority(str, Enum):
            LOW = "low"
            HIGH = "high"

        assert has_value_constraints(_model_with(Priority)) is True

    @pytest.mark.parametrize("annotation", [int, str, float, bool, Json], 
                             ids=["int", "str", "float", "bool", "Json"])
    def test_false_for_unconstrained_types(self, annotation):
        assert has_value_constraints(_model_with(annotation)) is False

    def test_detects_string_constraints_annotation(self):
        model = _model_with(Annotated[str, StringConstraints(to_upper=True, strip_whitespace=True)])
        assert has_value_constraints(model) is True

    @pytest.mark.parametrize("annotation,kwargs", [
        (int, {"gt": 0}),
        (int, {"ge": 0}),
        (int, {"lt": 100}),
        (int, {"le": 100}),
        (int, {"multiple_of": 5}),
        (str, {"min_length": 3}),
        (str, {"max_length": 50}),
        (str, {"pattern": r"^[A-Z]"}),
        (Decimal, {"max_digits": 5, "decimal_places": 2}),
    ], ids=["gt", "ge", "lt", "le", "multiple_of",
            "min_length", "max_length", "pattern", "max_digits+decimal_places"])
    def test_detects_every_field_constraint_argument(self, annotation, kwargs):
        assert has_value_constraints(_model_with(annotation, Field(**kwargs))) is True

    @pytest.mark.parametrize("annotation", [
        PositiveInt, NegativeInt, NonNegativeInt, NonPositiveInt,
        PositiveFloat, NegativeFloat, NonNegativeFloat, NonPositiveFloat,
    ], ids=["PositiveInt", "NegativeInt", "NonNegativeInt", "NonPositiveInt",
            "PositiveFloat", "NegativeFloat", "NonNegativeFloat", "NonPositiveFloat"])
    def test_detects_sign_constrained_aliases(self, annotation):
        assert has_value_constraints(_model_with(annotation)) is True

    @pytest.mark.parametrize("annotation", [
        SecretStr, Base64Str, ByteSize,
    ], ids=["SecretStr", "Base64Str", "ByteSize"])
    def test_detects_special_string_types(self, annotation):
        assert has_value_constraints(_model_with(annotation)) is True

    @pytest.mark.parametrize("annotation", [
        PastDate, FutureDate, AwareDatetime, NaiveDatetime,
    ], ids=["PastDate", "FutureDate", "AwareDatetime", "NaiveDatetime"])
    def test_detects_temporal_variants(self, annotation):
        assert has_value_constraints(_model_with(annotation)) is True

    def test_detects_constraint_injected_through_json_schema_extra(self):
        model = _model_with(int, Field(json_schema_extra={"minimum": 5}))
        assert has_value_constraints(model) is True

    @pytest.mark.parametrize("annotation,field", [
        (float, Field(allow_inf_nan=False)),
        (FiniteFloat, None),
        (StrictInt, None),
        (StrictStr, None),
        (Annotated[int, at.Predicate(lambda value: value > 0)], None),
    ], ids=["allow_inf_nan", "FiniteFloat", "StrictInt", "StrictStr", "Predicate"])
    def test_detects_constraints_absent_from_the_schema(self, annotation, field):
        """Pydantic enforces these without emitting a JSON Schema keyword for them."""
        assert has_value_constraints(_model_with(annotation, field)) is True


class TestMakeStrictSchemaUnchanged:
    """Confirm make_strict_schema still includes all constraint keywords."""

    def test_includes_all_constraints(self):
        class M(BaseModel):
            name: str = Field(min_length=3, max_length=50, pattern=r"^[A-Z]")
            score: float = Field(ge=0.0, le=1.0)
            count: int = Field(gt=0, lt=100)
            step: int = Field(multiple_of=5)
            tags: List[str] = Field(min_length=1, max_length=10)

        schema = make_strict_schema(M)
        assert "minLength" in schema["properties"]["name"]
        assert "maxLength" in schema["properties"]["name"]
        assert "pattern" in schema["properties"]["name"]
        assert "minimum" in schema["properties"]["score"]
        assert "maximum" in schema["properties"]["score"]
        assert "exclusiveMinimum" in schema["properties"]["count"]
        assert "exclusiveMaximum" in schema["properties"]["count"]
        assert "multipleOf" in schema["properties"]["step"]
        assert "minItems" in schema["properties"]["tags"]
        assert "maxItems" in schema["properties"]["tags"]