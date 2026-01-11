"""Comprehensive tests for Pricing/Cost Calculation system."""

import pytest
import json
import tempfile
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
from lamia.eval.model_cost import ModelCost
from lamia.eval.pricing_provider import PricingProvider
from lamia.eval.model_pricer import ModelPricer
from lamia.eval.providers.openai_pricing_provider import OpenAIPricingProvider
from lamia.eval.providers.anthropic_pricing_provider import AnthropicPricingProvider
from lamia.eval.providers.ollama_pricing_provider import OllamaPricingProvider
from lamia.facade.result_types import LamiaResult
from lamia.validation.base import TrackingContext
from lamia.interpreter.command_types import CommandType


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def pricing_config_file():
    """Create a temporary pricing configuration file."""
    config_data = {
        "openai": {
            "models": [
                {
                    "name": "gpt-4o",
                    "input_cost_per_1m": 2.50,
                    "output_cost_per_1m": 10.00
                },
                {
                    "name": "gpt-4o-mini",
                    "input_cost_per_1m": 0.15,
                    "output_cost_per_1m": 0.60
                },
                {
                    "name": "gpt-3.5-turbo",
                    "input_cost_per_1m": 0.50,
                    "output_cost_per_1m": 1.50
                }
            ]
        },
        "anthropic": {
            "models": [
                {
                    "name": "claude-3-opus",
                    "input_cost_per_1m": 15.00,
                    "output_cost_per_1m": 75.00
                },
                {
                    "name": "claude-3-sonnet",
                    "input_cost_per_1m": 3.00,
                    "output_cost_per_1m": 15.00
                },
                {
                    "name": "claude-3-haiku",
                    "input_cost_per_1m": 0.25,
                    "output_cost_per_1m": 1.25
                }
            ]
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    temp_path.unlink()


@pytest.fixture
def mock_llm_manager():
    """Create a mock LLM manager."""
    manager = Mock()
    manager.create_adapter_from_config = AsyncMock()
    return manager


# ============================================================================
# MODEL COST TESTS
# ============================================================================

class TestModelCost:
    """Test ModelCost dataclass."""

    def test_model_cost_creation(self):
        """Test creating a ModelCost instance."""
        cost = ModelCost(
            input_tokens=1000,
            output_tokens=500,
            total_cost_usd=0.025
        )

        assert cost.input_tokens == 1000
        assert cost.output_tokens == 500
        assert cost.total_cost_usd == 0.025

    def test_model_cost_addition(self):
        """Test adding two ModelCost instances."""
        cost1 = ModelCost(1000, 500, 0.025)
        cost2 = ModelCost(2000, 1000, 0.050)

        result = cost1 + cost2

        assert result.input_tokens == 3000
        assert result.output_tokens == 1500
        assert result.total_cost_usd == 0.075

    def test_model_cost_addition_with_none(self):
        """Test adding None to ModelCost returns original."""
        cost = ModelCost(1000, 500, 0.025)

        result = cost + None

        assert result == cost
        assert result.input_tokens == 1000

    def test_model_cost_string_representation(self):
        """Test ModelCost string representation."""
        cost = ModelCost(1000, 500, 0.025)

        result_str = str(cost)

        assert "$0.025000" in result_str
        assert "1000 input" in result_str
        assert "500 output" in result_str
        assert "tokens" in result_str

    def test_model_cost_zero_cost(self):
        """Test ModelCost with zero cost."""
        cost = ModelCost(0, 0, 0.0)

        assert cost.input_tokens == 0
        assert cost.output_tokens == 0
        assert cost.total_cost_usd == 0.0
        assert "$0.000000" in str(cost)

    def test_model_cost_large_values(self):
        """Test ModelCost with large values."""
        cost = ModelCost(
            input_tokens=10_000_000,
            output_tokens=5_000_000,
            total_cost_usd=250.50
        )

        assert cost.input_tokens == 10_000_000
        assert cost.output_tokens == 5_000_000
        assert cost.total_cost_usd == 250.50

    def test_model_cost_multiple_additions(self):
        """Test multiple ModelCost additions."""
        cost1 = ModelCost(100, 50, 0.01)
        cost2 = ModelCost(200, 100, 0.02)
        cost3 = ModelCost(300, 150, 0.03)

        result = cost1 + cost2 + cost3

        assert result.input_tokens == 600
        assert result.output_tokens == 300
        assert result.total_cost_usd == 0.06


# ============================================================================
# PRICING PROVIDER BASE CLASS TESTS
# ============================================================================

class TestPricingProviderInterface:
    """Test PricingProvider abstract base class."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that PricingProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            PricingProvider()

    def test_subclass_must_implement_all_methods(self):
        """Test that subclass must implement all abstract methods."""
        class IncompletePricingProvider(PricingProvider):
            @classmethod
            def name(cls) -> str:
                return "incomplete"

        with pytest.raises(TypeError):
            IncompletePricingProvider()

    def test_complete_subclass_can_be_instantiated(self):
        """Test that complete subclass can be instantiated."""
        class CompletePricingProvider(PricingProvider):
            @classmethod
            def name(cls) -> str:
                return "complete"

            async def get_model_pricing(self, model: str):
                return {"input_cost_per_1m": 1.0, "output_cost_per_1m": 2.0}

            async def calculate_cost(self, model: str, usage: dict):
                return ModelCost(100, 50, 0.01)

            async def update_pricing(self) -> bool:
                return True

            async def get_ordered_models(self, max_model: str):
                return [max_model]

        provider = CompletePricingProvider()
        assert provider is not None


# ============================================================================
# MODEL PRICER TESTS
# ============================================================================

class TestModelPricerInitialization:
    """Test ModelPricer initialization."""

    def test_init_with_default_config_path(self):
        """Test initialization with default config path."""
        pricer = ModelPricer()

        assert pricer.config_path is not None
        assert pricer._provider_classes is not None
        assert len(pricer._provider_instances) == 0

    def test_init_with_custom_config_path(self, pricing_config_file):
        """Test initialization with custom config path."""
        pricer = ModelPricer(config_path=pricing_config_file)

        assert pricer.config_path == pricing_config_file

    def test_init_with_llm_manager(self, mock_llm_manager):
        """Test initialization with LLM manager."""
        pricer = ModelPricer(llm_manager=mock_llm_manager)

        assert pricer.llm_manager == mock_llm_manager

    def test_provider_registry_built(self):
        """Test that provider registry is built on initialization."""
        pricer = ModelPricer()

        assert "openai" in pricer._provider_classes
        assert "anthropic" in pricer._provider_classes
        assert "ollama" in pricer._provider_classes

    def test_get_available_providers(self):
        """Test getting list of available providers."""
        pricer = ModelPricer()

        providers = pricer.get_available_providers()

        assert "openai" in providers
        assert "anthropic" in providers
        assert "ollama" in providers
        assert len(providers) == 3


class TestModelPricerProviderManagement:
    """Test ModelPricer provider management."""

    def test_get_provider_lazy_loading(self, pricing_config_file):
        """Test lazy loading of providers."""
        pricer = ModelPricer(config_path=pricing_config_file)

        # Initially no instances
        assert len(pricer._provider_instances) == 0

        # Get provider should lazy load
        provider = pricer._get_provider("openai")

        assert provider is not None
        assert isinstance(provider, OpenAIPricingProvider)
        assert "openai" in pricer._provider_instances

    def test_get_provider_caches_instance(self, pricing_config_file):
        """Test that provider instances are cached."""
        pricer = ModelPricer(config_path=pricing_config_file)

        provider1 = pricer._get_provider("openai")
        provider2 = pricer._get_provider("openai")

        assert provider1 is provider2

    def test_get_provider_unknown_returns_none(self):
        """Test getting unknown provider returns None."""
        pricer = ModelPricer()

        provider = pricer._get_provider("unknown_provider")

        assert provider is None

    def test_get_provider_handles_instantiation_errors(self, pricing_config_file):
        """Test handling of provider instantiation errors."""
        pricer = ModelPricer(config_path=pricing_config_file)

        # Mock provider class to raise error
        with patch.object(pricer._provider_classes['openai'], '__call__', side_effect=Exception("Init error")):
            provider = pricer._get_provider("openai")

        assert provider is None


@pytest.mark.asyncio
class TestModelPricerCostCalculation:
    """Test ModelPricer cost calculation."""

    async def test_calculate_cost_openai(self, pricing_config_file):
        """Test calculating cost for OpenAI model."""
        pricer = ModelPricer(config_path=pricing_config_file)

        context = TrackingContext(
            data_provider_name="openai:gpt-4o",
            command_type=CommandType.LLM,
            metadata={
                "usage": {
                    "prompt_tokens": 1000,
                    "completion_tokens": 500
                }
            }
        )
        result = LamiaResult(
            result_text="test",
            typed_result="test",
            tracking_context=context
        )

        cost = await pricer.calculate_cost("openai:gpt-4o", result)

        assert cost is not None
        assert cost.input_tokens == 1000
        assert cost.output_tokens == 500
        # 1000 * 2.50 / 1M + 500 * 10.00 / 1M = 0.0025 + 0.005 = 0.0075
        assert abs(cost.total_cost_usd - 0.0075) < 0.0001

    async def test_calculate_cost_anthropic(self, pricing_config_file):
        """Test calculating cost for Anthropic model."""
        pricer = ModelPricer(config_path=pricing_config_file)

        context = TrackingContext(
            data_provider_name="anthropic:claude-3-sonnet",
            command_type=CommandType.LLM,
            metadata={
                "usage": {
                    "input_tokens": 2000,
                    "output_tokens": 1000
                }
            }
        )
        result = LamiaResult(
            result_text="test",
            typed_result="test",
            tracking_context=context
        )

        cost = await pricer.calculate_cost("anthropic:claude-3-sonnet", result)

        assert cost is not None
        assert cost.input_tokens == 2000
        assert cost.output_tokens == 1000
        # 2000 * 3.00 / 1M + 1000 * 15.00 / 1M = 0.006 + 0.015 = 0.021
        assert abs(cost.total_cost_usd - 0.021) < 0.0001

    async def test_calculate_cost_no_usage_data(self, pricing_config_file):
        """Test calculating cost with no usage data."""
        pricer = ModelPricer(config_path=pricing_config_file)

        context = TrackingContext(
            data_provider_name="openai:gpt-4o",
            command_type=CommandType.LLM,
            metadata={}  # No usage data
        )
        result = LamiaResult(
            result_text="test",
            typed_result="test",
            tracking_context=context
        )

        cost = await pricer.calculate_cost("openai:gpt-4o", result)

        assert cost is None

    async def test_calculate_cost_unknown_provider(self):
        """Test calculating cost for unknown provider."""
        pricer = ModelPricer()

        context = TrackingContext(
            data_provider_name="unknown:model",
            command_type=CommandType.LLM,
            metadata={"usage": {"prompt_tokens": 100}}
        )
        result = LamiaResult(
            result_text="test",
            typed_result="test",
            tracking_context=context
        )

        cost = await pricer.calculate_cost("unknown:model", result)

        assert cost is None


@pytest.mark.asyncio
class TestModelPricerUpdatePricing:
    """Test ModelPricer pricing updates."""

    async def test_update_pricing_success(self, pricing_config_file):
        """Test successful pricing update."""
        pricer = ModelPricer(config_path=pricing_config_file)

        result = await pricer.update_pricing("openai")

        assert result is True

    async def test_update_pricing_unknown_provider(self):
        """Test updating pricing for unknown provider."""
        pricer = ModelPricer()

        result = await pricer.update_pricing("unknown")

        assert result is False

    async def test_update_pricing_error_handling(self, pricing_config_file):
        """Test handling of pricing update errors."""
        pricer = ModelPricer(config_path=pricing_config_file)

        # Get provider to cache it
        provider = pricer._get_provider("openai")

        # Mock update_pricing to raise error
        with patch.object(provider, 'update_pricing', side_effect=Exception("Update failed")):
            result = await pricer.update_pricing("openai")

        assert result is False


@pytest.mark.asyncio
class TestModelPricerOrderedModels:
    """Test ModelPricer ordered models functionality."""

    async def test_get_ordered_models_openai(self, pricing_config_file):
        """Test getting ordered OpenAI models."""
        pricer = ModelPricer(config_path=pricing_config_file)

        # Mock get_available_models to avoid API call
        provider = pricer._get_provider("openai")
        with patch.object(provider, 'get_available_models', return_value=AsyncMock(return_value=[])):
            models = await pricer.get_ordered_models("openai:gpt-4o")

        assert isinstance(models, list)
        # Should include gpt-4o and cheaper models
        assert any("gpt" in model for model in models)

    async def test_get_ordered_models_unknown_provider(self):
        """Test getting ordered models for unknown provider."""
        pricer = ModelPricer()

        models = await pricer.get_ordered_models("unknown:model")

        assert models == ["unknown:model"]


# ============================================================================
# OPENAI PRICING PROVIDER TESTS
# ============================================================================

class TestOpenAIPricingProvider:
    """Test OpenAIPricingProvider."""

    def test_init(self, pricing_config_file):
        """Test OpenAI provider initialization."""
        provider = OpenAIPricingProvider(pricing_config_file)

        assert provider.config_path == pricing_config_file
        assert provider.pricing_data is not None
        assert "gpt-4o" in provider.pricing_data

    def test_name(self):
        """Test provider name."""
        assert OpenAIPricingProvider.name() == "openai"

    def test_load_pricing_config(self, pricing_config_file):
        """Test loading pricing configuration."""
        provider = OpenAIPricingProvider(pricing_config_file)

        assert "gpt-4o" in provider.pricing_data
        assert provider.pricing_data["gpt-4o"]["input_cost_per_1m"] == 2.50
        assert provider.pricing_data["gpt-4o"]["output_cost_per_1m"] == 10.00

    def test_load_pricing_config_missing_file(self):
        """Test loading with missing config file."""
        provider = OpenAIPricingProvider(Path("/nonexistent/path.json"))

        assert provider.pricing_data == {}


@pytest.mark.asyncio
class TestOpenAIPricingProviderOperations:
    """Test OpenAI pricing provider operations."""

    async def test_get_model_pricing(self, pricing_config_file):
        """Test getting model pricing."""
        provider = OpenAIPricingProvider(pricing_config_file)

        pricing = await provider.get_model_pricing("openai:gpt-4o")

        assert pricing is not None
        assert pricing["input_cost_per_1m"] == 2.50
        assert pricing["output_cost_per_1m"] == 10.00

    async def test_get_model_pricing_without_prefix(self, pricing_config_file):
        """Test getting model pricing without openai: prefix."""
        provider = OpenAIPricingProvider(pricing_config_file)

        pricing = await provider.get_model_pricing("gpt-4o")

        assert pricing is not None
        assert pricing["input_cost_per_1m"] == 2.50

    async def test_get_model_pricing_unknown_model(self, pricing_config_file):
        """Test getting pricing for unknown model."""
        provider = OpenAIPricingProvider(pricing_config_file)

        pricing = await provider.get_model_pricing("unknown-model")

        assert pricing is None

    async def test_calculate_cost(self, pricing_config_file):
        """Test calculating cost for OpenAI model."""
        provider = OpenAIPricingProvider(pricing_config_file)

        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 500
        }

        cost = await provider.calculate_cost("openai:gpt-4o", usage)

        assert cost.input_tokens == 1000
        assert cost.output_tokens == 500
        assert abs(cost.total_cost_usd - 0.0075) < 0.0001

    async def test_calculate_cost_no_pricing_data(self, pricing_config_file):
        """Test calculating cost for model with no pricing data."""
        provider = OpenAIPricingProvider(pricing_config_file)

        usage = {"prompt_tokens": 100, "completion_tokens": 50}

        cost = await provider.calculate_cost("unknown-model", usage)

        assert cost.input_tokens == 0
        assert cost.output_tokens == 0
        assert cost.total_cost_usd == 0.0

    async def test_update_pricing(self, pricing_config_file):
        """Test update pricing (manual config)."""
        provider = OpenAIPricingProvider(pricing_config_file)

        result = await provider.update_pricing()

        assert result is True


# ============================================================================
# ANTHROPIC PRICING PROVIDER TESTS
# ============================================================================

class TestAnthropicPricingProvider:
    """Test AnthropicPricingProvider."""

    def test_init(self, pricing_config_file):
        """Test Anthropic provider initialization."""
        provider = AnthropicPricingProvider(pricing_config_file)

        assert provider.config_path == pricing_config_file
        assert provider.pricing_data is not None
        assert "claude-3-opus" in provider.pricing_data

    def test_name(self):
        """Test provider name."""
        assert AnthropicPricingProvider.name() == "anthropic"

    def test_load_pricing_config(self, pricing_config_file):
        """Test loading pricing configuration."""
        provider = AnthropicPricingProvider(pricing_config_file)

        assert "claude-3-opus" in provider.pricing_data
        assert provider.pricing_data["claude-3-opus"]["input_cost_per_1m"] == 15.00
        assert provider.pricing_data["claude-3-opus"]["output_cost_per_1m"] == 75.00


@pytest.mark.asyncio
class TestAnthropicPricingProviderOperations:
    """Test Anthropic pricing provider operations."""

    async def test_get_model_pricing(self, pricing_config_file):
        """Test getting model pricing."""
        provider = AnthropicPricingProvider(pricing_config_file)

        pricing = await provider.get_model_pricing("anthropic:claude-3-sonnet")

        assert pricing is not None
        assert pricing["input_cost_per_1m"] == 3.00
        assert pricing["output_cost_per_1m"] == 15.00

    async def test_calculate_cost(self, pricing_config_file):
        """Test calculating cost for Anthropic model."""
        provider = AnthropicPricingProvider(pricing_config_file)

        usage = {
            "input_tokens": 2000,
            "output_tokens": 1000
        }

        cost = await provider.calculate_cost("anthropic:claude-3-sonnet", usage)

        assert cost.input_tokens == 2000
        assert cost.output_tokens == 1000
        # 2000 * 3.00 / 1M + 1000 * 15.00 / 1M
        assert abs(cost.total_cost_usd - 0.021) < 0.0001

    async def test_get_ordered_models(self, pricing_config_file):
        """Test getting ordered models."""
        provider = AnthropicPricingProvider(pricing_config_file)

        models = await provider.get_ordered_models("anthropic:claude-3-opus")

        assert isinstance(models, list)
        assert len(models) > 0
        # Should be ordered by cost (expensive to cheap)
        assert "anthropic:claude-3-opus" in models

    async def test_update_pricing(self, pricing_config_file):
        """Test update pricing (manual config)."""
        provider = AnthropicPricingProvider(pricing_config_file)

        result = await provider.update_pricing()

        assert result is True


# ============================================================================
# OLLAMA PRICING PROVIDER TESTS
# ============================================================================

class TestOllamaPricingProvider:
    """Test OllamaPricingProvider."""

    def test_init(self, pricing_config_file):
        """Test Ollama provider initialization."""
        provider = OllamaPricingProvider(pricing_config_file)

        assert provider.config_path == pricing_config_file
        assert provider.pricing_data == {}  # Ollama is free

    def test_name(self):
        """Test provider name."""
        assert OllamaPricingProvider.name() == "ollama"


@pytest.mark.asyncio
class TestOllamaPricingProviderOperations:
    """Test Ollama pricing provider operations."""

    async def test_get_model_pricing_free(self, pricing_config_file):
        """Test getting model pricing (always free)."""
        provider = OllamaPricingProvider(pricing_config_file)

        pricing = await provider.get_model_pricing("ollama:llama3.2")

        assert pricing is not None
        assert pricing["input_cost_per_1m"] == 0.0
        assert pricing["output_cost_per_1m"] == 0.0

    async def test_calculate_cost_free(self, pricing_config_file):
        """Test calculating cost for Ollama model (always free)."""
        provider = OllamaPricingProvider(pricing_config_file)

        usage = {
            "prompt_tokens": 10000,
            "completion_tokens": 5000
        }

        cost = await provider.calculate_cost("ollama:llama3.2", usage)

        assert cost.input_tokens == 10000
        assert cost.output_tokens == 5000
        assert cost.total_cost_usd == 0.0

    def test_extract_family_name(self, pricing_config_file):
        """Test extracting family name from model."""
        provider = OllamaPricingProvider(pricing_config_file)

        assert provider._extract_family_name("llama3.2:1b") == "llama3.2"
        assert provider._extract_family_name("llama3.2") == "llama3.2"
        assert provider._extract_family_name("mistral:7b") == "mistral"

    def test_extract_param_count_from_name(self, pricing_config_file):
        """Test extracting parameter count from model name."""
        provider = OllamaPricingProvider(pricing_config_file)

        assert provider._extract_param_count_from_name("llama3.2:1b") == 1
        assert provider._extract_param_count_from_name("llama3.2:70b") == 70
        assert provider._extract_param_count_from_name("llama3.2:7b") == 7
        assert provider._extract_param_count_from_name("unknown-model") == 1

    async def test_update_pricing(self, pricing_config_file):
        """Test update pricing (not implemented for Ollama)."""
        provider = OllamaPricingProvider(pricing_config_file)

        result = await provider.update_pricing()

        assert result is True


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@pytest.mark.asyncio
class TestPricingSystemIntegration:
    """Integration tests for pricing system."""

    async def test_end_to_end_cost_calculation_openai(self, pricing_config_file):
        """Test end-to-end cost calculation for OpenAI."""
        pricer = ModelPricer(config_path=pricing_config_file)

        context = TrackingContext(
            data_provider_name="openai:gpt-4o",
            command_type=CommandType.LLM,
            metadata={
                "usage": {
                    "prompt_tokens": 1500,
                    "completion_tokens": 750
                }
            }
        )
        result = LamiaResult(
            result_text="Generated response",
            typed_result="Processed",
            tracking_context=context
        )

        cost = await pricer.calculate_cost("openai:gpt-4o", result)

        assert cost is not None
        assert cost.input_tokens == 1500
        assert cost.output_tokens == 750
        assert cost.total_cost_usd > 0

    async def test_end_to_end_cost_calculation_anthropic(self, pricing_config_file):
        """Test end-to-end cost calculation for Anthropic."""
        pricer = ModelPricer(config_path=pricing_config_file)

        context = TrackingContext(
            data_provider_name="anthropic:claude-3-haiku",
            command_type=CommandType.LLM,
            metadata={
                "usage": {
                    "input_tokens": 1000,
                    "output_tokens": 500
                }
            }
        )
        result = LamiaResult(
            result_text="Generated response",
            typed_result="Processed",
            tracking_context=context
        )

        cost = await pricer.calculate_cost("anthropic:claude-3-haiku", result)

        assert cost is not None
        assert cost.total_cost_usd > 0
        # Haiku should be cheapest
        assert cost.total_cost_usd < 0.001

    async def test_end_to_end_cost_calculation_ollama(self, pricing_config_file):
        """Test end-to-end cost calculation for Ollama (free)."""
        pricer = ModelPricer(config_path=pricing_config_file)

        context = TrackingContext(
            data_provider_name="ollama:llama3.2",
            command_type=CommandType.LLM,
            metadata={
                "usage": {
                    "prompt_tokens": 5000,
                    "completion_tokens": 2500
                }
            }
        )
        result = LamiaResult(
            result_text="Generated response",
            typed_result="Processed",
            tracking_context=context
        )

        cost = await pricer.calculate_cost("ollama:llama3.2", result)

        assert cost is not None
        assert cost.input_tokens == 5000
        assert cost.output_tokens == 2500
        assert cost.total_cost_usd == 0.0  # Free!

    async def test_multiple_costs_accumulation(self, pricing_config_file):
        """Test accumulating multiple costs."""
        pricer = ModelPricer(config_path=pricing_config_file)

        # First request
        context1 = TrackingContext(
            data_provider_name="openai:gpt-4o",
            command_type=CommandType.LLM,
            metadata={"usage": {"prompt_tokens": 1000, "completion_tokens": 500}}
        )
        result1 = LamiaResult("test", "test", context1)
        cost1 = await pricer.calculate_cost("openai:gpt-4o", result1)

        # Second request
        context2 = TrackingContext(
            data_provider_name="openai:gpt-4o",
            command_type=CommandType.LLM,
            metadata={"usage": {"prompt_tokens": 2000, "completion_tokens": 1000}}
        )
        result2 = LamiaResult("test", "test", context2)
        cost2 = await pricer.calculate_cost("openai:gpt-4o", result2)

        # Accumulate
        total_cost = cost1 + cost2

        assert total_cost.input_tokens == 3000
        assert total_cost.output_tokens == 1500
        assert total_cost.total_cost_usd == cost1.total_cost_usd + cost2.total_cost_usd
