import pytest
from unittest.mock import AsyncMock, patch
import os
import requests
import sys
import subprocess
from unittest.mock import Mock
import unittest.mock

from lamia.engine.llm_manager import (
    create_adapter_from_config, 
    generate_response,
    is_ollama_running,
    start_ollama_service,
    ensure_ollama_model_pulled,
    MissingAPIKeysError,
)
from lamia.engine.config_manager import ConfigManager
from lamia.adapters.llm.base import LLMResponse
from lamia.adapters.llm.openai_adapter import OpenAIAdapter
from lamia.adapters.llm.anthropic_adapter import AnthropicAdapter
from lamia.adapters.llm.local import OllamaAdapter

@pytest.fixture
def mock_llm_response():
    return LLMResponse(
        text="This is a mock response",
        model="mock-model",
        usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        raw_response={}
    )

class TestCreateAdapterFromConfig:
    def test_create_ollama_adapter(self):
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

    def test_create_openai_adapter(self):
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

    def test_create_anthropic_adapter(self):
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

    def test_unsupported_model(self):
        config = {
            "default_model": "unsupported",
            "models": {"unsupported": {"default_model": "foo"}},
            "validation": {"fallback_models": []}
        }
        cm = ConfigManager.from_dict(config)
        with pytest.raises(ValueError, match="Unsupported model type: unsupported"):
            create_adapter_from_config(cm)

    def test_create_openai_adapter_throws_on_missing_key(self):
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

    def test_create_anthropic_adapter_missing_key(self):
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

    def test_create_openai_adapter_with_env_key(self):
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

    def test_lamia_api_key_from_env(self, monkeypatch):
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

    def test_lamia_api_key_from_config(self):
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

class TestGenerateResponse:
    @pytest.mark.asyncio
    async def test_generate_response_success(self, mock_config_manager, mock_llm_response):
        """Test successful response generation"""
        # Mock the adapter's generate method
        mock_adapter = AsyncMock()
        mock_adapter.generate.return_value = mock_llm_response
        
        # Mock the async context manager
        mock_adapter.__aenter__.return_value = mock_adapter
        mock_adapter.__aexit__.return_value = None

        with patch('lamia.llm_manager.create_adapter_from_config', return_value=mock_adapter):
            response = await generate_response("Test prompt")
            
            assert response.text == "This is a mock response"
            assert response.model == "mock-model"
            assert response.usage == {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
            mock_adapter.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_response_with_custom_config(self, mock_config_manager, mock_llm_response):
        """Test response generation with custom configuration"""
        mock_adapter = AsyncMock()
        mock_adapter.generate.return_value = mock_llm_response
        mock_adapter.__aenter__.return_value = mock_adapter
        mock_adapter.__aexit__.return_value = None

        custom_config_path = "custom_config.yaml"
        
        with patch('lamia.llm_manager.create_adapter_from_config', return_value=mock_adapter):
            response = await generate_response(
                "Test prompt",
                config_path=custom_config_path
            )
            
            assert response.text == "This is a mock response"
            mock_adapter.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_response_error(self, mock_config_manager):
        """Test error handling during response generation"""
        mock_adapter = AsyncMock()
        mock_adapter.generate.side_effect = Exception("API Error")
        mock_adapter.__aenter__.return_value = mock_adapter
        mock_adapter.__aexit__.return_value = None

        with patch('lamia.llm_manager.create_adapter_from_config', return_value=mock_adapter):
            with pytest.raises(Exception, match="API Error"):
                await generate_response("Test prompt")

    @pytest.mark.asyncio
    async def test_generate_response_with_parameters(self, mock_config_manager, mock_llm_response):
        """Test response generation with custom parameters"""
        mock_adapter = AsyncMock()
        mock_adapter.generate.return_value = mock_llm_response
        mock_adapter.__aenter__.return_value = mock_adapter
        mock_adapter.__aexit__.return_value = None

        with patch('lamia.llm_manager.create_adapter_from_config', return_value=mock_adapter):
            await generate_response(
                "Test prompt",
                temperature=0.5,
                max_tokens=500
            )
            
            mock_adapter.generate.assert_called_once_with(
                "Test prompt",
                temperature=0.5,
                max_tokens=500
            )

class TestOllamaService:
    def test_is_ollama_running_true(self):
        """Test detection of running Ollama service"""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            assert is_ollama_running() is True
            mock_get.assert_called_once_with("http://localhost:11434/api/version", timeout=2)

    def test_is_ollama_running_false(self):
        """Test detection of non-running Ollama service"""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError()
            assert is_ollama_running() is False

    def test_start_ollama_service_already_running(self):
        """Test starting Ollama when it's already running"""
        with patch('lamia.engine.llm_manager.is_ollama_running', return_value=True):
            assert start_ollama_service() is True

    def test_start_ollama_service_success(self):
        """Test successful Ollama service start"""
        with patch('lamia.engine.llm_manager.is_ollama_running') as mock_check, \
             patch('subprocess.Popen') as mock_popen:
            # First check fails, second succeeds
            mock_check.side_effect = [False, True]
            mock_popen.return_value = MagicMock()
            assert start_ollama_service() is True
            mock_popen.assert_called_once_with(
                ["ollama", "serve"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

    def test_start_ollama_service_not_installed(self):
        """Test error when Ollama is not installed"""
        with patch('lamia.engine.llm_manager.is_ollama_running', return_value=False), \
             patch('subprocess.Popen') as mock_popen:
            mock_popen.side_effect = FileNotFoundError()
            
            with pytest.raises(RuntimeError, match="Ollama is not installed"):
                start_ollama_service()

    def test_ensure_ollama_model_exists(self):
        """Test checking for existing Ollama model"""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            assert ensure_ollama_model_pulled("llama2") is True
            mock_get.assert_called_once_with(
                "http://localhost:11434/api/show",
                json={"name": "llama2"}
            )

    def test_ensure_ollama_model_pull(self):
        """Test pulling non-existent Ollama model"""
        with patch('requests.get') as mock_get, \
             patch('requests.post') as mock_post:
            # Model doesn't exist
            mock_get.return_value.status_code = 404
            # Pull succeeds
            mock_post.return_value.status_code = 200
            
            assert ensure_ollama_model_pulled("llama2") is True
            mock_post.assert_called_once_with(
                "http://localhost:11434/api/pull",
                json={"name": "llama2"}
            )

    def test_ensure_ollama_model_pull_failure(self):
        """Test failure in pulling Ollama model"""
        with patch('requests.get') as mock_get, \
             patch('requests.post') as mock_post:
            mock_get.return_value.status_code = 404
            mock_post.side_effect = requests.exceptions.RequestException("Network error")
            
            with pytest.raises(RuntimeError, match="Failed to check/pull Ollama model"):
                ensure_ollama_model_pulled("llama2") 