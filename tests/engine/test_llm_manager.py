import pytest
from unittest.mock import patch, MagicMock, mock_open
import os
import subprocess
import requests
import sys
from pathlib import Path
import importlib.util

from lamia.engine.llm_manager import (
    check_api_key,
    check_all_required_api_keys,
    is_ollama_running,
    start_ollama_service,
    list_available_ollama_models,
    ensure_ollama_model_pulled,
    create_adapter_from_config,
    _discover_adapters_in_path,
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
        
        result = check_api_key("openai", cm)
        assert result == "test-openai-key"
        assert result == "test-anthropic-key"

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


class TestOllamaFunctions:
    """Test suite for Ollama-related functions"""

    def test_is_ollama_running_true(self):
        """Test is_ollama_running returns True when service is running"""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            assert is_ollama_running() is True
            mock_get.assert_called_once_with("http://localhost:11434/api/version", timeout=2)

    def test_is_ollama_running_false_bad_status(self):
        """Test is_ollama_running returns False when service returns bad status"""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 404
            assert is_ollama_running() is False

    def test_is_ollama_running_false_connection_error(self):
        """Test is_ollama_running returns False on connection error"""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError()
            assert is_ollama_running() is False

    def test_is_ollama_running_false_timeout(self):
        """Test is_ollama_running returns False on timeout"""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout()
            assert is_ollama_running() is False

    def test_list_available_ollama_models_success(self):
        """Test list_available_ollama_models returns model list"""
        with patch('lamia.engine.llm_manager.is_ollama_running', return_value=True), \
             patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                "models": [
                    {"name": "llama2:latest"},
                    {"name": "codellama:7b"}
                ]
            }
            
            result = list_available_ollama_models()
            assert result == ["llama2:latest", "codellama:7b"]

    def test_list_available_ollama_models_service_not_running(self):
        """Test list_available_ollama_models when service is not running"""
        with patch('lamia.engine.llm_manager.is_ollama_running', return_value=False):
            result = list_available_ollama_models()
            assert result == []

    def test_list_available_ollama_models_bad_response(self):
        """Test list_available_ollama_models with bad response"""
        with patch('lamia.engine.llm_manager.is_ollama_running', return_value=True), \
             patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 500
            
            result = list_available_ollama_models()
            assert result == []

    def test_list_available_ollama_models_connection_error(self):
        """Test list_available_ollama_models with connection error"""
        with patch('lamia.engine.llm_manager.is_ollama_running', return_value=True), \
             patch('requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError()
            
            result = list_available_ollama_models()
            assert result == []

    def test_start_ollama_service_already_running(self):
        """Test start_ollama_service when already running"""
        with patch('lamia.engine.llm_manager.is_ollama_running', return_value=True):
            result = start_ollama_service()
            assert result is True

    def test_start_ollama_service_success(self):
        """Test start_ollama_service starts successfully"""
        with patch('lamia.engine.llm_manager.is_ollama_running') as mock_check, \
             patch('subprocess.Popen') as mock_popen:
            mock_check.side_effect = [False, True]  # Not running, then running
            mock_popen.return_value = MagicMock()
            
            result = start_ollama_service()
            assert result is True
            mock_popen.assert_called_once_with(
                ["ollama", "serve"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

    def test_start_ollama_service_timeout(self):
        """Test start_ollama_service timeout"""
        with patch('lamia.engine.llm_manager.is_ollama_running', return_value=False), \
             patch('subprocess.Popen') as mock_popen, \
             patch('time.sleep'):  # Speed up the test
            mock_popen.return_value = MagicMock()
            
            result = start_ollama_service()
            assert result is False

    def test_start_ollama_service_not_installed(self):
        """Test start_ollama_service when ollama is not installed"""
        with patch('lamia.engine.llm_manager.is_ollama_running', return_value=False), \
             patch('subprocess.Popen') as mock_popen:
            mock_popen.side_effect = FileNotFoundError()
            
            with pytest.raises(RuntimeError, match="Ollama is not installed"):
                start_ollama_service()

    def test_start_ollama_service_generic_error(self):
        """Test start_ollama_service with generic error"""
        with patch('lamia.engine.llm_manager.is_ollama_running', return_value=False), \
             patch('subprocess.Popen') as mock_popen:
            mock_popen.side_effect = Exception("Some error")
            
            result = start_ollama_service()
            assert result is False

    def test_ensure_ollama_model_pulled_exists(self):
        """Test ensure_ollama_model_pulled when model exists"""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            
            result = ensure_ollama_model_pulled("llama2")
            assert result is True
            mock_get.assert_called_once_with(
                "http://localhost:11434/api/show",
                json={"name": "llama2"}
            )

    def test_ensure_ollama_model_pulled_pull_success(self):
        """Test ensure_ollama_model_pulled pulls model successfully"""
        with patch('requests.get') as mock_get, \
             patch('requests.post') as mock_post:
            mock_get.return_value.status_code = 404
            mock_post.return_value.status_code = 200
            
            result = ensure_ollama_model_pulled("llama2")
            assert result is True
            mock_post.assert_called_once_with(
                "http://localhost:11434/api/pull",
                json={"name": "llama2"}
            )

    def test_ensure_ollama_model_pulled_pull_failure(self):
        """Test ensure_ollama_model_pulled when pull fails"""
        with patch('requests.get') as mock_get, \
             patch('requests.post') as mock_post:
            mock_get.return_value.status_code = 404
            mock_post.return_value.status_code = 500
            
            result = ensure_ollama_model_pulled("llama2")
            assert result is False

    def test_ensure_ollama_model_pulled_connection_error(self):
        """Test ensure_ollama_model_pulled with connection error"""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError()
            
            with pytest.raises(RuntimeError, match="Failed to check/pull Ollama model"):
                ensure_ollama_model_pulled("llama2")


class TestDiscoverAdaptersInPath:
    """Test suite for _discover_adapters_in_path function"""

    def test_discover_adapters_in_path_nonexistent_directory(self):
        """Test _discover_adapters_in_path with nonexistent directory"""
        result = _discover_adapters_in_path("/nonexistent/path")
        assert result == {}

    def test_discover_adapters_in_path_empty_directory(self):
        """Test _discover_adapters_in_path with empty directory"""
        with patch('os.path.isdir', return_value=True), \
             patch('os.listdir', return_value=[]):
            result = _discover_adapters_in_path("/empty/path")
            assert result == {}

    def test_discover_adapters_in_path_no_python_files(self):
        """Test _discover_adapters_in_path with no Python files"""
        with patch('os.path.isdir', return_value=True), \
             patch('os.listdir', return_value=["file.txt", "README.md"]):
            result = _discover_adapters_in_path("/path")
            assert result == {}

    def test_discover_adapters_in_path_import_error(self):
        """Test _discover_adapters_in_path handles import errors gracefully"""
        with patch('os.path.isdir', return_value=True), \
             patch('os.listdir', return_value=["broken.py"]), \
             patch('importlib.util.spec_from_file_location', return_value=None):
            result = _discover_adapters_in_path("/path")
            assert result == {}


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

    def test_openai_adapter_with_env_key(self):
        config = {
            "default_model": "openai",
            "models": {
                "openai": {"default_model": "gpt-3.5-turbo", "temperature": 0.7, "max_tokens": 1000}
            },
            # No api_keys provided
            "validation": {"fallback_models": []}
        }
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-env-key"}):
            cm = ConfigManager(config)
            with patch("lamia.engine.llm_manager.OpenAIAdapter", autospec=True) as MockAdapter:
                adapter = create_adapter_from_config(cm)
                # Ensure adapter was instantiated with the env key
                MockAdapter.assert_called()
                assert adapter.api_key == "test-env-key"

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
