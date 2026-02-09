"""Tests for the init wizard detection and utility functions."""

import os
import stat
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import requests as requests_lib

from lamia.cli.init_wizard import (
    _build_provider_list,
    detect_api_key,
    _input_number,
    _input_yes_no,
    _primary_env_var_for_provider,
    save_global_key,
    _save_local_key,
    ModelChainEntry,
    WizardResult,
)


class TestOllamaDetection:
    """Ollama utilities now live in ollama_adapter; test via the re-exports."""

    def test_ollama_installed_when_on_path(self):
        from lamia.adapters.llm.local.ollama_adapter import is_ollama_installed
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("lamia.adapters.llm.local.ollama_adapter.subprocess.run", return_value=mock_result):
            assert is_ollama_installed() is True

    def test_ollama_not_installed_when_missing(self):
        from lamia.adapters.llm.local.ollama_adapter import is_ollama_installed
        with patch("lamia.adapters.llm.local.ollama_adapter.subprocess.run", side_effect=OSError("missing")):
            assert is_ollama_installed() is False

    def test_ollama_running_when_service_responds(self):
        from lamia.adapters.llm.local.ollama_adapter import is_ollama_running
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("lamia.adapters.llm.local.ollama_adapter.requests.get", return_value=mock_resp):
            assert is_ollama_running() is True

    def test_ollama_not_running_on_connection_error(self):
        from lamia.adapters.llm.local.ollama_adapter import is_ollama_running
        with patch("lamia.adapters.llm.local.ollama_adapter.requests.get", side_effect=requests_lib.ConnectionError("refused")):
            assert is_ollama_running() is False

    def test_list_ollama_models_returns_names(self):
        from lamia.adapters.llm.local.ollama_adapter import list_ollama_models_sync
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [
                {"name": "llama3.2:1b"},
                {"name": "mistral"},
            ]
        }
        with patch("lamia.adapters.llm.local.ollama_adapter.requests.get", return_value=mock_resp):
            models = list_ollama_models_sync()
            assert models == ["llama3.2:1b", "mistral"]

    def test_list_ollama_models_empty_on_failure(self):
        from lamia.adapters.llm.local.ollama_adapter import list_ollama_models_sync
        with patch("lamia.adapters.llm.local.ollama_adapter.requests.get", side_effect=requests_lib.ConnectionError("refused")):
            assert list_ollama_models_sync() == []


class TestEnvVarConvention:

    def test_openai(self):
        assert _primary_env_var_for_provider("openai") == "OPENAI_API_KEY"

    def test_anthropic(self):
        assert _primary_env_var_for_provider("anthropic") == "ANTHROPIC_API_KEY"

    def test_unknown(self):
        assert _primary_env_var_for_provider("acme") == "ACME_API_KEY"


class TestApiKeyDetection:

    def test_detect_key_found(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-real-key")
        assert detect_api_key("openai") == "sk-real-key"

    def test_detect_key_ignores_placeholder(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-your-openai-key-here")
        assert detect_api_key("openai") is None

    def test_detect_key_ignores_anthropic_placeholder(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-your-anthropic-key-here")
        assert detect_api_key("anthropic") is None

    def test_detect_key_missing(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert detect_api_key("anthropic") is None

    def test_detect_key_unknown_provider(self, monkeypatch):
        monkeypatch.delenv("UNKNOWN_PROVIDER_API_KEY", raising=False)
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
        assert file_mode & stat.S_IRUSR
        assert file_mode & stat.S_IWUSR
        assert not (file_mode & stat.S_IRGRP)
        assert not (file_mode & stat.S_IROTH)

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


class TestWizardInputs:

    def test_yes_no_reprompts_on_invalid(self, monkeypatch, capsys):
        responses = iter(["wat", "y"])
        monkeypatch.setattr("builtins.input", lambda *_: next(responses))
        assert _input_yes_no("Continue?", default=False) is True
        output = capsys.readouterr().out
        assert "Please answer yes or no" in output

    def test_number_reprompts_on_invalid_and_out_of_range(self, monkeypatch, capsys):
        responses = iter(["nan", "0", "5", "2"])
        monkeypatch.setattr("builtins.input", lambda *_: next(responses))
        assert _input_number("Pick: ", max_val=3, default=1) == 2
        output = capsys.readouterr().out
        assert output.count("Please enter a number between 1 and 3.") == 3


class TestProviderList:

    def test_provider_list_uses_config_order(self):
        providers = _build_provider_list(
            ollama_available=True,
            ollama_model_count=2,
            openai_key="sk-openai-real",
            anthropic_key=None,
        )
        assert [name for name, _ in providers] == ["openai", "anthropic", "ollama"]