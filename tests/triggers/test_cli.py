"""Tests for lamia.triggers.cli — cloud trigger listing.

Cloud-touching tests mock GCPTriggerProvider rather than hitting real GCP:
this repo only needs to verify lamia calls lamia_cloud's interface correctly.
"""

from unittest import mock

import pytest

from lamia.triggers import cli as triggers_cli


def test_handle_list_prints_no_triggers_deployed(monkeypatch, capsys):
    mock_provider = mock.MagicMock()
    mock_provider.list_deployments.return_value = []
    monkeypatch.setattr(triggers_cli, "_get_cloud_provider", lambda root: mock_provider)

    triggers_cli._handle_list()

    assert "No triggers deployed." in capsys.readouterr().out


def test_handle_list_prints_dead_letter_count_when_present(monkeypatch, capsys):
    mock_provider = mock.MagicMock()
    mock_provider.list_deployments.return_value = [
        {
            "name": "task",
            "script": "task.lm",
            "trigger_method": "email_received",
            "mode": "reactive",
            "last_run": "2026-07-01",
            "last_status": "success",
            "dead_letter_count": 3,
        }
    ]
    monkeypatch.setattr(triggers_cli, "_get_cloud_provider", lambda root: mock_provider)

    triggers_cli._handle_list()

    out = capsys.readouterr().out
    assert "dead letter: 3 failed event(s)" in out


def test_handle_list_omits_dead_letter_line_when_zero(monkeypatch, capsys):
    mock_provider = mock.MagicMock()
    mock_provider.list_deployments.return_value = [
        {
            "name": "task",
            "script": "task.lm",
            "trigger_method": "email_received",
            "mode": "reactive",
            "last_run": "2026-07-01",
            "last_status": "success",
            "dead_letter_count": 0,
        }
    ]
    monkeypatch.setattr(triggers_cli, "_get_cloud_provider", lambda root: mock_provider)

    triggers_cli._handle_list()

    assert "dead letter" not in capsys.readouterr().out


@pytest.mark.integration
def test_get_cloud_provider_builds_provider_from_config(monkeypatch, tmp_path):
    pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
    import lamia_cloud.gcp.trigger_provider as trigger_provider_module

    (tmp_path / "config.yaml").write_text("cloud:\n  project_id: proj\n")
    mock_provider = mock.MagicMock()
    mock_provider_cls = mock.MagicMock()
    mock_provider_cls.from_config.return_value = mock_provider
    monkeypatch.setattr(trigger_provider_module, "GCPTriggerProvider", mock_provider_cls)

    result = triggers_cli._get_cloud_provider(tmp_path)

    mock_provider_cls.from_config.assert_called_once_with({"project_id": "proj"})
    assert result is mock_provider


@pytest.mark.integration
def test_get_cloud_provider_errors_without_project_id(tmp_path, capsys):
    pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
    (tmp_path / "config.yaml").write_text("cloud:\n  location: us-central1\n")

    with pytest.raises(SystemExit) as exc:
        triggers_cli._get_cloud_provider(tmp_path)

    assert exc.value.code == 1
    assert "cloud.project_id" in capsys.readouterr().err
