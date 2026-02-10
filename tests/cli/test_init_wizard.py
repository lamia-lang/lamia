"""Tests for the init wizard via its public entry point ``run_init_wizard``."""

import os
import stat
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import requests as requests_lib

from lamia.cli.init_wizard import run_init_wizard, ModelChainEntry, WizardResult
from lamia.env_loader import get_project_env_path, ENV_FILENAME


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture()
def no_ollama():
    """Prevent the wizard from touching a real Ollama installation."""
    mock = MagicMock()
    mock.is_ollama_installed.return_value = False
    with patch("lamia.cli.init_wizard.OllamaAdapter", return_value=mock):
        yield


def _feed_inputs(monkeypatch, inputs: list[str]) -> None:
    it = iter(inputs)
    monkeypatch.setattr("builtins.input", lambda *_: next(it))


# ── OllamaAdapter (tested independently, not part of the wizard) ────────

class TestOllamaDetection:

    def test_ollama_installed_when_on_path(self):
        from lamia.adapters.llm.local.ollama_adapter import OllamaAdapter
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("lamia.adapters.llm.local.ollama_adapter.subprocess.run", return_value=mock_result):
            assert OllamaAdapter.is_ollama_installed() is True

    def test_ollama_not_installed_when_missing(self):
        from lamia.adapters.llm.local.ollama_adapter import OllamaAdapter
        with patch("lamia.adapters.llm.local.ollama_adapter.subprocess.run", side_effect=OSError("missing")):
            assert OllamaAdapter.is_ollama_installed() is False

    def test_ollama_running_when_service_responds(self):
        from lamia.adapters.llm.local.ollama_adapter import OllamaAdapter
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("lamia.adapters.llm.local.ollama_adapter.requests.get", return_value=mock_resp):
            assert OllamaAdapter.is_ollama_running() is True

    def test_ollama_not_running_on_connection_error(self):
        from lamia.adapters.llm.local.ollama_adapter import OllamaAdapter
        with patch("lamia.adapters.llm.local.ollama_adapter.requests.get", side_effect=requests_lib.ConnectionError("refused")):
            assert OllamaAdapter.is_ollama_running() is False

    def test_list_ollama_models_returns_names(self):
        from lamia.adapters.llm.local.ollama_adapter import OllamaAdapter
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "llama3.2:1b"}, {"name": "mistral"}]}
        with patch("lamia.adapters.llm.local.ollama_adapter.requests.get", return_value=mock_resp):
            adapter = OllamaAdapter()
            assert adapter.list_models_sync() == ["llama3.2:1b", "mistral"]

    def test_list_ollama_models_empty_on_failure(self):
        from lamia.adapters.llm.local.ollama_adapter import OllamaAdapter
        mock_running = MagicMock()
        mock_running.status_code = 200
        with patch("lamia.adapters.llm.local.ollama_adapter.requests.get", return_value=mock_running):
            adapter = OllamaAdapter()
        with patch("lamia.adapters.llm.local.ollama_adapter.requests.get", side_effect=requests_lib.ConnectionError("refused")):
            assert adapter.list_models_sync() == []


# ── Data classes ─────────────────────────────────────────────────────────

class TestWizardResult:

    def test_model_chain_entry_fields(self):
        entry = ModelChainEntry(name="anthropic:claude-haiku-4-5-20251001", max_retries=2)
        assert entry.name == "anthropic:claude-haiku-4-5-20251001"
        assert entry.max_retries == 2

    def test_wizard_result_defaults(self):
        result = WizardResult()
        assert result.model_chain == []
        assert result.with_extensions is False


# ── Key detection (through wizard output) ────────────────────────────────

