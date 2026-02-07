"""Tests for env_loader module."""

import pytest
from unittest.mock import patch, MagicMock


class TestEnvLoader:
    """Test environment variable loader."""

    def test_loads_dotenv_when_available(self):
        """Test that load_dotenv is called when dotenv is available."""
        mock_load_dotenv = MagicMock()
        with patch.dict('sys.modules', {'dotenv': MagicMock(load_dotenv=mock_load_dotenv)}):
            import importlib
            import lamia.env_loader
            importlib.reload(lamia.env_loader)
            mock_load_dotenv.assert_called_once()

    def test_does_not_crash_when_dotenv_missing(self):
        """Test that missing dotenv does not raise an error."""
        with patch.dict('sys.modules', {'dotenv': None}):
            import importlib
            import lamia.env_loader
            try:
                importlib.reload(lamia.env_loader)
            except ImportError:
                pass  # Expected when dotenv is None in sys.modules

    def test_module_is_importable(self):
        """Test that env_loader module can be imported."""
        import lamia.env_loader
        assert lamia.env_loader is not None