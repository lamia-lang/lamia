import pytest
from unittest.mock import patch, MagicMock
import os
from lamia.engine.config_manager import ConfigManager, PROVIDER_REGISTRY


class TestConfigManager:
    """Test suite for ConfigManager class"""

    def test_init_with_valid_config(self):
        """Test ConfigManager initialization with valid config"""
        config = {
            "default_model": "openai",
            "models": {"openai": {"default_model": "gpt-3.5-turbo"}},
            "api_keys": {"openai": "test-key"}
        }
        cm = ConfigManager(config)
        assert cm.config == config
        assert cm.config["api_keys"]["openai"] == "test-key"

    def test_init_with_empty_config(self):
        """Test ConfigManager initialization with empty config"""
        config = {}
        cm = ConfigManager(config)
        assert cm.config == {"api_keys": {}}

    def test_init_with_invalid_config_type(self):
        """Test ConfigManager initialization with invalid config type"""
        with pytest.raises(ValueError, match="ConfigManager expects a config dict"):
            ConfigManager("not a dict")

    def test_init_enriches_api_keys_from_env(self):
        """Test that ConfigManager enriches API keys from environment variables"""
        config = {"default_model": "openai"}
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key", "ANTHROPIC_API_KEY": "env-anthropic-key"}):
            cm = ConfigManager(config)
            assert cm.config["api_keys"]["openai"] == "env-key"
            assert cm.config["api_keys"]["anthropic"] == "env-anthropic-key"

    def test_init_preserves_existing_api_keys(self):
        """Test that existing API keys in config are preserved over env vars"""
        config = {
            "api_keys": {"openai": "config-key"}
        }
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            cm = ConfigManager(config)
            assert cm.config["api_keys"]["openai"] == "config-key"

    def test_from_dict_class_method(self):
        """Test ConfigManager.from_dict class method"""
        config = {"default_model": "openai"}
        cm = ConfigManager.from_dict(config)
        assert isinstance(cm, ConfigManager)
        assert cm.config["default_model"] == "openai"

    def test_is_remote_provider_true(self):
        """Test is_remote_provider returns True for remote providers"""
        assert ConfigManager.is_remote_provider("openai") is True
        assert ConfigManager.is_remote_provider("anthropic") is True
        assert ConfigManager.is_remote_provider("lamia") is True

    def test_is_remote_provider_false(self):
        """Test is_remote_provider returns False for local providers"""
        assert ConfigManager.is_remote_provider("ollama") is False

    def test_is_remote_provider_unknown(self):
        """Test is_remote_provider returns False for unknown providers"""
        assert ConfigManager.is_remote_provider("unknown") is False

    def test_get_env_var_name_valid(self):
        """Test get_env_var_name returns correct env var names"""
        assert ConfigManager.get_env_var_name("openai") == "OPENAI_API_KEY"
        assert ConfigManager.get_env_var_name("anthropic") == "ANTHROPIC_API_KEY"
        assert ConfigManager.get_env_var_name("lamia") == "LAMIA_API_KEY"

    def test_get_env_var_name_ollama(self):
        """Test get_env_var_name returns None for ollama"""
        assert ConfigManager.get_env_var_name("ollama") is None

    def test_get_env_var_name_unknown(self):
        """Test get_env_var_name returns None for unknown providers"""
        assert ConfigManager.get_env_var_name("unknown") is None

    def test_get_config(self):
        """Test get_config returns the entire configuration"""
        config = {"default_model": "openai", "models": {}}
        cm = ConfigManager(config)
        returned_config = cm.get_config()
        assert returned_config["default_model"] == "openai"
        assert "api_keys" in returned_config

    def test_get_model_config_valid(self):
        """Test get_model_config returns correct model configuration"""
        config = {
            "models": {
                "openai": {"default_model": "gpt-3.5-turbo", "temperature": 0.7},
                "anthropic": {"default_model": "claude-3-opus-20240229"}
            }
        }
        cm = ConfigManager(config)
        
        openai_config = cm.get_model_config("openai")
        assert openai_config["default_model"] == "gpt-3.5-turbo"
        assert openai_config["temperature"] == 0.7

    def test_get_model_config_missing(self):
        """Test get_model_config raises error for missing model"""
        config = {"models": {}}
        cm = ConfigManager(config)
        
        with pytest.raises(ValueError, match="Configuration for model 'nonexistent' not found"):
            cm.get_model_config("nonexistent")

    def test_get_model_config_no_models_section(self):
        """Test get_model_config when no models section exists"""
        config = {}
        cm = ConfigManager(config)
        
        with pytest.raises(ValueError, match="Configuration for model 'openai' not found"):
            cm.get_model_config("openai")

    def test_get_validation_config(self):
        """Test get_validation_config returns validation settings"""
        config = {
            "validation": {
                "enabled": True,
                "max_retries": 3,
                "validators": ["html"]
            }
        }
        cm = ConfigManager(config)
        
        validation_config = cm.get_validation_config()
        assert validation_config["enabled"] is True
        assert validation_config["max_retries"] == 3
        assert validation_config["validators"] == ["html"]

    def test_get_validation_config_empty(self):
        """Test get_validation_config returns empty dict when no validation config"""
        config = {}
        cm = ConfigManager(config)
        
        validation_config = cm.get_validation_config()
        assert validation_config == {}

    def test_get_default_model(self):
        """Test get_default_model returns default model"""
        config = {"default_model": "anthropic"}
        cm = ConfigManager(config)
        
        assert cm.get_default_model() == "anthropic"

    def test_get_default_model_none(self):
        """Test get_default_model returns None when not set"""
        config = {}
        cm = ConfigManager(config)
        
        assert cm.get_default_model() is None

    def test_get_has_context_memory_with_dict_entry(self):
        """Test get_has_context_memory with dictionary model entry"""
        config = {
            "models": {
                "openai": {
                    "models": [
                        {"name": "gpt-4", "has_context_memory": True},
                        {"name": "gpt-3.5-turbo", "has_context_memory": False}
                    ]
                }
            }
        }
        cm = ConfigManager(config)
        
        assert cm.get_has_context_memory("openai", "gpt-4") is True
        assert cm.get_has_context_memory("openai", "gpt-3.5-turbo") is False

    def test_get_has_context_memory_with_string_entry(self):
        """Test get_has_context_memory with string model entry"""
        config = {
            "models": {
                "openai": {
                    "models": ["gpt-4", "gpt-3.5-turbo"]
                }
            }
        }
        cm = ConfigManager(config)
        
        assert cm.get_has_context_memory("openai", "gpt-4") is None
        assert cm.get_has_context_memory("openai", "gpt-3.5-turbo") is None

    def test_get_has_context_memory_model_not_found(self):
        """Test get_has_context_memory returns None for non-existent model"""
        config = {
            "models": {
                "openai": {
                    "models": [{"name": "gpt-4", "has_context_memory": True}]
                }
            }
        }
        cm = ConfigManager(config)
        
        assert cm.get_has_context_memory("openai", "nonexistent") is None

    def test_get_has_context_memory_provider_not_found(self):
        """Test get_has_context_memory returns None for non-existent provider"""
        config = {"models": {}}
        cm = ConfigManager(config)
        
        assert cm.get_has_context_memory("nonexistent", "gpt-4") is None

    def test_get_api_key_exists(self):
        """Test get_api_key returns existing API key"""
        config = {"api_keys": {"openai": "test-key"}}
        cm = ConfigManager(config)
        
        assert cm.get_api_key("openai") == "test-key"

    def test_get_api_key_missing(self):
        """Test get_api_key returns None for missing API key"""
        config = {"api_keys": {}}
        cm = ConfigManager(config)
        
        assert cm.get_api_key("openai") is None

    def test_get_api_key_no_api_keys_section(self):
        """Test get_api_key returns None when no api_keys section"""
        config = {}
        cm = ConfigManager(config)
        
        assert cm.get_api_key("openai") is None

    def test_get_extensions_folder_default(self):
        """Test get_extensions_folder returns default value"""
        config = {}
        cm = ConfigManager(config)
        
        assert cm.get_extensions_folder() == "extensions"

    def test_get_extensions_folder_custom(self):
        """Test get_extensions_folder returns custom value"""
        config = {"extensions_folder": "custom_extensions"}
        cm = ConfigManager(config)
        
        assert cm.get_extensions_folder() == "custom_extensions"


