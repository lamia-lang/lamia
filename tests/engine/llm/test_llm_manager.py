import pytest
from unittest.mock import patch, MagicMock, AsyncMock, mock_open
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
        
        with pytest.raises(ValueError) as exc_info:
            manager = LLMManager(cm)

        assert "The following providers are not supported: unknown" in str(exc_info.value)

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
        
        with pytest.raises(MissingAPIKeysError) as exc_info:
            manager = LLMManager(cm)
        
        assert "openai" in str(exc_info.value)

    def test_check_all_required_api_keys_missing_fallback(self):
        """Test check_all_required_api_keys with missing fallback model key"""
        cm = _create_config_provider(
            [{"name": "openai", "max_retries": 3}, {"name": "anthropic", "max_retries": 2}],
            api_keys={"openai": "key1"}
        )
        
        with pytest.raises(MissingAPIKeysError) as exc_info:
            manager = LLMManager(cm)
        
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
        
        mock_adapter_class, mock_instance = _create_mock_adapter("openai", is_remote=True)
        with patch('lamia.engine.managers.llm.providers.OpenAIAdapter', mock_adapter_class):
            manager = LLMManager(cm)
            model = LLMModel(name="openai:gpt-3.5-turbo")
            result = await manager.create_adapter_from_config(model, with_retries=False)
            mock_adapter_class.assert_called_once_with(api_key="test-key")
            assert result == mock_instance

    @pytest.mark.asyncio
    async def test_create_adapter_from_config_anthropic(self):
        """Test create_adapter_from_config with Anthropic"""
        cm = _create_config_provider(
            [{"name": "anthropic:claude-3-opus-20240229", "max_retries": 3}],
            api_keys={"anthropic": "test-key"}
        )
        
        mock_adapter_class, mock_instance = _create_mock_adapter("anthropic", is_remote=True)
        with patch('lamia.engine.managers.llm.providers.AnthropicAdapter', mock_adapter_class):
            manager = LLMManager(cm)
            model = LLMModel(name="anthropic:claude-3-opus-20240229")
            result = await manager.create_adapter_from_config(model, with_retries=False)
            mock_adapter_class.assert_called_once_with(api_key="test-key")
            assert result == mock_instance

    @pytest.mark.asyncio
    async def test_create_adapter_from_config_ollama(self):
        """Test create_adapter_from_config with Ollama"""
        cm = _create_config_provider(
            [{"name": "ollama:llama2", "max_retries": 3}],
            providers={"ollama": {"default_model": "llama2"}}
        )
        
        with patch.object(OllamaAdapter, '_start_ollama_service', return_value=True):
            manager = LLMManager(cm)
            model = LLMModel(name="ollama:llama2")
            result = await manager.create_adapter_from_config(model, with_retries=False)
            assert isinstance(result, OllamaAdapter)
            assert result.base_url == "http://localhost:11434"

    @pytest.mark.asyncio
    async def test_create_adapter_from_config_with_different_model(self):
        """Test create_adapter_from_config with different model in chain"""
        cm = _create_config_provider(
            [{"name": "openai:gpt-3.5-turbo", "max_retries": 3},
             {"name": "anthropic:claude-3-opus-20240229", "max_retries": 2}],
            api_keys={"openai": "key1", "anthropic": "key2"}
        )
        
        mock_openai_class, mock_openai_instance = _create_mock_adapter("openai", is_remote=True)
        mock_anthropic_class, mock_anthropic_instance = _create_mock_adapter("anthropic", is_remote=True)
        
        with patch('lamia.engine.managers.llm.providers.OpenAIAdapter', mock_openai_class):
            with patch('lamia.engine.managers.llm.providers.AnthropicAdapter', mock_anthropic_class):
                manager = LLMManager(cm)
                model = LLMModel(name="anthropic:claude-3-opus-20240229")
                result = await manager.create_adapter_from_config(model, with_retries=False)
                mock_anthropic_class.assert_called_once_with(api_key="key2")
                assert result == mock_anthropic_instance

    @pytest.mark.asyncio
    async def test_create_adapter_from_config_unsupported_model(self):
        """Test create_adapter_from_config with unsupported model"""
        cm = _create_config_provider([{"name": "unsupported:some-model", "max_retries": 3}])
        
        with pytest.raises(ValueError, match="not supported"):
            manager = LLMManager(cm)

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
        monkeypatch.setenv("LAMIA_API_KEY", "env-lamia-key")
        cm = _create_config_provider([{"name": "openai:gpt-3.5-turbo", "max_retries": 3}])
        
        mock_openai_class, _ = _create_mock_adapter("openai", is_remote=True)
        mock_lamia_class, mock_lamia_instance = _create_mock_adapter("lamia", is_remote=True)
        mock_lamia_class.get_supported_providers.return_value = {"openai", "anthropic"}
        
        with patch('lamia.engine.managers.llm.providers.OpenAIAdapter', mock_openai_class):
            with patch('lamia.engine.managers.llm.llm_manager.LamiaAdapter', mock_lamia_class):
                manager = LLMManager(cm)
                model = LLMModel(name="openai:gpt-3.5-turbo")
                result = await manager.create_adapter_from_config(model, with_retries=False)
                # The adapter should have been created using the proxy key from the env variable
                mock_lamia_class.assert_called_once_with(api_key="env-lamia-key")
                assert result == mock_lamia_instance
        
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
        with patch.object(OllamaAdapter, '_start_ollama_service', return_value=True):
            manager = LLMManager(cm)
            model = LLMModel(name="ollama:llama2")
            adapter = await manager.create_adapter_from_config(model, with_retries=False)
            assert isinstance(adapter, OllamaAdapter)
            assert adapter.base_url == "http://localhost:11434"

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

def _create_mock_adapter(provider_name: str, is_remote: bool = True):
    """Helper to create a properly configured mock adapter."""
    mock_adapter_class = MagicMock()
    mock_adapter_class.name.return_value = provider_name
    mock_adapter_class.is_remote.return_value = is_remote
    
    # Create mock instance that will be returned when adapter_class() is called
    mock_instance = MagicMock()
    mock_instance.async_initialize = AsyncMock()
    mock_adapter_class.return_value = mock_instance
    
    return mock_adapter_class, mock_instance
