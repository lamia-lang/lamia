import pytest
from unittest.mock import patch, MagicMock, mock_open
import os
import subprocess
import requests
import sys
from pathlib import Path
import importlib.util

from lamia.engine.llm.llm_manager import (
    check_api_key,
    check_all_required_api_keys,
    create_adapter_from_config,
    MissingAPIKeysError
)
from lamia.engine.config_manager import ConfigManager
from lamia.adapters.llm.openai_adapter import OpenAIAdapter
from lamia.adapters.llm.anthropic_adapter import AnthropicAdapter
from lamia.adapters.llm.local import OllamaAdapter


class TestCheckApiKey:
    """Test suite for check_api_key function"""

    def test_check_api_keys_direct(self):
        """Test check_api_key with direct OpenAI API key"""
        config = {"api_keys": {"openai": "test-openai-key", "anthropic": "test-anthropic-key"}}
        cm = ConfigManager(config)
        
        assert check_api_key("openai", cm) == "test-openai-key"
        assert check_api_key("anthropic", cm) == "test-anthropic-key"

    def test_check_api_key_direct_overrides_lamia_proxy(self):
        """Test lamia proxy API key takes precedence over direct provider key"""
        config = {"api_keys": {"openai": "direct-key", "lamia": "proxy-key"}}
        cm = ConfigManager(config)
        
        result = check_api_key("openai", cm)
        assert result == "direct-key"

    def test_check_api_key_env_fallback(self):
        """Test check_api_key falls back to environment variable"""
        config = {"api_keys": {}}
        cm = ConfigManager(config)
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            result = check_api_key("openai", cm)
            assert result == "env-key"

    def test_check_api_key_missing_raises_error(self):
        """Test check_api_key raises MissingAPIKeysError when key is missing"""
        config = {"api_keys": {}}
        cm = ConfigManager(config)
        
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(MissingAPIKeysError) as exc_info:
                check_api_key("openai", cm)
            
            assert "openai" in str(exc_info.value)
            assert "OPENAI_API_KEY" in str(exc_info.value)

    def test_check_api_key_unknown_provider(self):
        """Test check_api_key with unknown provider"""
        config = {"api_keys": {}}
        cm = ConfigManager(config)
        
        with pytest.raises(MissingAPIKeysError) as exc_info:
            check_api_key("unknown", cm)

        assert "unknown" in str(exc_info.value)

    def test_missing_api_keys_error_message_single(self):
        """Test MissingAPIKeysError with single missing key"""
        missing = [("openai", "OPENAI_API_KEY")]
        error = MissingAPIKeysError(missing)

        assert "openai" in str(error)
        assert "OPENAI_API_KEY" in str(error)
        assert error.missing == missing

    def test_missing_api_keys_error_message_multiple(self):
        """Test MissingAPIKeysError with multiple missing keys"""
        missing = [("openai", "OPENAI_API_KEY"), ("anthropic", "ANTHROPIC_API_KEY")]
        error = MissingAPIKeysError(missing)

        assert "openai" in str(error)
        assert "anthropic" in str(error)
        assert "OPENAI_API_KEY" in str(error)
        assert "ANTHROPIC_API_KEY" in str(error)

