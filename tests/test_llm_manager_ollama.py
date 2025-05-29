import pytest
from unittest.mock import patch, MagicMock
import requests
import subprocess
from lamia.engine.llm_manager import (
    is_ollama_running,
    start_ollama_service,
    ensure_ollama_model_pulled,
)

def test_is_ollama_running_true():
    with patch('requests.get') as mock_get:
        mock_get.return_value.status_code = 200
        assert is_ollama_running() is True
        mock_get.assert_called_once_with("http://localhost:11434/api/version", timeout=2)

def test_is_ollama_running_false():
    with patch('requests.get') as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError()
        assert is_ollama_running() is False

def test_start_ollama_service_already_running():
    with patch('lamia.engine.llm_manager.is_ollama_running', return_value=True):
        assert start_ollama_service() is True

def test_start_ollama_service_success():
    with patch('lamia.engine.llm_manager.is_ollama_running') as mock_check, \
         patch('subprocess.Popen') as mock_popen:
        mock_check.side_effect = [False, True]
        mock_popen.return_value = MagicMock()
        assert start_ollama_service() is True
        mock_popen.assert_called_once_with(
            ["ollama", "serve"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

def test_start_ollama_service_not_installed():
    with patch('lamia.engine.llm_manager.is_ollama_running', return_value=False), \
         patch('subprocess.Popen') as mock_popen:
        mock_popen.side_effect = FileNotFoundError()
        with pytest.raises(RuntimeError, match="Ollama is not installed"):
            start_ollama_service()

def test_ensure_ollama_model_exists():
    with patch('requests.get') as mock_get:
        mock_get.return_value.status_code = 200
        assert ensure_ollama_model_pulled("llama2") is True
        mock_get.assert_called_once_with(
            "http://localhost:11434/api/show",
            json={"name": "llama2"}
        )

def test_ensure_ollama_model_pull():
    with patch('requests.get') as mock_get, \
         patch('requests.post') as mock_post:
        mock_get.return_value.status_code = 404
        mock_post.return_value.status_code = 200
        assert ensure_ollama_model_pulled("llama2") is True
        mock_post.assert_called_once_with(
            "http://localhost:11434/api/pull",
            json={"name": "llama2"}
        )

def test_ensure_ollama_model_pull_failure():
    with patch('requests.get') as mock_get, \
         patch('requests.post') as mock_post:
        mock_get.return_value.status_code = 404
        mock_post.side_effect = requests.exceptions.RequestException("Network error")
        with pytest.raises(RuntimeError, match="Failed to check/pull Ollama model"):
            ensure_ollama_model_pulled("llama2") 