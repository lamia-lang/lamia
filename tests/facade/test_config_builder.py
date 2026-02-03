"""Tests for config_builder module."""

import asyncio
from datetime import timedelta
from unittest import mock

import pytest

from lamia import Lamia, LLMModel
from lamia._internal_types.model_retry import ModelWithRetries
from lamia.engine.config_provider import ConfigProvider
from lamia.facade.config_builder import (
    build_config_from_dict,
    build_config_from_models,
    _construct_model_from_config,
)
from lamia.types import ExternalOperationRetryConfig


class TestConstructModelFromConfig:
    """Tests for _construct_model_from_config function."""

    def test_construct_model_with_full_name(self):
        """Test constructing model with provider:model format."""
        config = {}
        model_chain_item = {"name": "openai:gpt-4o"}

        model = _construct_model_from_config(config, model_chain_item)

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

        model = _construct_model_from_config(config, model_chain_item)

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

        model = _construct_model_from_config(config, model_chain_item)

        assert model is None

    def test_construct_model_missing_name_raises(self):
        """Test that missing name raises ValueError."""
        config = {}
        model_chain_item = {}

        with pytest.raises(ValueError, match="must have a name"):
            _construct_model_from_config(config, model_chain_item)

    def test_construct_model_missing_providers_raises(self):
        """Test that missing providers config raises ValueError."""
        config = {}
        model_chain_item = {"name": "openai"}

        with pytest.raises(ValueError, match="Providers are not configured"):
            _construct_model_from_config(config, model_chain_item)

    def test_construct_model_unconfigured_provider_raises(self):
        """Test that unconfigured provider raises ValueError."""
        config = {"providers": {"anthropic": {"enabled": True}}}
        model_chain_item = {"name": "openai"}

        with pytest.raises(ValueError, match="is not configured"):
            _construct_model_from_config(config, model_chain_item)

    def test_construct_model_missing_default_model_raises(self):
        """Test that missing default_model raises ValueError."""
        config = {"providers": {"openai": {"enabled": True}}}
        model_chain_item = {"name": "openai"}

        with pytest.raises(ValueError, match="does not have a default model"):
            _construct_model_from_config(config, model_chain_item)

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

        model = _construct_model_from_config(config, model_chain_item)

        assert model is not None
        assert model.temperature == 0.7
        assert model.max_tokens == 4096
        assert model.top_p == 0.9


class TestBuildConfigFromDict:
    """Tests for build_config_from_dict function."""

    def test_build_config_returns_config_provider(self):
        """Test that build_config_from_dict returns ConfigProvider."""
        config = {"model_chain": [{"name": "openai:gpt-4o"}]}

        result = build_config_from_dict(config)

        assert isinstance(result, ConfigProvider)

    def test_build_config_with_model_chain(self):
        """Test building config with model chain."""
        config = {
            "model_chain": [{"name": "openai:gpt-4o", "max_retries": 2}]
        }

        result = build_config_from_dict(config)
        chain = result.get_model_chain()

        assert len(chain) == 1
        assert chain[0].model.name == "openai:gpt-4o"
        assert chain[0].retries == 2

    def test_build_config_empty_model_chain(self):
        """Test building config with no models."""
        config = {}

        result = build_config_from_dict(config)
        chain = result.get_model_chain()

        assert len(chain) == 0

    def test_build_config_retry_config_defaults(self):
        """Test retry config uses defaults."""
        config = {}

        result = build_config_from_dict(config)
        retry_config = result.get_retry_config()

        assert retry_config is not None
        assert retry_config.max_attempts == 3
        assert retry_config.base_delay == 1.0

    def test_build_config_retry_config_disabled(self):
        """Test retry config when disabled."""
        config = {"retry_config": {"enabled": False}}

        result = build_config_from_dict(config)
        retry_config = result.get_retry_config()

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

        result = build_config_from_dict(config)
        retry_config = result.get_retry_config()

        assert retry_config is not None
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

        result = build_config_from_dict(config)
        chain = result.get_model_chain()

        assert len(chain) == 1
        assert chain[0].model.name == "anthropic:claude-3"

    def test_build_config_with_api_keys(self):
        """Test that api_keys are propagated to ConfigProvider."""
        config = {
            "api_keys": {"openai": "sk-test-key", "anthropic": "sk-ant-key"},
            "model_chain": [{"name": "openai:gpt-4o"}]
        }

        result = build_config_from_dict(config)

        assert result.get_api_key("openai") == "sk-test-key"
        assert result.get_api_key("anthropic") == "sk-ant-key"

    def test_build_config_with_web_config(self):
        """Test that web_config is propagated to ConfigProvider."""
        config = {
            "web_config": {
                "human_in_loop": True,
                "browser_options": {"headless": True}
            }
        }

        result = build_config_from_dict(config)

        assert result.is_human_in_loop_enabled() is True

    def test_build_config_with_all_options(self):
        """Test building config with all config options."""
        config = {
            "model_chain": [{"name": "openai:gpt-4o", "max_retries": 3}],
            "api_keys": {"openai": "sk-test"},
            "retry_config": {"max_attempts": 5},
            "web_config": {"human_in_loop": True}
        }

        result = build_config_from_dict(config)

        # Verify all options are propagated
        chain = result.get_model_chain()
        assert len(chain) == 1
        assert chain[0].model.name == "openai:gpt-4o"
        assert result.get_api_key("openai") == "sk-test"
        retry_config = result.get_retry_config()
        assert retry_config is not None
        assert retry_config.max_attempts == 5
        assert result.is_human_in_loop_enabled() is True


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

        result_retry_config = result.get_retry_config()
        assert result_retry_config is not None
        assert result_retry_config.max_attempts == 5

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
                models=(123,),  # type: ignore[arg-type]
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


