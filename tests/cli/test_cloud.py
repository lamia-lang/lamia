"""Tests for lamia.cli.cloud — the 'lamia cloud' subcommand."""

import sys
from pathlib import Path
from unittest import mock

import pytest
import yaml


@pytest.fixture
def mock_deployer():
    deployer = mock.MagicMock()
    deployer.connect_repository.return_value = {
        "connected": True,
        "message": "Connected.",
        "connection_id": "v1-123456-abc123def456",
        "branch": "main",
    }
    deployer.is_repository_connected.return_value = True
    deployer.disconnect_repository.return_value = {
        "disconnected": True,
        "deleted": ["WIF provider: lamia-gh-lamia-lang-lamia"],
    }
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
    monkeypatch.setattr(
        cloud_mod, "set_repository_ci_variables",
        lambda **kwargs: None,
    )


class TestCloudConnect:
    @pytest.mark.usefixtures("_stub_cloud")
    def test_connect_success(self, monkeypatch, capsys, mock_deployer, tmp_path):
        (tmp_path / "config.yaml").write_text("cloud:\n  provider: gcp\n  project_id: test\n")
        monkeypatch.setattr(sys, "argv", ["lamia", "cloud", "connect", "--project-root", str(tmp_path)])

        import lamia.cli.cloud as cloud_mod
        cloud_mod.handle_cloud()

        out = capsys.readouterr().out
        assert "Detected repository" in out
        assert "Git mode enabled" in out
        mock_deployer.connect_repository.assert_called_once()

    @pytest.mark.usefixtures("_stub_cloud")
    def test_connect_does_not_write_ci_auth_to_config(self, monkeypatch, tmp_path):
        (tmp_path / "config.yaml").write_text("cloud:\n  provider: gcp\n  project_id: test\n")
        monkeypatch.setattr(sys, "argv", ["lamia", "cloud", "connect", "--project-root", str(tmp_path)])

        import lamia.cli.cloud as cloud_mod
        cloud_mod.handle_cloud()

        cfg = yaml.safe_load((tmp_path / "config.yaml").read_text())
        assert cfg["cloud"]["project_id"] == "test"
        assert "connected_repo" not in cfg["cloud"]
        assert "project_number" not in cfg["cloud"]
        assert "wif_provider" not in cfg["cloud"]
        assert "service_account" not in cfg["cloud"]

    @pytest.mark.usefixtures("_stub_cloud")
    def test_connect_removes_legacy_wif_fields(self, monkeypatch, tmp_path):
        """Connect should not modify config.yaml auth fields."""
        (tmp_path / "config.yaml").write_text(
            "cloud:\n  provider: gcp\n  project_id: test\n"
            "  wif_provider: old\n  service_account: old@proj.iam\n"
        )
        monkeypatch.setattr(sys, "argv", ["lamia", "cloud", "connect", "--project-root", str(tmp_path)])

        import lamia.cli.cloud as cloud_mod
        cloud_mod.handle_cloud()

        cfg = yaml.safe_load((tmp_path / "config.yaml").read_text())
        assert cfg["cloud"]["wif_provider"] == "old"
        assert cfg["cloud"]["service_account"] == "old@proj.iam"

    @pytest.mark.usefixtures("_stub_cloud")
    def test_connect_custom_branch(self, monkeypatch, capsys, mock_deployer, tmp_path):
        (tmp_path / "config.yaml").write_text("cloud:\n  provider: gcp\n  project_id: test\n")
        monkeypatch.setattr(sys, "argv", [
            "lamia", "cloud", "connect",
            "--project-root", str(tmp_path),
            "--branch", "master",
        ])

        import lamia.cli.cloud as cloud_mod
        cloud_mod.handle_cloud()

        mock_deployer.connect_repository.assert_called_once_with(
            "https://github.com/lamia-lang/lamia.git", branch="master",
        )

    @pytest.mark.usefixtures("_stub_cloud")
    def test_connect_prints_ci_workflow_snippet(self, monkeypatch, capsys, tmp_path):
        (tmp_path / "config.yaml").write_text("cloud:\n  provider: gcp\n  project_id: test\n")
        monkeypatch.setattr(sys, "argv", ["lamia", "cloud", "connect", "--project-root", str(tmp_path)])

        import lamia.cli.cloud as cloud_mod
        cloud_mod.handle_cloud()

        out = capsys.readouterr().out
        assert "GitHub CI variables configured successfully" in out
        assert "LAMIA_CONNECTION_ID" in out
        assert "id-token: write" in out
        assert "lamia schedule add" in out
        assert "pull_request_target" in out.lower() or "push" in out.lower()

    @pytest.mark.usefixtures("_stub_cloud")
    def test_connect_configures_github_variables(self, monkeypatch, tmp_path):
        (tmp_path / "config.yaml").write_text("cloud:\n  provider: gcp\n  project_id: test\n")
        monkeypatch.setattr(sys, "argv", ["lamia", "cloud", "connect", "--project-root", str(tmp_path)])

        import lamia.cli.cloud as cloud_mod
        setup_mock = mock.MagicMock()
        monkeypatch.setattr(cloud_mod, "set_repository_ci_variables", setup_mock)
        cloud_mod.handle_cloud()

        setup_mock.assert_called_once()

    @pytest.mark.usefixtures("_stub_cloud")
    def test_connect_exits_when_github_variable_setup_fails(self, monkeypatch, tmp_path):
        (tmp_path / "config.yaml").write_text("cloud:\n  provider: gcp\n  project_id: test\n")
        monkeypatch.setattr(sys, "argv", ["lamia", "cloud", "connect", "--project-root", str(tmp_path)])

        import lamia.cli.cloud as cloud_mod
        monkeypatch.setattr(
            cloud_mod,
            "set_repository_ci_variables",
            mock.MagicMock(side_effect=RuntimeError("denied")),
        )
        with pytest.raises(SystemExit) as exc_info:
            cloud_mod.handle_cloud()
        assert exc_info.value.code == 1

    @pytest.mark.usefixtures("_stub_cloud")
    def test_connect_warns_about_push_only_trigger(self, monkeypatch, capsys, tmp_path):
        (tmp_path / "config.yaml").write_text("cloud:\n  provider: gcp\n  project_id: test\n")
        monkeypatch.setattr(sys, "argv", ["lamia", "cloud", "connect", "--project-root", str(tmp_path)])

        import lamia.cli.cloud as cloud_mod
        cloud_mod.handle_cloud()

        out = capsys.readouterr().out
        assert "pull_request_target" in out

    def test_connect_no_git_repo(self, monkeypatch, capsys):
        import lamia.cli.cloud as cloud_mod
        monkeypatch.setattr(cloud_mod, "get_remote_origin", lambda path: None)
        monkeypatch.setattr(sys, "argv", ["lamia", "cloud", "connect"])

        with pytest.raises(SystemExit) as exc_info:
            cloud_mod.handle_cloud()
        assert exc_info.value.code == 1

    @pytest.mark.usefixtures("_stub_cloud")
    def test_connect_deployer_failure(self, monkeypatch, capsys, mock_deployer):
        mock_deployer.connect_repository.side_effect = RuntimeError("auth failed")
        monkeypatch.setattr(sys, "argv", ["lamia", "cloud", "connect"])

        import lamia.cli.cloud as cloud_mod
        with pytest.raises(SystemExit) as exc_info:
            cloud_mod.handle_cloud()
        assert exc_info.value.code == 1


