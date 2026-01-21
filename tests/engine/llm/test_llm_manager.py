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
from lamia import LLMModel
from lamia._internal_types.model_retry import ModelWithRetries


class TestLLMManager:
    """Test suite for LLMManager"""

    def test_check_api_keys_direct(self):
        """Test check_api_key with direct OpenAI API key"""
        cm = _create_config_provider(
            [{"name": "openai", "max_retries": 3}, {"name": "anthropic", "max_retries": 2}],
            api_keys={"openai": "test-openai-key", "anthropic": "test-anthropic-key"}
        )
        
        manager = LLMManager(cm)
        assert manager._resolve_api_key("openai") == ("test-openai-key", False)
        assert manager._resolve_api_key("anthropic") == ("test-anthropic-key", False)

    def test_check_api_key_direct_does_not_override_lamia_proxy(self):
        """Test lamia proxy API key takes precedence over direct provider key"""
        cm = _create_config_provider(
            [{"name": "openai", "max_retries": 3}],
            api_keys={"openai": "direct-key", "lamia": "proxy-key"}
        )
        
        manager = LLMManager(cm)
        result = manager._resolve_api_key("openai")
        assert result == ("proxy-key", True)

    def test_check_api_key_env_fallback(self):
        """Test check_api_key falls back to environment variable"""
        cm = _create_config_provider([{"name": "openai", "max_retries": 3}])
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            manager = LLMManager(cm)
            result = manager._resolve_api_key("openai")
            assert result == ("env-key", False)

    def test_check_api_key_missing_raises_error(self):
        """Test check_api_key raises MissingAPIKeysError when key is missing"""
        cm = _create_config_provider([{"name": "openai", "max_retries": 3}])
        
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(MissingAPIKeysError) as exc_info:
                manager = LLMManager(cm)
            
            assert "openai" in str(exc_info.value)
            assert "OPENAI_API_KEY" in str(exc_info.value)

    def test_check_api_key_unknown_provider(self):
        """Test check_api_key with unknown provider"""
        cm = _create_config_provider([{"name": "unknown", "max_retries": 3}])
        
        with pytest.raises(MissingAPIKeysError) as exc_info:
            manager = LLMManager(cm)

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
        cm = _create_config_provider(
            [{"name": "openai", "max_retries": 3}, {"name": "anthropic", "max_retries": 2}],
            api_keys={"openai": "key1", "anthropic": "key2"}
        )
        
        manager = LLMManager(cm)
        # Should not raise any exception
        manager._check_all_required_api_keys({"openai", "anthropic"})

    def test_check_all_required_api_keys_lamia_proxy(self):
        """Test check_all_required_api_keys with lamia key as proxy"""
        cm = _create_config_provider(
            [{"name": "openai", "max_retries": 3}, {"name": "anthropic", "max_retries": 2}],
            api_keys={"lamia": "proxy-key"}
        )
        
        manager = LLMManager(cm)
        # Should not raise any exception
        manager._check_all_required_api_keys({"openai", "anthropic"})

    def test_check_all_required_api_keys_ollama_no_key_needed(self):
        """Test check_all_required_api_keys with ollama (no key needed)"""
        cm = _create_config_provider([{"name": "ollama", "max_retries": 3}])
        
        manager = LLMManager(cm)
        # Should not raise any exception
        manager._check_all_required_api_keys({"ollama"})

    def test_check_all_required_api_keys_missing_primary(self):
        """Test check_all_required_api_keys with missing primary model key"""
        cm = _create_config_provider([{"name": "openai", "max_retries": 3}])
        
        manager = LLMManager(cm)
        with pytest.raises(MissingAPIKeysError) as exc_info:
            manager._check_all_required_api_keys({"openai"})
        
        assert "openai" in str(exc_info.value)

    def test_check_all_required_api_keys_missing_fallback(self):
        """Test check_all_required_api_keys with missing fallback model key"""
        cm = _create_config_provider(
            [{"name": "openai", "max_retries": 3}, {"name": "anthropic", "max_retries": 2}],
            api_keys={"openai": "key1"}
        )
        
        manager = LLMManager(cm)
        with pytest.raises(MissingAPIKeysError) as exc_info:
            manager._check_all_required_api_keys({"anthropic"})
        
        assert "anthropic" in str(exc_info.value)


