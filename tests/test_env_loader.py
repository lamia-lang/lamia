"""Tests for env_loader module."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import lamia.env_loader


class TestEnvLoader:
    """Test environment variable loader."""

    def test_module_is_importable(self):
        """Test that env_loader module can be imported."""
        assert lamia.env_loader is not None

    def test_load_dotenv_uses_explicit_cwd_path(self, tmp_path, monkeypatch):
        """Ensure load_dotenv is called with explicit Path.cwd()/.env, not bare."""
        monkeypatch.chdir(tmp_path)
        project_env = tmp_path / ".env"
        project_env.write_text("FOO=bar\n")

        mock_load = MagicMock()
        with patch.object(lamia.env_loader, "load_dotenv", mock_load):
            lamia.env_loader.load_env_files()

        assert mock_load.call_count >= 1
        first_call_path = mock_load.call_args_list[0][0][0]
        assert first_call_path == project_env

    def test_does_not_load_parent_directory_env(self, tmp_path, monkeypatch):
        """Verify that .env in a parent directory is NOT loaded."""
        parent_env = tmp_path / ".env"
        parent_env.write_text("SECRET=from-parent\n")

        child_dir = tmp_path / "child"
        child_dir.mkdir()
        monkeypatch.chdir(child_dir)

        mock_load = MagicMock()
        with patch.object(lamia.env_loader, "load_dotenv", mock_load):
            lamia.env_loader.load_env_files()

        loaded_paths = [str(c[0][0]) for c in mock_load.call_args_list if c[0]]
        assert str(parent_env) not in loaded_paths

    def test_every_call_has_explicit_path(self, tmp_path, monkeypatch):
        """load_dotenv must never be called without an explicit path (security)."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("X=1\n")

        mock_load = MagicMock()
        with patch.object(lamia.env_loader, "load_dotenv", mock_load):
            lamia.env_loader.load_env_files()

        for c in mock_load.call_args_list:
            assert c[0], "load_dotenv was called without an explicit path"
            assert isinstance(c[0][0], Path)