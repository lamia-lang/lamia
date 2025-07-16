import pytest
from unittest.mock import patch, MagicMock
import subprocess
import requests
from lamia.engine.managers.llm.ollama_manager import OllamaManager


def test_is_running_true():
    manager = OllamaManager()
    with patch('requests.get') as mock_get:
        mock_get.return_value.status_code = 200
        assert manager.is_running() is True
        mock_get.assert_called_once_with("http://localhost:11434/api/version", timeout=2)

def test_is_running_false_bad_status():
    manager = OllamaManager()
    with patch('requests.get') as mock_get:
        mock_get.return_value.status_code = 404
        assert manager.is_running() is False

def test_is_running_false_connection_error():
    manager = OllamaManager()
    with patch('requests.get') as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError()
        assert manager.is_running() is False

def test_is_running_false_timeout():
    manager = OllamaManager()
    with patch('requests.get') as mock_get:
        mock_get.side_effect = requests.exceptions.Timeout()
        assert manager.is_running() is False

def test_list_models_success():
    manager = OllamaManager()
    with patch.object(manager, 'is_running', return_value=True), \
         patch('requests.get') as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "models": [
                {"name": "llama2:latest"},
                {"name": "codellama:7b"}
            ]
        }
        result = manager.list_models()
        assert result == ["llama2:latest", "codellama:7b"]

def test_list_models_service_not_running():
    manager = OllamaManager()
    with patch.object(manager, 'is_running', return_value=False):
        result = manager.list_models()
        assert result == []

def test_list_models_bad_response():
    manager = OllamaManager()
    with patch.object(manager, 'is_running', return_value=True), \
         patch('requests.get') as mock_get:
        mock_get.return_value.status_code = 500
        result = manager.list_models()
        assert result == []

def test_list_models_connection_error():
    manager = OllamaManager()
    with patch.object(manager, 'is_running', return_value=True), \
         patch('requests.get') as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError()
        result = manager.list_models()
        assert result == []

def test_start_service_already_running():
    manager = OllamaManager()
    with patch.object(manager, 'is_running', return_value=True):
        result = manager.start_service()
        assert result is True

def test_start_service_success():
    manager = OllamaManager()
    with patch.object(manager, 'is_running') as mock_check, \
         patch('subprocess.Popen') as mock_popen:
        mock_check.side_effect = [False, True]  # Not running, then running
        mock_popen.return_value = MagicMock()
        result = manager.start_service()
        assert result is True
        mock_popen.assert_called_once_with(
            ["ollama", "serve"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

def test_start_service_timeout():
    manager = OllamaManager()
    with patch.object(manager, 'is_running', return_value=False), \
         patch('subprocess.Popen') as mock_popen, \
         patch('time.sleep'):
        mock_popen.return_value = MagicMock()
        result = manager.start_service()
        assert result is False

def test_start_service_not_installed():
    manager = OllamaManager()
    with patch.object(manager, 'is_running', return_value=False), \
         patch('subprocess.Popen') as mock_popen:
        mock_popen.side_effect = FileNotFoundError()
        with pytest.raises(RuntimeError, match="Ollama is not installed"):
            manager.start_service()

def test_start_service_generic_error():
    manager = OllamaManager()
    with patch.object(manager, 'is_running', return_value=False), \
         patch('subprocess.Popen') as mock_popen:
        mock_popen.side_effect = Exception("Some error")
        result = manager.start_service()
        assert result is False

def test_ensure_model_pulled_exists():
    manager = OllamaManager()
    with patch('requests.get') as mock_get:
        mock_get.return_value.status_code = 200
        result = manager.ensure_model_pulled("llama2")
        assert result is True
        mock_get.assert_called_once_with(
            "http://localhost:11434/api/show",
            json={"name": "llama2"}
        )

def test_ensure_model_pulled_pull_success():
    manager = OllamaManager()
    with patch('requests.get') as mock_get, \
         patch('requests.post') as mock_post:
        mock_get.return_value.status_code = 404
        mock_post.return_value.status_code = 200
        result = manager.ensure_model_pulled("llama2")
        assert result is True
        mock_post.assert_called_once_with(
            "http://localhost:11434/api/pull",
            json={"name": "llama2"}
        )

def test_ensure_model_pulled_pull_failure():
    manager = OllamaManager()
    with patch('requests.get') as mock_get, \
         patch('requests.post') as mock_post:
        mock_get.return_value.status_code = 404
        mock_post.return_value.status_code = 500
        result = manager.ensure_model_pulled("llama2")
        assert result is False

def test_ensure_model_pulled_connection_error():
    manager = OllamaManager()
    with patch('requests.get') as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError()
        with pytest.raises(RuntimeError, match="Failed to check/pull Ollama model"):
            manager.ensure_model_pulled("llama2") 