class TestProviderRegistry:
    """Test suite for PROVIDER_REGISTRY constant"""

    def test_provider_registry_structure(self):
        """Test that PROVIDER_REGISTRY has correct structure"""
        assert isinstance(PROVIDER_REGISTRY, dict)
        
        for provider, config in PROVIDER_REGISTRY.items():
            assert isinstance(provider, str)
            assert isinstance(config, dict)
            assert "is_remote" in config
            assert "env_var" in config
            assert isinstance(config["is_remote"], bool)
            assert config["env_var"] is None or isinstance(config["env_var"], str)

    def test_provider_registry_known_providers(self):
        """Test that known providers are in registry"""
        assert "openai" in PROVIDER_REGISTRY
        assert "anthropic" in PROVIDER_REGISTRY
        assert "lamia" in PROVIDER_REGISTRY
        assert "ollama" in PROVIDER_REGISTRY

    def test_provider_registry_remote_flags(self):
        """Test that remote flags are correct"""
        assert PROVIDER_REGISTRY["openai"]["is_remote"] is True
        assert PROVIDER_REGISTRY["anthropic"]["is_remote"] is True
        assert PROVIDER_REGISTRY["lamia"]["is_remote"] is True
        assert PROVIDER_REGISTRY["ollama"]["is_remote"] is False

    def test_provider_registry_env_vars(self):
        """Test that env vars are correct"""
        assert PROVIDER_REGISTRY["openai"]["env_var"] == "OPENAI_API_KEY"
        assert PROVIDER_REGISTRY["anthropic"]["env_var"] == "ANTHROPIC_API_KEY"
        assert PROVIDER_REGISTRY["lamia"]["env_var"] == "LAMIA_API_KEY"
        assert PROVIDER_REGISTRY["ollama"]["env_var"] is None 