class TestCloudDisconnect:
    @pytest.mark.usefixtures("_stub_cloud")
    def test_disconnect_does_not_touch_config(self, monkeypatch, capsys, mock_deployer, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        original = (
            "cloud:\n  provider: gcp\n  project_id: test\n"
            "  connected_repo: keep-this\n"
        )
        cfg_path.write_text(original)
        monkeypatch.setattr(sys, "argv", ["lamia", "cloud", "disconnect", "--project-root", str(tmp_path)])

        import lamia.cli.cloud as cloud_mod
        cloud_mod.handle_cloud()

        assert cfg_path.read_text() == original

    @pytest.mark.usefixtures("_stub_cloud")
    def test_disconnect_prints_deleted_resources(self, monkeypatch, capsys, mock_deployer):
        monkeypatch.setattr(sys, "argv", ["lamia", "cloud", "disconnect"])

        import lamia.cli.cloud as cloud_mod
        cloud_mod.handle_cloud()

        out = capsys.readouterr().out
        assert "Deleted:" in out
        assert "disconnected" in out.lower()


class TestCloudStatus:
    @pytest.mark.usefixtures("_stub_cloud")
    def test_status_connected(self, monkeypatch, capsys, mock_deployer):
        monkeypatch.setattr(sys, "argv", ["lamia", "cloud", "status"])
        from lamia.cli.cloud import handle_cloud

        handle_cloud()
        out = capsys.readouterr().out
        assert "connected" in out.lower()

    @pytest.mark.usefixtures("_stub_cloud")
    def test_status_not_connected(self, monkeypatch, capsys, mock_deployer):
        mock_deployer.is_repository_connected.return_value = False
        monkeypatch.setattr(sys, "argv", ["lamia", "cloud", "status"])

        from lamia.cli.cloud import handle_cloud
        with pytest.raises(SystemExit) as exc_info:
            handle_cloud()
        assert exc_info.value.code == 1
