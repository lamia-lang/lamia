import pytest
from unittest.mock import patch
import os
from lamia.engine.llm_manager import (
    create_adapter_from_config, 
    MissingAPIKeysError,
)
from lamia.engine.config_manager import ConfigManager
from lamia.adapters.llm.openai_adapter import OpenAIAdapter
from lamia.adapters.llm.anthropic_adapter import AnthropicAdapter
from lamia.adapters.llm.local import OllamaAdapter

def test_create_ollama_adapter():
    config = {
        "default_model": "ollama",
        "models": {
            "ollama": {"default_model": "llama2",
                        "base_url": "http://localhost:11434",
                        "temperature": 0.7,
                        "max_tokens": 1000,
                        "context_size": 4096,
                        "num_ctx": 4096,
                        "num_gpu": 50,
                        "num_thread": 8,
                        "repeat_penalty": 1.1,
                        "top_k": 40,
                        "top_p": 0.9}
        },
        "validation": {"fallback_models": []}
    }
    cm = ConfigManager.from_dict(config)
    adapter = create_adapter_from_config(cm)
    assert isinstance(adapter, OllamaAdapter)
    assert adapter.model == "llama2"
    assert adapter.base_url == "http://localhost:11434"

def test_create_openai_adapter():
    config = {
        "default_model": "openai",
        "models": {
            "openai": {"default_model": "gpt-3.5-turbo",
                        "api_key": "test-key",
                        "temperature": 0.7,
                        "max_tokens": 1000}
        },
        "api_keys": {"openai": "test-key"},
        "validation": {"fallback_models": []}
    }
    cm = ConfigManager.from_dict(config)
    with patch("lamia.engine.llm_manager.OpenAIAdapter", autospec=True) as MockAdapter:
        adapter = create_adapter_from_config(cm)
        assert MockAdapter.called

def test_create_anthropic_adapter():
    config = {
        "default_model": "anthropic",
        "models": {
            "anthropic": {"default_model": "claude-3-opus-20240229",
                           "api_key": "test-key",
                           "temperature": 0.7,
                           "max_tokens": 1000}
        },
        "api_keys": {"anthropic": "test-key"},
        "validation": {"fallback_models": []}
    }
    cm = ConfigManager.from_dict(config)
    with patch("lamia.engine.llm_manager.AnthropicAdapter", autospec=True) as MockAdapter:
        adapter = create_adapter_from_config(cm)
        assert MockAdapter.called

def test_unsupported_model():
    config = {
        "default_model": "unsupported",
        "models": {"unsupported": {"default_model": "foo"}},
        "validation": {"fallback_models": []}
    }
    cm = ConfigManager.from_dict(config)
    with pytest.raises(ValueError, match="Unsupported model type: unsupported"):
        create_adapter_from_config(cm)

def test_create_openai_adapter_throws_on_missing_key():
    config = {
        "default_model": "openai",
        "models": {
            "openai": {"default_model": "gpt-3.5-turbo",
                        "temperature": 0.7,
                        "max_tokens": 1000}
        },
        # No api_keys
        "validation": {"fallback_models": []}
    }
    cm = ConfigManager.from_dict(config)
    with patch.dict(os.environ, {}, clear=True), \
         patch("lamia.engine.llm_manager.OpenAIAdapter", autospec=True):
        with pytest.raises(MissingAPIKeysError):
            create_adapter_from_config(cm)

def test_create_anthropic_adapter_missing_key():
    config = {
        "default_model": "anthropic",
        "models": {
            "anthropic": {"default_model": "claude-3-opus-20240229",
                           "temperature": 0.7,
                           "max_tokens": 1000}
        },
        # No api_keys
        "validation": {"fallback_models": []}
    }
    cm = ConfigManager.from_dict(config)
    with patch.dict(os.environ, {}, clear=True):
        with patch("lamia.engine.llm_manager.AnthropicAdapter", autospec=True):
            with pytest.raises(MissingAPIKeysError):
                create_adapter_from_config(cm)

def test_create_openai_adapter_with_env_key():
    config = {
        "default_model": "openai",
        "models": {
            "openai": {"default_model": "gpt-3.5-turbo",
                        "temperature": 0.7,
                        "max_tokens": 1000}
        },
        # No api_keys
        "validation": {"fallback_models": []}
    }
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-env-key'}):
        cm = ConfigManager.from_dict(config)
        with patch("lamia.engine.llm_manager.OpenAIAdapter", autospec=True) as MockAdapter:
            create_adapter_from_config(cm)
            assert MockAdapter.called

def test_lamia_api_key_from_env(monkeypatch):
    config = {
        "default_model": "openai",
        "models": {
            "openai": {"default_model": "gpt-3.5-turbo"}
        },
        # No api_keys
        "validation": {"fallback_models": []}
    }
    monkeypatch.setenv('LAMIA_API_KEY', 'env-lamia-key')
    cm = ConfigManager.from_dict(config)
    with patch("lamia.engine.llm_manager.OpenAIAdapter", autospec=True) as MockAdapter:
        adapter = create_adapter_from_config(cm)
        assert MockAdapter.called
    monkeypatch.delenv('LAMIA_API_KEY', raising=False)

def test_lamia_api_key_from_config():
    config = {
        "default_model": "openai",
        "models": {
            "openai": {"default_model": "gpt-3.5-turbo"}
        },
        "api_keys": {"lamia": "config-lamia-key"},
        "validation": {"fallback_models": []}
    }
    cm = ConfigManager.from_dict(config)
    with patch("lamia.engine.llm_manager.OpenAIAdapter", autospec=True) as MockAdapter:
        adapter = create_adapter_from_config(cm)
        assert MockAdapter.called 