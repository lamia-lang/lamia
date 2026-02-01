"""Tests for config_builder module."""

import asyncio
from datetime import timedelta
from unittest import mock

import pytest

from lamia import Lamia, LLMModel
from lamia._internal_types.model_retry import ModelWithRetries
from lamia.adapters.llm.openai_adapter import OpenAIAdapter
from lamia.engine.config_provider import ConfigProvider
from lamia.facade.config_builder import (
    build_config_from_dict,
    build_config_from_models,
    construct_model,
)
from lamia.types import ExternalOperationRetryConfig


class TestConstructModel:
    """Tests for construct_model function."""

    def test_construct_model_with_full_name(self):
        """Test constructing model with provider:model format."""
        config = {}
        model_chain_item = {"name": "openai:gpt-4o"}

        model = construct_model(config, model_chain_item)

        assert model is not None
        assert model.name == "openai:gpt-4o"

    def test_construct_model_with_provider_name_and_default(self):
        """Test constructing model with provider name using default model."""
        config = {
            "providers": {
                "openai": {
                    "enabled": True,
                    "default_model": "gpt-4o"
                }
            }
        }
        model_chain_item = {"name": "openai"}

        model = construct_model(config, model_chain_item)

        assert model is not None
        assert model.name == "openai:gpt-4o"

    def test_construct_model_disabled_provider_returns_none(self):
        """Test that disabled provider returns None."""
        config = {
            "providers": {
                "openai": {
                    "enabled": False,
                    "default_model": "gpt-4o"
                }
            }
        }
        model_chain_item = {"name": "openai"}

        model = construct_model(config, model_chain_item)

        assert model is None

    def test_construct_model_missing_name_raises(self):
        """Test that missing name raises ValueError."""
        config = {}
        model_chain_item = {}

        with pytest.raises(ValueError, match="must have a name"):
            construct_model(config, model_chain_item)

    def test_construct_model_missing_providers_raises(self):
        """Test that missing providers config raises ValueError."""
        config = {}
        model_chain_item = {"name": "openai"}

        with pytest.raises(ValueError, match="Providers are not configured"):
            construct_model(config, model_chain_item)

    def test_construct_model_unconfigured_provider_raises(self):
        """Test that unconfigured provider raises ValueError."""
        config = {"providers": {"anthropic": {"enabled": True}}}
        model_chain_item = {"name": "openai"}

        with pytest.raises(ValueError, match="is not configured"):
            construct_model(config, model_chain_item)

    def test_construct_model_missing_default_model_raises(self):
        """Test that missing default_model raises ValueError."""
        config = {"providers": {"openai": {"enabled": True}}}
        model_chain_item = {"name": "openai"}

        with pytest.raises(ValueError, match="does not have a default model"):
            construct_model(config, model_chain_item)

    def test_construct_model_inherits_parameters(self):
        """Test that model inherits parameters from provider and model settings."""
        config = {
            "providers": {
                "openai": {
                    "enabled": True,
                    "default_model": "gpt-4o",
                    "temperature": 0.7,
                    "gpt-4o": {
                        "max_tokens": 4096
                    }
                }
            }
        }
        model_chain_item = {"name": "openai", "top_p": 0.9}

        model = construct_model(config, model_chain_item)

        assert model.temperature == 0.7
        assert model.max_tokens == 4096
        assert model.top_p == 0.9


class TestBuildConfigFromDict:
    """Tests for build_config_from_dict function."""

    def test_build_config_with_model_chain(self):
        """Test building config with model chain."""
        config = {
            "model_chain": [{"name": "openai:gpt-4o"}]
        }

        models, retry_config = build_config_from_dict(config)

        assert len(models) == 1
        assert models[0].name == "openai:gpt-4o"

    def test_build_config_empty_model_chain(self):
        """Test building config with no models."""
        config = {}

        models, retry_config = build_config_from_dict(config)

        assert len(models) == 0

    def test_build_config_retry_config_defaults(self):
        """Test retry config uses defaults."""
        config = {}

        models, retry_config = build_config_from_dict(config)

        assert retry_config is not None
        assert retry_config.max_attempts == 3
        assert retry_config.base_delay == 1.0

    def test_build_config_retry_config_disabled(self):
        """Test retry config when disabled."""
        config = {"retry_config": {"enabled": False}}

        models, retry_config = build_config_from_dict(config)

        assert retry_config is None

    def test_build_config_retry_config_custom(self):
        """Test retry config with custom values."""
        config = {
            "retry_config": {
                "max_attempts": 5,
                "base_delay": 2.0,
                "max_delay": 120.0,
                "exponential_base": 3.0,
                "max_total_duration": 300
            }
        }

        models, retry_config = build_config_from_dict(config)

        assert retry_config.max_attempts == 5
        assert retry_config.base_delay == 2.0
        assert retry_config.max_delay == 120.0
        assert retry_config.exponential_base == 3.0
        assert retry_config.max_total_duration == timedelta(seconds=300)

    def test_build_config_skips_disabled_providers(self):
        """Test that disabled providers are skipped gracefully."""
        config = {
            "providers": {
                "openai": {"enabled": False, "default_model": "gpt-4o"},
                "anthropic": {"enabled": True, "default_model": "claude-3"}
            },
            "model_chain": [
                {"name": "openai"},
                {"name": "anthropic"}
            ]
        }

        models, retry_config = build_config_from_dict(config)

        assert len(models) == 1
        assert models[0].name == "anthropic:claude-3"