class TestCheckAllRequiredApiKeys:
    """Test suite for check_all_required_api_keys function"""

    def test_check_all_required_api_keys_success(self):
        """Test check_all_required_api_keys with all keys present"""
        config = {
            "default_model": "openai",
            "validation": {"fallback_models": ["anthropic"]},
            "api_keys": {"openai": "key1", "anthropic": "key2"}
        }
        cm = ConfigManager(config)
        
        # Should not raise any exception
        check_all_required_api_keys(cm)

    def test_check_all_required_api_keys_lamia_proxy(self):
        """Test check_all_required_api_keys with lamia key as proxy"""
        config = {
            "default_model": "openai",
            "validation": {"fallback_models": ["anthropic"]},
            "api_keys": {"lamia": "proxy-key"}
        }
        cm = ConfigManager(config)
        
        # Should not raise any exception
        check_all_required_api_keys(cm)

    def test_check_all_required_api_keys_ollama_no_key_needed(self):
        """Test check_all_required_api_keys with ollama (no key needed)"""
        config = {
            "default_model": "ollama",
            "validation": {"fallback_models": []},
            "api_keys": {}
        }
        cm = ConfigManager(config)
        
        # Should not raise any exception
        check_all_required_api_keys(cm)

    def test_check_all_required_api_keys_missing_default(self):
        """Test check_all_required_api_keys with missing default model key"""
        config = {
            "default_model": "openai",
            "validation": {"fallback_models": []},
            "api_keys": {}
        }
        cm = ConfigManager(config)
        
        with pytest.raises(MissingAPIKeysError) as exc_info:
            check_all_required_api_keys(cm)
        
        assert "openai" in str(exc_info.value)

    def test_check_all_required_api_keys_missing_fallback(self):
        """Test check_all_required_api_keys with missing fallback model key"""
        config = {
            "default_model": "openai",
            "validation": {"fallback_models": ["anthropic"]},
            "api_keys": {"openai": "key1"}
        }
        cm = ConfigManager(config)
        
        with pytest.raises(MissingAPIKeysError) as exc_info:
            check_all_required_api_keys(cm)
        
        assert "anthropic" in str(exc_info.value)

    def test_check_all_required_api_keys_no_validation_config(self):
        """Test check_all_required_api_keys with no validation config"""
        config = {
            "default_model": "openai",
            "api_keys": {"openai": "key1"}
        }
        cm = ConfigManager(config)
        
        # Should not raise any exception
        check_all_required_api_keys(cm)


