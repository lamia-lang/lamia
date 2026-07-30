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


def test_handle_list_prints_failed_event_count(monkeypatch, capsys):
    mock_provider = mock.MagicMock()
    mock_provider.list_deployments.return_value = [
        {
            "name": "task",
            "script": "task.lm",
            "trigger_method": "email_received",
            "mode": "reactive",
            "last_run": "2026-07-01",
            "last_status": "success",
            "failed_event_count": 3,
        }
    ]
    monkeypatch.setattr(triggers_cli, "_get_cloud_provider", lambda root: mock_provider)

    triggers_cli._handle_list()

    out = capsys.readouterr().out
    assert "failed events: 3" in out


def test_handle_list_verbose_shows_event_payloads(monkeypatch, capsys):
    mock_provider = mock.MagicMock()
    mock_provider.list_deployments.return_value = [
        {
            "name": "task",
            "script": "task.lm",
            "trigger_method": "email_received",
            "mode": "reactive",
            "last_run": "2026-07-01",
            "last_status": "success",
            "failed_event_count": 1,
        }
    ]
    mock_provider.get_failed_events.return_value = [
        {"payload": {"sender": "a@b.com", "subject": "test"}, "timestamp": "2026-07-01T10:00:00Z"},
    ]
    monkeypatch.setattr(triggers_cli, "_get_cloud_provider", lambda root: mock_provider)

    triggers_cli._handle_list(verbose=True)

    out = capsys.readouterr().out
    assert "failed events: 1" in out
    assert "a@b.com" in out
    assert "2026-07-01T10:00:00Z" in out


def test_handle_list_omits_failed_line_when_zero(monkeypatch, capsys):
    mock_provider = mock.MagicMock()
    mock_provider.list_deployments.return_value = [
        {
            "name": "task",
            "script": "task.lm",
            "trigger_method": "email_received",
            "mode": "reactive",
            "last_run": "2026-07-01",
            "last_status": "success",
            "failed_event_count": 0,
        }
    ]
    monkeypatch.setattr(triggers_cli, "_get_cloud_provider", lambda root: mock_provider)

    triggers_cli._handle_list()

    assert "failed events" not in capsys.readouterr().out


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


class TestHandleLogs:
    def test_prints_stdout_stderr_and_url(self, monkeypatch, capsys):
        mock_provider = mock.MagicMock()
        mock_provider.fetch_logs.return_value = {
            "stdout": "run output\n",
            "stderr": "warning line\n",
            "logs_url": "https://console.cloud.google.com/logs/query",
        }
        monkeypatch.setattr(triggers_cli, "_get_cloud_provider", lambda root: mock_provider)

        args = mock.MagicMock()
        args.id = "pricing-reply"
        triggers_cli._handle_logs(args)

        mock_provider.fetch_logs.assert_called_once_with("pricing-reply")
        captured = capsys.readouterr()
        assert captured.out == (
            "run output\n\nLogs: https://console.cloud.google.com/logs/query\n"
        )
        assert captured.err == "warning line\n"

    def test_tolerates_partial_log_payload(self, monkeypatch, capsys):
        mock_provider = mock.MagicMock()
        mock_provider.fetch_logs.return_value = {"stdout": "only stdout\n"}
        monkeypatch.setattr(triggers_cli, "_get_cloud_provider", lambda root: mock_provider)

        args = mock.MagicMock()
        args.id = "pricing-reply"
        triggers_cli._handle_logs(args)

        assert capsys.readouterr().out == "only stdout\n"

    def test_exits_when_trigger_has_no_jobs(self, monkeypatch, capsys):
        mock_provider = mock.MagicMock()
        mock_provider.fetch_logs.side_effect = ValueError("No deployed jobs found")
        monkeypatch.setattr(triggers_cli, "_get_cloud_provider", lambda root: mock_provider)

        args = mock.MagicMock()
        args.id = "missing"
        with pytest.raises(SystemExit):
            triggers_cli._handle_logs(args)

        assert "No deployed jobs found" in capsys.readouterr().err