class TestLamiaFromConfig:
    """Tests for Lamia.from_config using build_config_from_dict."""

    def test_from_config_creates_lamia_with_all_options(self):
        """Test that from_config passes all config options to engine."""
        config = {
            "model_chain": [{"name": "openai:gpt-4o", "max_retries": 2}],
            "api_keys": {"openai": "sk-test"},
            "retry_config": {"max_attempts": 5},
            "web_config": {"human_in_loop": True}
        }

        with mock.patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_engine = mock.MagicMock()
            MockEngine.return_value = mock_engine

            lamia = Lamia.from_config(config)

            # Verify engine was created with ConfigProvider containing all options
            MockEngine.assert_called_once()
            config_provider = MockEngine.call_args[0][0]
            assert isinstance(config_provider, ConfigProvider)

            # Verify all options are in the config provider
            chain = config_provider.get_model_chain()
            assert len(chain) == 1
            assert chain[0].model.name == "openai:gpt-4o"
            assert chain[0].retries == 2
            assert config_provider.get_api_key("openai") == "sk-test"
            retry_config = config_provider.get_retry_config()
            assert retry_config is not None
            assert retry_config.max_attempts == 5
            assert config_provider.is_human_in_loop_enabled() is True

    def test_from_config_api_keys_not_lost(self):
        """Test that api_keys from config dict are not lost (previous bug)."""
        config = {
            "model_chain": [{"name": "openai:gpt-4o"}],
            "api_keys": {"openai": "sk-from-config", "anthropic": "sk-ant-key"}
        }

        with mock.patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_engine = mock.MagicMock()
            MockEngine.return_value = mock_engine

            Lamia.from_config(config)

            config_provider = MockEngine.call_args[0][0]
            # This would have been None before the fix
            assert config_provider.get_api_key("openai") == "sk-from-config"
            assert config_provider.get_api_key("anthropic") == "sk-ant-key"


class TestLamiaIntegration:
    """Tests for Lamia facade integration."""

    @pytest.mark.integration
    def test_api_key_available_in_config_provider(self):
        """Test API key is available in config provider."""
        api_keys = {"openai": "sk-test"}
        with mock.patch('lamia.facade.lamia.LamiaEngine') as MockEngine:
            mock_engine = mock.MagicMock()
            MockEngine.return_value = mock_engine

            Lamia("openai", api_keys=api_keys)

            # Verify the ConfigProvider was created with the API key
            config_provider = MockEngine.call_args[0][0]
            assert config_provider.get_api_key("openai") == "sk-test"