class TestBuildConfigFromModels:
    """Tests for build_config_from_models function."""

    def test_build_config_from_string_model(self):
        """Test building config from string model name."""
        result = build_config_from_models(
            models=("openai:gpt-4o",),
            api_keys=None,
            retry_config=None,
            web_config=None
        )

        assert isinstance(result, ConfigProvider)
        chain = result.get_model_chain()
        assert len(chain) == 1
        assert chain[0].model.name == "openai:gpt-4o"
        assert chain[0].retries == 1

    def test_build_config_from_llm_model(self):
        """Test building config from LLMModel instance."""
        model = LLMModel(name="openai:gpt-4o", temperature=0.5)
        result = build_config_from_models(
            models=(model,),
            api_keys=None,
            retry_config=None,
            web_config=None
        )

        chain = result.get_model_chain()
        assert chain[0].model.temperature == 0.5

    def test_build_config_from_tuple_with_retries(self):
        """Test building config from tuple with custom retries."""
        result = build_config_from_models(
            models=(("openai:gpt-4o", 3),),
            api_keys=None,
            retry_config=None,
            web_config=None
        )

        chain = result.get_model_chain()
        assert chain[0].retries == 3

    def test_build_config_default_to_ollama(self):
        """Test that empty models defaults to ollama."""
        result = build_config_from_models(
            models=(),
            api_keys=None,
            retry_config=None,
            web_config=None
        )

        chain = result.get_model_chain()
        assert len(chain) == 1
        assert chain[0].model.name == "ollama"

    def test_build_config_with_api_keys(self):
        """Test building config with API keys."""
        api_keys = {"openai": "sk-test"}
        result = build_config_from_models(
            models=("openai",),
            api_keys=api_keys,
            retry_config=None,
            web_config=None
        )

        assert result.get_api_key("openai") == "sk-test"

    def test_build_config_with_retry_config(self):
        """Test building config with retry config."""
        retry_config = ExternalOperationRetryConfig(
            max_attempts=5,
            base_delay=1.0,
            max_delay=60.0,
            exponential_base=2.0,
            max_total_duration=None
        )
        result = build_config_from_models(
            models=("openai",),
            api_keys=None,
            retry_config=retry_config,
            web_config=None
        )

        assert result.get_retry_config().max_attempts == 5

    def test_build_config_with_web_config(self):
        """Test building config with web config."""
        web_config = {"human_in_loop": True}
        result = build_config_from_models(
            models=("openai",),
            api_keys=None,
            retry_config=None,
            web_config=web_config
        )

        assert result.is_human_in_loop_enabled() is True

    def test_build_config_invalid_model_type_raises(self):
        """Test that invalid model type raises TypeError."""
        with pytest.raises(TypeError, match="Each model spec must be"):
            build_config_from_models(
                models=(123,),
                api_keys=None,
                retry_config=None,
                web_config=None
            )

    def test_build_config_multiple_models(self):
        """Test building config with multiple models."""
        result = build_config_from_models(
            models=("openai:gpt-4o", ("anthropic:claude-3", 2)),
            api_keys=None,
            retry_config=None,
            web_config=None
        )

        chain = result.get_model_chain()
        assert len(chain) == 2
        assert chain[0].model.name == "openai:gpt-4o"
        assert chain[0].retries == 1
        assert chain[1].model.name == "anthropic:claude-3"
        assert chain[1].retries == 2


class TestLamiaIntegration:
    """Tests for Lamia facade integration."""

    @pytest.mark.integration
    def test_api_key_propagated_to_adapter(self):
        """Test API key is propagated to adapter."""
        api_keys = {"openai": "sk-test"}
        with mock.patch.object(OpenAIAdapter, "__init__", return_value=None) as mocked_init:
            lamia = Lamia("openai", api_keys=api_keys)
            asyncio.run(lamia._engine.start())

            mocked_init.assert_called_once_with(api_key="sk-test", model=mock.ANY)