class TestCreateAdapterFromConfig:
    """Test suite for create_adapter_from_config function"""

    def test_create_adapter_from_config_openai(self):
        """Test create_adapter_from_config with OpenAI"""
        config = {
            "default_model": "openai",
            "models": {
                "openai": {"default_model": "gpt-3.5-turbo"}
            },
            "api_keys": {"openai": "test-key"},
            "validation": {"fallback_models": []}
        }
        cm = ConfigManager(config)
        
        with patch('lamia.engine.llm_manager.OpenAIAdapter') as MockAdapter:
            result = create_adapter_from_config(cm)
            MockAdapter.assert_called_once_with(
                api_key="test-key",
                model="gpt-3.5-turbo"
            )

    def test_create_adapter_from_config_anthropic(self):
        """Test create_adapter_from_config with Anthropic"""
        config = {
            "default_model": "anthropic",
            "models": {
                "anthropic": {"default_model": "claude-3-opus-20240229"}
            },
            "api_keys": {"anthropic": "test-key"},
            "validation": {"fallback_models": []}
        }
        cm = ConfigManager(config)
        
        with patch('lamia.engine.llm_manager.AnthropicAdapter') as MockAdapter:
            result = create_adapter_from_config(cm)
            MockAdapter.assert_called_once_with(
                api_key="test-key",
                model="claude-3-opus-20240229"
            )

    def test_create_adapter_from_config_ollama(self):
        """Test create_adapter_from_config with Ollama"""
        config = {
            "default_model": "ollama",
            "models": {
                "ollama": {"default_model": "llama2"}
            },
            "validation": {"fallback_models": []}
        }
        cm = ConfigManager(config)
        
        result = create_adapter_from_config(cm)
        assert isinstance(result, OllamaAdapter)
        assert result.model == "llama2"

    def test_create_adapter_from_config_with_override(self):
        """Test create_adapter_from_config with model override"""
        config = {
            "default_model": "openai",
            "models": {
                "openai": {"default_model": "gpt-3.5-turbo"},
                "anthropic": {"default_model": "claude-3-opus-20240229"}
            },
            "api_keys": {"openai": "key1", "anthropic": "key2"},
            "validation": {"fallback_models": []}
        }
        cm = ConfigManager(config)
        
        with patch('lamia.engine.llm_manager.AnthropicAdapter') as MockAdapter:
            result = create_adapter_from_config(cm, override_model="anthropic")
            MockAdapter.assert_called_once_with(
                api_key="key2",
                model="claude-3-opus-20240229"
            )

    def test_create_adapter_from_config_has_context_memory(self):
        """Test create_adapter_from_config with has_context_memory setting"""
        config = {
            "default_model": "ollama",
            "models": {
                "ollama": {
                    "default_model": "llama2",
                    "models": [{"name": "llama2", "has_context_memory": True}]
                }
            },
            "validation": {"fallback_models": []}
        }
        cm = ConfigManager(config)
        
        result = create_adapter_from_config(cm)
        assert isinstance(result, OllamaAdapter)
        assert result.has_context_memory is True

    def test_create_adapter_from_config_unsupported_model(self):
        """Test create_adapter_from_config with unsupported model"""
        config = {
            "default_model": "unsupported",
            "models": {
                "unsupported": {"default_model": "some-model"}
            },
            "validation": {"fallback_models": []}
        }
        cm = ConfigManager(config)
        
        with pytest.raises(ValueError, match="Unsupported model type: unsupported"):
            create_adapter_from_config(cm)

    def test_create_adapter_from_config_missing_api_key(self):
        """Test create_adapter_from_config with missing API key"""
        config = {
            "default_model": "openai",
            "models": {
                "openai": {"default_model": "gpt-3.5-turbo"}
            },
            "api_keys": {},
            "validation": {"fallback_models": []}
        }
        cm = ConfigManager(config)
        
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(MissingAPIKeysError):
                create_adapter_from_config(cm)

    def test_create_adapter_from_config_extension_adapter_conflict(self):
        """Test create_adapter_from_config with extension adapter name conflict"""
        config = {
            "default_model": "openai",
            "models": {
                "openai": {"default_model": "gpt-3.5-turbo"}
            },
            "api_keys": {"openai": "key"},
            "validation": {"fallback_models": []}
        }
        cm = ConfigManager(config)
        
        with patch('lamia.engine.llm_manager._discover_adapters_in_path') as mock_discover:
            mock_discover.return_value = {"openai": MagicMock}  # Conflict with built-in
            
            with pytest.raises(RuntimeError, match="User-defined adapter name.*conflict.*openai"):
                create_adapter_from_config(cm)

        """Additional tests for create_adapter_from_config covering environment variable fallbacks and extended config options."""

    def test_lamia_api_key_from_env(self, monkeypatch):
        config = {
            "default_model": "openai",
            "models": {
                "openai": {"default_model": "gpt-3.5-turbo"}
            },
            # No api_keys provided
            "validation": {"fallback_models": []}
        }
        monkeypatch.setenv("LAMIA_API_KEY", "env-lamia-key")
        cm = ConfigManager(config)
        with patch("lamia.engine.llm_manager.OpenAIAdapter", autospec=True) as MockAdapter:
            create_adapter_from_config(cm)
            # The adapter should have been created using the proxy key from the env variable
            MockAdapter.assert_called()
        monkeypatch.delenv("LAMIA_API_KEY", raising=False)

    def test_ollama_adapter_extended_config(self):
        config = {
            "default_model": "ollama",
            "models": {
                "ollama": {
                    "default_model": "llama2",
                    "base_url": "http://localhost:11434",
                    "temperature": 0.7,
                    "max_tokens": 1000,
                    "context_size": 4096,
                    "num_ctx": 4096,
                    "num_gpu": 50,
                    "num_thread": 8,
                    "repeat_penalty": 1.1,
                    "top_k": 40,
                    "top_p": 0.9
                }
            },
            "validation": {"fallback_models": []}
        }
        cm = ConfigManager(config)
        adapter = create_adapter_from_config(cm)
        assert isinstance(adapter, OllamaAdapter)
        assert adapter.base_url == "http://localhost:11434"
        assert adapter.temperature == 0.7
        assert adapter.max_tokens == 1000 
