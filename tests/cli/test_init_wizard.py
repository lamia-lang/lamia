"""Tests for the init wizard detection and utility functions.

These tests cover the non-interactive helper functions (detection, key storage, etc.)
without testing the interactive prompts themselves.
"""

import os
import stat
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import requests as requests_lib

from lamia.cli.init_wizard import (
    is_ollama_installed,
    is_ollama_running,
    list_ollama_models,
    detect_api_key,
    save_global_key,
    _save_local_key,
    ModelChainEntry,
    WizardResult,
)


class TestOllamaDetection:

    def test_ollama_installed_when_on_path(self):
        with patch("lamia.cli.init_wizard.shutil.which", return_value="/usr/local/bin/ollama"):
            assert is_ollama_installed() is True

    def test_ollama_not_installed_when_missing(self):
        with patch("lamia.cli.init_wizard.shutil.which", return_value=None):
            assert is_ollama_installed() is False

    def test_ollama_running_when_service_responds(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("lamia.cli.init_wizard.requests.get", return_value=mock_resp):
            assert is_ollama_running() is True

    def test_ollama_not_running_on_connection_error(self):
        with patch("lamia.cli.init_wizard.requests.get", side_effect=requests_lib.ConnectionError("refused")):
            assert is_ollama_running() is False

    def test_list_ollama_models_returns_names(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [
                {"name": "llama3.2:1b"},
                {"name": "mistral"},
            ]
        }
        with patch("lamia.cli.init_wizard.requests.get", return_value=mock_resp):
            models = list_ollama_models()
            assert models == ["llama3.2:1b", "mistral"]

    def test_list_ollama_models_empty_on_failure(self):
        with patch("lamia.cli.init_wizard.requests.get", side_effect=requests_lib.ConnectionError("refused")):
            assert list_ollama_models() == []


class TestApiKeyDetection:

    def test_detect_key_found(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-real-key")
        assert detect_api_key("openai") == "sk-real-key"

    def test_detect_key_ignores_placeholder(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-your-openai-key-here")
        assert detect_api_key("openai") is None

    def test_detect_key_missing(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert detect_api_key("anthropic") is None

    def test_detect_key_unknown_provider(self):
        assert detect_api_key("unknown_provider") is None


class TestGlobalKeyStorage:

    def test_save_global_key_creates_dir_and_file(self, tmp_path, monkeypatch):
        lamia_dir = tmp_path / ".lamia"
        env_file = lamia_dir / ".env"

        with patch("lamia.cli.init_wizard.get_global_lamia_dir", return_value=lamia_dir), \
             patch("lamia.cli.init_wizard.get_global_env_path", return_value=env_file):
            save_global_key("openai", "sk-test-key")

        assert lamia_dir.exists()
        assert env_file.exists()
        content = env_file.read_text()
        assert "OPENAI_API_KEY=sk-test-key" in content

    def test_save_global_key_sets_secure_permissions(self, tmp_path):
        lamia_dir = tmp_path / ".lamia"
        env_file = lamia_dir / ".env"

        with patch("lamia.cli.init_wizard.get_global_lamia_dir", return_value=lamia_dir), \
             patch("lamia.cli.init_wizard.get_global_env_path", return_value=env_file):
            save_global_key("openai", "sk-test-key")

        file_mode = env_file.stat().st_mode
        # Check owner read/write only (0600)
        assert file_mode & stat.S_IRUSR  # owner can read
        assert file_mode & stat.S_IWUSR  # owner can write
        assert not (file_mode & stat.S_IRGRP)  # group cannot read
        assert not (file_mode & stat.S_IROTH)  # others cannot read

    def test_save_global_key_updates_existing_key(self, tmp_path):
        lamia_dir = tmp_path / ".lamia"
        lamia_dir.mkdir()
        env_file = lamia_dir / ".env"
        env_file.write_text("OPENAI_API_KEY=old-key\n")

        with patch("lamia.cli.init_wizard.get_global_lamia_dir", return_value=lamia_dir), \
             patch("lamia.cli.init_wizard.get_global_env_path", return_value=env_file):
            save_global_key("openai", "new-key")

        content = env_file.read_text()
        assert "OPENAI_API_KEY=new-key" in content
        assert "old-key" not in content

    def test_save_global_key_preserves_other_keys(self, tmp_path):
        lamia_dir = tmp_path / ".lamia"
        lamia_dir.mkdir()
        env_file = lamia_dir / ".env"
        env_file.write_text("ANTHROPIC_API_KEY=ant-key\n")

        with patch("lamia.cli.init_wizard.get_global_lamia_dir", return_value=lamia_dir), \
             patch("lamia.cli.init_wizard.get_global_env_path", return_value=env_file):
            save_global_key("openai", "oai-key")

        content = env_file.read_text()
        assert "ANTHROPIC_API_KEY=ant-key" in content
        assert "OPENAI_API_KEY=oai-key" in content

    def test_save_global_key_sets_env_var_in_process(self, tmp_path, monkeypatch):
        lamia_dir = tmp_path / ".lamia"
        env_file = lamia_dir / ".env"
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with patch("lamia.cli.init_wizard.get_global_lamia_dir", return_value=lamia_dir), \
             patch("lamia.cli.init_wizard.get_global_env_path", return_value=env_file):
            save_global_key("openai", "sk-immediate")

        assert os.environ.get("OPENAI_API_KEY") == "sk-immediate"


class TestLocalKeyStorage:

    def test_save_local_key_creates_file(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        _save_local_key(str(tmp_path), "openai", "sk-local-123")

        env_file = tmp_path / ".env"
        assert env_file.exists()
        content = env_file.read_text()
        assert "OPENAI_API_KEY=sk-local-123" in content

    def test_save_local_key_updates_existing(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("OPENAI_API_KEY=old-key\nOTHER_VAR=keep\n")

        _save_local_key(str(tmp_path), "openai", "new-key")

        content = env_file.read_text()
        assert "OPENAI_API_KEY=new-key" in content
        assert "old-key" not in content
        assert "OTHER_VAR=keep" in content

    def test_save_local_key_sets_env_var_in_process(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        _save_local_key(str(tmp_path), "anthropic", "sk-ant-local")
        assert os.environ.get("ANTHROPIC_API_KEY") == "sk-ant-local"


class TestWizardResult:

    def test_model_chain_entry_fields(self):
        entry = ModelChainEntry(name="anthropic:claude-haiku-4-5-20251001", max_retries=2)
        assert entry.name == "anthropic:claude-haiku-4-5-20251001"
        assert entry.max_retries == 2

    def test_wizard_result_defaults(self):
        result = WizardResult()
        assert result.model_chain == []
        assert result.with_extensions is False