class TestCreateAdapterFromConfig:
    """Test suite for create_adapter_from_config function"""

    @pytest.mark.asyncio
    async def test_create_adapter_from_config_openai(self):
        """Test create_adapter_from_config with OpenAI"""
        cm = _create_config_provider(
            [{"name": "openai:gpt-3.5-turbo", "max_retries": 3}],
            api_keys={"openai": "test-key"}
        )
        
        with patch('lamia.engine.managers.llm.providers.OpenAIAdapter') as MockAdapter:
            manager = LLMManager(cm)
            model = LLMModel(name="openai:gpt-3.5-turbo")
            result = await manager.create_adapter_from_config(model)
            MockAdapter.assert_called_once_with(api_key="test-key")

    @pytest.mark.asyncio
    async def test_create_adapter_from_config_anthropic(self):
        """Test create_adapter_from_config with Anthropic"""
        cm = _create_config_provider(
            [{"name": "anthropic:claude-3-opus-20240229", "max_retries": 3}],
            api_keys={"anthropic": "test-key"}
        )
        
        with patch('lamia.engine.managers.llm.providers.AnthropicAdapter') as MockAdapter:
            manager = LLMManager(cm)
            model = LLMModel(name="anthropic:claude-3-opus-20240229")
            result = await manager.create_adapter_from_config(model)
            MockAdapter.assert_called_once_with(api_key="test-key")

    @pytest.mark.asyncio
    async def test_create_adapter_from_config_ollama(self):
        """Test create_adapter_from_config with Ollama"""
        cm = _create_config_provider(
            [{"name": "ollama:llama2", "max_retries": 3}],
            providers={"ollama": {"default_model": "llama2"}}
        )
        
        manager = LLMManager(cm)
        model = LLMModel(name="ollama:llama2")
        result = await manager.create_adapter_from_config(model, with_retries=False)
        assert isinstance(result, OllamaAdapter)
        assert result.model == "llama2"

    @pytest.mark.asyncio
    async def test_create_adapter_from_config_with_different_model(self):
        """Test create_adapter_from_config with different model in chain"""
        cm = _create_config_provider(
            [{"name": "openai:gpt-3.5-turbo", "max_retries": 3},
             {"name": "anthropic:claude-3-opus-20240229", "max_retries": 2}],
            api_keys={"openai": "key1", "anthropic": "key2"}
        )
        
        with patch('lamia.engine.managers.llm.providers.AnthropicAdapter') as MockAdapter:
            manager = LLMManager(cm)
            model = LLMModel(name="anthropic:claude-3-opus-20240229")
            result = await manager.create_adapter_from_config(model)
            MockAdapter.assert_called_once_with(api_key="key2")

    @pytest.mark.asyncio
    async def test_create_adapter_from_config_unsupported_model(self):
        """Test create_adapter_from_config with unsupported model"""
        cm = _create_config_provider([{"name": "unsupported:some-model", "max_retries": 3}])
        
        manager = LLMManager(cm)
        model = LLMModel(name="unsupported:some-model")
        with pytest.raises(ValueError, match="Unknown provider"):
            await manager.create_adapter_from_config(model)

    @pytest.mark.asyncio
    async def test_create_adapter_from_config_missing_api_key(self):
        """Test create_adapter_from_config with missing API key - should raise during init"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(MissingAPIKeysError):
                cm = _create_config_provider([{"name": "openai:gpt-3.5-turbo", "max_retries": 3}])
                manager = LLMManager(cm)

    @pytest.mark.asyncio
    async def test_lamia_api_key_from_env(self, monkeypatch):
        """Test that LAMIA_API_KEY from env is used as proxy"""
        cm = _create_config_provider([{"name": "openai:gpt-3.5-turbo", "max_retries": 3}])
        monkeypatch.setenv("LAMIA_API_KEY", "env-lamia-key")
        manager = LLMManager(cm)
        with patch("lamia.adapters.llm.lamia_adapter.LamiaAdapter", autospec=True) as MockAdapter:
            model = LLMModel(name="openai:gpt-3.5-turbo")
            await manager.create_adapter_from_config(model)
            # The adapter should have been created using the proxy key from the env variable
            MockAdapter.assert_called_once_with(api_key="env-lamia-key")
        monkeypatch.delenv("LAMIA_API_KEY", raising=False)

    @pytest.mark.asyncio
    async def test_ollama_adapter_extended_config(self):
        """Test Ollama adapter with extended configuration"""
        cm = _create_config_provider(
            [{"name": "ollama:llama2", "max_retries": 3}],
            providers={
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
            }
        )
        manager = LLMManager(cm)
        model = LLMModel(name="ollama:llama2")
        adapter = await manager.create_adapter_from_config(model, with_retries=False)
        assert isinstance(adapter, OllamaAdapter)
        assert adapter.base_url == "http://localhost:11434"
        assert adapter.temperature == 0.7
        assert adapter.max_tokens == 1000

def _create_config_provider(model_chain_specs, api_keys=None, providers=None):
    """Helper to create ConfigProvider with proper ModelWithRetries objects."""
    model_chain = []
    for spec in model_chain_specs:
        if isinstance(spec, dict):
            model_name = spec["name"]
            max_retries = spec.get("max_retries", 1)
        else:
            model_name = spec
            max_retries = 1
        
        model = LLMModel(name=model_name)
        model_chain.append(ModelWithRetries(model, max_retries))
    
    config = {
        "model_chain": model_chain,
        "api_keys": api_keys or {},
        "providers": providers or {}
    }
    return ConfigProvider(config)