class TestWizardKeyDetection:

    def test_detects_key_from_shell_env(self, tmp_path, monkeypatch, capsys, no_ollama):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-real-key")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        _feed_inputs(monkeypatch, ["1", "1", "", "n"])
        run_init_wizard(str(tmp_path))
        output = capsys.readouterr().out
        assert "OPENAI_API_KEY found via shell environment" in output

    def test_detects_key_from_project_env(self, tmp_path, monkeypatch, capsys, no_ollama):
        project_env = get_project_env_path(tmp_path)
        project_env.write_text("OPENAI_API_KEY=sk-proj-key\n")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-key")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        _feed_inputs(monkeypatch, ["1", "1", "", "n"])
        run_init_wizard(str(tmp_path))
        output = capsys.readouterr().out
        assert f"found via {project_env}" in output

    def test_detects_key_from_global_env(self, tmp_path, monkeypatch, capsys, no_ollama):
        global_env = tmp_path / "fake_global" / ENV_FILENAME
        global_env.parent.mkdir()
        global_env.write_text("OPENAI_API_KEY=sk-global-key\n")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-global-key")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        _feed_inputs(monkeypatch, ["1", "1", "", "n"])
        with patch("lamia.cli.init_wizard.get_global_env_path", return_value=global_env):
            run_init_wizard(str(tmp_path))
        output = capsys.readouterr().out
        assert f"found via {global_env}" in output

    def test_reports_no_api_key_when_missing(self, tmp_path, monkeypatch, capsys, no_ollama):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        # provider, model, retries, skip key entry, no fallback
        _feed_inputs(monkeypatch, ["1", "1", "", "", "n"])
        run_init_wizard(str(tmp_path))
        output = capsys.readouterr().out
        assert "no API key" in output

    def test_ignores_placeholder_key(self, tmp_path, monkeypatch, capsys, no_ollama):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-your-openai-key-here")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        _feed_inputs(monkeypatch, ["1", "1", "", "", "n"])
        run_init_wizard(str(tmp_path))
        output = capsys.readouterr().out
        assert "openai" in output and "no API key" in output

    def test_ignores_anthropic_placeholder(self, tmp_path, monkeypatch, capsys, no_ollama):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-your-anthropic-key-here")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        _feed_inputs(monkeypatch, ["1", "1", "", "", "n"])
        run_init_wizard(str(tmp_path))
        output = capsys.readouterr().out
        assert "anthropic" in output and "no API key" in output

    def test_env_var_names_come_from_registry(self, tmp_path, monkeypatch, capsys, no_ollama):
        """The wizard displays correct env var names from the provider registry."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-real")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-real")
        _feed_inputs(monkeypatch, ["1", "1", "", "n"])
        run_init_wizard(str(tmp_path))
        output = capsys.readouterr().out
        assert "OPENAI_API_KEY" in output
        assert "ANTHROPIC_API_KEY" in output


# ── Key storage (through wizard flow) ────────────────────────────────────

class TestWizardKeyStorage:

    def test_saves_key_globally_with_secure_permissions(self, tmp_path, monkeypatch, no_ollama):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        global_env = tmp_path / "fake_global" / ENV_FILENAME
        # provider, model, retries, enter key, store globally, no fallback
        _feed_inputs(monkeypatch, ["1", "1", "", "sk-new-global", "y", "n"])
        with patch("lamia.cli.init_wizard.get_global_env_path", return_value=global_env), \
             patch("lamia.cli.init_wizard.get_global_lamia_dir", return_value=global_env.parent):
            run_init_wizard(str(tmp_path))
        assert global_env.exists()
        content = global_env.read_text()
        assert "OPENAI_API_KEY=sk-new-global" in content
        mode = global_env.stat().st_mode
        assert mode & stat.S_IRUSR
        assert mode & stat.S_IWUSR
        assert not (mode & stat.S_IRGRP)
        assert not (mode & stat.S_IROTH)

    def test_saves_key_locally(self, tmp_path, monkeypatch, no_ollama):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        # provider, model, retries, enter key, store locally, no fallback
        _feed_inputs(monkeypatch, ["1", "1", "", "sk-new-local", "n", "n"])
        run_init_wizard(str(tmp_path))
        local_env = get_project_env_path(tmp_path)
        assert local_env.exists()
        assert "OPENAI_API_KEY=sk-new-local" in local_env.read_text()

    def test_saves_key_updates_existing_and_preserves_others(self, tmp_path, monkeypatch, no_ollama):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        local_env = get_project_env_path(tmp_path)
        local_env.write_text("OPENAI_API_KEY=old-key\nOTHER_VAR=keep\n")
        _feed_inputs(monkeypatch, ["1", "1", "", "new-key", "n", "n"])
        run_init_wizard(str(tmp_path))
        content = local_env.read_text()
        assert "OPENAI_API_KEY=new-key" in content
        assert "old-key" not in content
        assert "OTHER_VAR=keep" in content

    def test_saves_key_sets_env_var_in_process(self, tmp_path, monkeypatch, no_ollama):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        _feed_inputs(monkeypatch, ["1", "1", "", "sk-process-test", "n", "n"])
        run_init_wizard(str(tmp_path))
        assert os.environ.get("OPENAI_API_KEY") == "sk-process-test"


# ── Input validation (through wizard flow) ───────────────────────────────

class TestWizardInputValidation:

    def test_yes_no_reprompts_on_invalid(self, tmp_path, monkeypatch, capsys, no_ollama):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-real-key")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        # provider, model, retries, then invalid fallback answer, then valid "n"
        _feed_inputs(monkeypatch, ["1", "1", "", "wat", "n"])
        run_init_wizard(str(tmp_path))
        output = capsys.readouterr().out
        assert "Please answer yes or no" in output

    def test_number_reprompts_on_invalid_and_out_of_range(self, tmp_path, monkeypatch, capsys, no_ollama):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-real-key")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        # invalid provider picks, then valid, model, retries, no fallback
        _feed_inputs(monkeypatch, ["nan", "0", "99", "1", "1", "", "n"])
        run_init_wizard(str(tmp_path))
        output = capsys.readouterr().out
        assert "Please enter a number between 1 and" in output


# ── Model chain construction ─────────────────────────────────────────────

class TestWizardModelChain:

    def test_default_model_only(self, tmp_path, monkeypatch, no_ollama):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-real-key")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        _feed_inputs(monkeypatch, ["1", "1", "", "n"])
        result = run_init_wizard(str(tmp_path))
        assert len(result.model_chain) == 1
        assert result.model_chain[0].name.startswith("openai:")
        assert result.model_chain[0].max_retries == 2

    def test_with_fallback(self, tmp_path, monkeypatch, no_ollama):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-real-key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-real-key")
        _feed_inputs(monkeypatch, [
            "1", "1", "",   # default: openai, first model, retries=2
            "y",            # add fallback
            "2", "1", "",   # fallback: anthropic, first model, retries=2
            "n",            # no more fallbacks
        ])
        result = run_init_wizard(str(tmp_path))
        assert len(result.model_chain) == 2
        assert result.model_chain[0].name.startswith("openai:")
        assert result.model_chain[1].name.startswith("anthropic:")

    def test_custom_retries(self, tmp_path, monkeypatch, no_ollama):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-real-key")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        _feed_inputs(monkeypatch, ["1", "1", "5", "n"])
        result = run_init_wizard(str(tmp_path))
        assert result.model_chain[0].max_retries == 5