"""Tests for lamia.cli.cloud — the 'lamia cloud' subcommand."""

import sys
from unittest import mock

import pytest


@pytest.fixture
def mock_deployer():
    deployer = mock.MagicMock()
    deployer.connect_repository.return_value = {
        "connected": True,
        "message": "Connected.",
    }
    deployer.is_repository_connected.return_value = True
    return deployer


@pytest.fixture
def _stub_cloud(monkeypatch, mock_deployer):
    """Patch git detection and deployer factory for all cloud CLI tests."""
    import lamia.cli.cloud as cloud_mod

    monkeypatch.setattr(
        cloud_mod, "get_remote_origin",
        lambda path: "https://github.com/lamia-lang/lamia.git",
    )
    monkeypatch.setattr(
        cloud_mod, "_get_deployer",
        lambda root: mock_deployer,
    )


class TestCloudConnect:
    @pytest.mark.usefixtures("_stub_cloud")
    def test_connect_success(self, monkeypatch, capsys, mock_deployer):
        monkeypatch.setattr(sys, "argv", ["lamia", "cloud", "connect"])
        from lamia.cli.cloud import handle_cloud

        handle_cloud()
        out = capsys.readouterr().out
        assert "Detected repository" in out
        assert "Git mode enabled" in out
        mock_deployer.connect_repository.assert_called_once_with(
            "https://github.com/lamia-lang/lamia.git"
        )

    def test_connect_no_git_repo(self, monkeypatch, capsys):
        import lamia.cli.cloud as cloud_mod

        monkeypatch.setattr(cloud_mod, "get_remote_origin", lambda path: None)
        monkeypatch.setattr(sys, "argv", ["lamia", "cloud", "connect"])

        with pytest.raises(SystemExit) as exc_info:
            cloud_mod.handle_cloud()
        assert exc_info.value.code == 1
        assert "no remote origin" in capsys.readouterr().err.lower()

    @pytest.mark.usefixtures("_stub_cloud")
    def test_connect_deployer_failure(self, monkeypatch, capsys, mock_deployer):
        mock_deployer.connect_repository.side_effect = RuntimeError("auth failed")
        monkeypatch.setattr(sys, "argv", ["lamia", "cloud", "connect"])

        from lamia.cli.cloud import handle_cloud

        with pytest.raises(SystemExit) as exc_info:
            handle_cloud()
        assert exc_info.value.code == 1
        assert "auth failed" in capsys.readouterr().err


class TestCloudStatus:
    @pytest.mark.usefixtures("_stub_cloud")
    def test_status_connected(self, monkeypatch, capsys, mock_deployer):
        monkeypatch.setattr(sys, "argv", ["lamia", "cloud", "status"])
        from lamia.cli.cloud import handle_cloud

        handle_cloud()
        out = capsys.readouterr().out
        assert "connected" in out.lower()
        mock_deployer.is_repository_connected.assert_called_once()

    @pytest.mark.usefixtures("_stub_cloud")
    def test_status_not_connected(self, monkeypatch, capsys, mock_deployer):
        mock_deployer.is_repository_connected.return_value = False
        monkeypatch.setattr(sys, "argv", ["lamia", "cloud", "status"])

        from lamia.cli.cloud import handle_cloud

        with pytest.raises(SystemExit) as exc_info:
            handle_cloud()
        assert exc_info.value.code == 1
        out = capsys.readouterr().out
        assert "not connected" in out.lower()
