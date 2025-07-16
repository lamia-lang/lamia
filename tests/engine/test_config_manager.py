import pytest
from unittest.mock import patch
import os
from lamia.engine.config_provider import ConfigProvider
from lamia._internal_types.model_retry import ModelWithRetries
from lamia import LLMModel


class TestConfigProvider:
    """Test suite for ConfigProvider class"""

    def test_init_with_valid_config(self):
        """Test ConfigProvider initialization with valid config"""
        config = {
            "model_chain": [ModelWithRetries(LLMModel("openai"), retries=1)],
            "api_keys": {"openai": "test-key"},
        }
        cm = ConfigProvider(config)
        assert cm.config == config
        assert cm.config["api_keys"]["openai"] == "test-key"

    def test_init_with_empty_config(self):
        """Test ConfigProvider initialization with empty config"""
        config = {}
        cm = ConfigProvider(config)
        assert cm.config == {}

    def test_init_with_invalid_config_type(self):
        """Test ConfigProvider initialization with invalid config type"""
        with pytest.raises(ValueError, match="ConfigProvider expects a config dict"):
            ConfigProvider("not a dict")

    def test_init_preserves_existing_api_keys(self):
        """Test that existing API keys in config are preserved over env vars"""
        config = {
            "api_keys": {"openai": "config-key"}
        }
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            cm = ConfigProvider(config)
            assert cm.config["api_keys"]["openai"] == "config-key"

    def test_from_dict_class_method(self):
        """Test ConfigProvider.from_dict class method"""
        config = {"model_chain": [ModelWithRetries(LLMModel("openai"), retries=1)]}
        cm = ConfigProvider.from_dict(config)
        assert isinstance(cm, ConfigProvider)
        assert cm.config["model_chain"][0].model.name == "openai"

    def test_get_config(self):
        """Test get_config returns the entire configuration"""
        config = {"default_model": "openai", "models": {}}
        cm = ConfigProvider(config)
        returned_config = cm.get_config()
        assert returned_config["default_model"] == "openai"
        assert "api_keys" in returned_config

    def test_get_model_chain(self):
        chain = [
            ModelWithRetries(LLMModel("openai"), retries=2),
            ModelWithRetries(LLMModel("anthropic"), retries=1),
        ]
        cm = ConfigProvider({"model_chain": chain})
        assert cm.get_model_chain() == chain

    def test_get_api_key_exists(self):
        """Test get_api_key returns existing API key"""
        config = {"api_keys": {"openai": "test-key"}}
        cm = ConfigProvider(config)
        
        assert cm.get_api_key("openai") == "test-key"

    def test_get_api_key_missing(self):
        """Test get_api_key returns None for missing API key"""
        config = {"api_keys": {}}
        cm = ConfigProvider(config)
        
        assert cm.get_api_key("openai") is None

    def test_get_api_key_no_api_keys_section(self):
        """Test get_api_key returns None when no api_keys section"""
        config = {}
        cm = ConfigProvider(config)
        
        assert cm.get_api_key("openai") is None

    def test_get_extensions_folder_default(self):
        """Test get_extensions_folder returns default value"""
        config = {}
        cm = ConfigProvider(config)
        
        assert cm.get_extensions_folder() == "extensions"

    def test_get_extensions_folder_custom(self):
        """Test get_extensions_folder returns custom value"""
        config = {"extensions_folder": "custom_extensions"}
        cm = ConfigProvider(config)
        
        assert cm.get_extensions_folder() == "custom_extensions"