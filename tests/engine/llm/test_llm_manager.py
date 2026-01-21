import pytest
from unittest.mock import patch, MagicMock, mock_open
import os
import subprocess
import requests
import sys
from pathlib import Path
import importlib.util

from lamia.engine.managers.llm.llm_manager import (
    MissingAPIKeysError,
    LLMManager
)
from lamia.engine.config_provider import ConfigProvider
from lamia.adapters.llm.local import OllamaAdapter


class TestLLMManager:
    """Test suite for LLMManager"""

    def test_check_api_keys_direct(self):
        """Test check_api_key with direct OpenAI API key"""
        config = {"api_keys": {"openai": "test-openai-key", "anthropic": "test-anthropic-key"}}
        cm = ConfigProvider(config)
        
        manager = LLMManager(cm)
        assert manager._resolve_api_key("openai") == ("test-openai-key", False)
        assert manager._resolve_api_key("anthropic") == ("test-anthropic-key", False)

    def test_check_api_key_direct_does_not_override_lamia_proxy(self):
        """Test lamia proxy API key takes precedence over direct provider key"""
        config = {"api_keys": {"openai": "direct-key", "lamia": "proxy-key"}}
        cm = ConfigProvider(config)
        
        manager = LLMManager(cm)
        result = manager._resolve_api_key("openai")
        assert result == ("proxy-key", True)

    def test_check_api_key_env_fallback(self):
        """Test check_api_key falls back to environment variable"""
        config = {"api_keys": {}}
        cm = ConfigProvider(config)
        
        manager = LLMManager(cm)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            result = manager._resolve_api_key("openai")
            assert result == ("env-key", False)

    def test_check_api_key_missing_raises_error(self):
        """Test check_api_key raises MissingAPIKeysError when key is missing"""
        config = {"api_keys": {}}
        cm = ConfigProvider(config)
        
        manager = LLMManager(cm)
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(MissingAPIKeysError) as exc_info:
                manager._resolve_api_key("openai")
            
            assert "openai" in str(exc_info.value)
            assert "OPENAI_API_KEY" in str(exc_info.value)

    def test_check_api_key_unknown_provider(self):
        """Test check_api_key with unknown provider"""
        config = {"":"", "api_keys": {}}
        cm = ConfigProvider(config)
        
        manager = LLMManager(cm)
        with pytest.raises(MissingAPIKeysError) as exc_info:
            manager._resolve_api_key("unknown")

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
        cm = ConfigProvider(config)
        
        manager = LLMManager(cm)
        # Should not raise any exception
        manager._check_all_required_api_keys({"openai", "anthropic"})

    def test_check_all_required_api_keys_lamia_proxy(self):
        """Test check_all_required_api_keys with lamia key as proxy"""
        config = {
            "default_model": "openai",
            "validation": {"fallback_models": ["anthropic"]},
            "api_keys": {"lamia": "proxy-key"}
        }
        cm = ConfigProvider(config)
        
        manager = LLMManager(cm)
        # Should not raise any exception
        manager._check_all_required_api_keys({"openai", "anthropic"})

    def test_check_all_required_api_keys_ollama_no_key_needed(self):
        """Test check_all_required_api_keys with ollama (no key needed)"""
        config = {
            "default_model": "ollama",
            "validation": {"fallback_models": []},
            "api_keys": {}
        }
        cm = ConfigProvider(config)
        
        manager = LLMManager(cm)
        # Should not raise any exception
        manager._check_all_required_api_keys({"ollama"})

    def test_check_all_required_api_keys_missing_default(self):
        """Test check_all_required_api_keys with missing default model key"""
        config = {
            "default_model": "openai",
            "validation": {"fallback_models": []},
            "api_keys": {}
        }
        cm = ConfigProvider(config)
        
        manager = LLMManager(cm)
        with pytest.raises(MissingAPIKeysError) as exc_info:
            manager._check_all_required_api_keys({"openai"})
        
        assert "openai" in str(exc_info.value)

    def test_check_all_required_api_keys_missing_fallback(self):
        """Test check_all_required_api_keys with missing fallback model key"""
        config = {
            "default_model": "openai",
            "validation": {"fallback_models": ["anthropic"]},
            "api_keys": {"openai": "key1"}
        }
        cm = ConfigProvider(config)
        
        manager = LLMManager(cm)
        with pytest.raises(MissingAPIKeysError) as exc_info:
            manager._check_all_required_api_keys({"anthropic"})
        
        assert "anthropic" in str(exc_info.value)

    def test_check_all_required_api_keys_no_validation_config(self):
        """Test check_all_required_api_keys with no validation config"""
        config = {
            "default_model": "openai",
            "api_keys": {"openai": "key1"}
        }
        cm = ConfigProvider(config)
        
        manager = LLMManager(cm)
        # Should not raise any exception
        manager._check_all_required_api_keys({"openai"})


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
        cm = ConfigProvider(config)
        
        with patch('lamia.engine.llm.providers.OpenAIAdapter') as MockAdapter:
            manager = LLMManager(cm)
            result = manager.create_adapter_from_config()
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
        cm = ConfigProvider(config)
        
        with patch('lamia.engine.llm.providers.AnthropicAdapter') as MockAdapter:
            manager = LLMManager(cm)
            result = manager.create_adapter_from_config()
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
        cm = ConfigProvider(config)
        
        manager = LLMManager(cm)
        result = manager.create_adapter_from_config()
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
        cm = ConfigProvider(config)
        
        with patch('lamia.engine.llm.providers.AnthropicAdapter') as MockAdapter:
            manager = LLMManager(cm)
            result = manager.create_adapter_from_config(override_model="anthropic")
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
        cm = ConfigProvider(config)
        
        manager = LLMManager(cm)
        result = manager.create_adapter_from_config()
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
        cm = ConfigProvider(config)
        
        manager = LLMManager(cm)
        with pytest.raises(ValueError, match="Unknown provider: unsupported"):
            manager.create_adapter_from_config()

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
        cm = ConfigProvider(config)
        
        manager = LLMManager(cm)
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(MissingAPIKeysError):
                manager.create_adapter_from_config()

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
        cm = ConfigProvider(config)
        manager = LLMManager(cm)
        with patch("lamia.engine.llm.llm_manager.LamiaAdapter", autospec=True) as MockAdapter:
            manager.create_adapter_from_config()
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
        cm = ConfigProvider(config)
        manager = LLMManager(cm)
        adapter = manager.create_adapter_from_config()
        assert isinstance(adapter, OllamaAdapter)
        assert adapter.base_url == "http://localhost:11434"
        assert adapter.temperature == 0.7
        assert adapter.max_tokens == 1000 
