"""Tests for lamia.triggers.cli — trigger listing (local + cloud merged).

Cloud-touching tests mock GCPTriggerProvider rather than hitting real GCP:
this repo only needs to verify lamia calls lamia_cloud's interface correctly.
"""

from unittest import mock

import pytest

from lamia.triggers import cli as triggers_cli
from lamia.triggers.local.provider import LocalTriggerProvider


def test_handle_list_verbose_shows_active_executions_count(monkeypatch, capsys):
    """Issue #11: --verbose must surface the active_executions count."""
    monkeypatch.setattr(LocalTriggerProvider, "list_deployments", lambda self: [
        {
            "name": "wf-c9d2",
            "script": "wf.lm",
            "trigger_method": "email_received",
            "mode": "reactive",
            "last_run": "2026-07-01",
            "last_status": "running",
            "failed_event_count": 0,
            "active_executions": 3,
            "location": "local",
        }
    ])
    monkeypatch.setattr(triggers_cli, "_try_cloud_list", lambda: [])

    triggers_cli._handle_list(verbose=True)

    out = capsys.readouterr().out
    assert "active executions: 3" in out or "3 active" in out, (
        f"expected active_executions count in verbose output, got:\n{out}"
    )


def test_handle_drain_unknown_id_reports_not_found(monkeypatch, capsys):
    """Issue #12: draining a nonexistent trigger id must say 'not found', not
    'no failed events' (which implies the id exists)."""
    monkeypatch.setattr(LocalTriggerProvider, "list_deployments", lambda self: [])
    monkeypatch.setattr(LocalTriggerProvider, "clear_failed_events", lambda self, name: 0)
    monkeypatch.setattr(triggers_cli, "_try_get_cloud_provider", lambda: None)

    with pytest.raises(SystemExit):
        triggers_cli._handle_drain("does-not-exist-9999")

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "not found" in combined.lower(), (
        f"expected 'not found' for unknown trigger id, got:\n{combined}"
    )


def test_handle_list_prints_no_triggers_active(monkeypatch, capsys):
    monkeypatch.setattr(LocalTriggerProvider, "list_deployments", lambda self: [])
    monkeypatch.setattr(triggers_cli, "_try_cloud_list", lambda: [])

    triggers_cli._handle_list()

    assert "No triggers active." in capsys.readouterr().out


def test_handle_list_shows_local_trigger(monkeypatch, capsys):
    monkeypatch.setattr(LocalTriggerProvider, "list_deployments", lambda self: [
        {
            "name": "pricing-a3f2",
            "script": "pricing.lm",
            "trigger_method": "email_received",
            "mode": "reactive",
            "last_run": "2026-07-01",
            "last_status": "running",
            "failed_event_count": 0,
            "location": "local",
        }
    ])
    monkeypatch.setattr(triggers_cli, "_try_cloud_list", lambda: [])

    triggers_cli._handle_list()

    out = capsys.readouterr().out
    assert "pricing-a3f2" in out
    assert "local" in out
    assert "running" in out


def test_handle_list_prints_failed_event_count(monkeypatch, capsys):
    monkeypatch.setattr(LocalTriggerProvider, "list_deployments", lambda self: [
        {
            "name": "task-b1c2",
            "script": "task.lm",
            "trigger_method": "email_received",
            "mode": "reactive",
            "last_run": "2026-07-01",
            "last_status": "running",
            "failed_event_count": 3,
            "location": "local",
        }
    ])
    monkeypatch.setattr(triggers_cli, "_try_cloud_list", lambda: [])

    triggers_cli._handle_list()

    out = capsys.readouterr().out
    assert "failed events: 3" in out


def test_handle_list_verbose_shows_event_payloads(monkeypatch, capsys):
    monkeypatch.setattr(LocalTriggerProvider, "list_deployments", lambda self: [
        {
            "name": "task-b1c2",
            "script": "task.lm",
            "trigger_method": "email_received",
            "mode": "reactive",
            "last_run": "2026-07-01",
            "last_status": "running",
            "failed_event_count": 1,
            "location": "local",
        }
    ])
    monkeypatch.setattr(triggers_cli, "_try_cloud_list", lambda: [])
    monkeypatch.setattr(
        LocalTriggerProvider, "get_failed_events",
        lambda self, name: [
            {"payload": {"sender": "a@b.com", "subject": "test"}, "timestamp": "2026-07-01T10:00:00Z"},
        ],
    )

    triggers_cli._handle_list(verbose=True)

    out = capsys.readouterr().out
    assert "failed events: 1" in out
    assert "a@b.com" in out
    assert "2026-07-01T10:00:00Z" in out


def test_handle_list_omits_failed_line_when_zero(monkeypatch, capsys):
    monkeypatch.setattr(LocalTriggerProvider, "list_deployments", lambda self: [
        {
            "name": "task-b1c2",
            "script": "task.lm",
            "trigger_method": "email_received",
            "mode": "reactive",
            "last_run": "2026-07-01",
            "last_status": "running",
            "failed_event_count": 0,
            "location": "local",
        }
    ])
    monkeypatch.setattr(triggers_cli, "_try_cloud_list", lambda: [])

    triggers_cli._handle_list()

    assert "failed events" not in capsys.readouterr().out


def test_handle_drain_clears_local_failed_events(monkeypatch, capsys):
    monkeypatch.setattr(LocalTriggerProvider, "list_deployments", lambda self: [{"name": "pricing-a3f2"}])
    monkeypatch.setattr(LocalTriggerProvider, "clear_failed_events", lambda self, name: 2)

    triggers_cli._handle_drain("pricing-a3f2")

    out = capsys.readouterr().out
    assert "Drained 2" in out


def test_handle_drain_no_events(monkeypatch, capsys):
    monkeypatch.setattr(LocalTriggerProvider, "list_deployments", lambda self: [{"name": "pricing-a3f2"}])
    monkeypatch.setattr(LocalTriggerProvider, "clear_failed_events", lambda self, name: 0)
    monkeypatch.setattr(triggers_cli, "_try_get_cloud_provider", lambda: None)

    triggers_cli._handle_drain("pricing-a3f2")

    out = capsys.readouterr().out
    assert "No failed events" in out


def test_handle_clear_stops_local_trigger(monkeypatch, capsys):
    monkeypatch.setattr(
        LocalTriggerProvider,
        "clear_trigger",
        lambda self, name: {"cleared": True, "was_running": True},
    )

    triggers_cli._handle_clear("pricing-a3f2")

    out = capsys.readouterr().out
    assert "stopped and cleared" in out


def test_handle_clear_reports_stale_when_pid_dead(monkeypatch, capsys):
    """Issue #13: cleaning a stale registry entry must not read as 'stopped'."""
    monkeypatch.setattr(
        LocalTriggerProvider,
        "clear_trigger",
        lambda self, name: {"cleared": True, "was_running": False},
    )

    triggers_cli._handle_clear("stale-1234")

    out = capsys.readouterr().out
    assert "not running" in out or "stale" in out


def test_handle_clear_not_found(monkeypatch, capsys):
    monkeypatch.setattr(
        LocalTriggerProvider,
        "clear_trigger",
        lambda self, name: {"cleared": False, "was_running": False},
    )
    monkeypatch.setattr(triggers_cli, "_try_get_cloud_provider", lambda: None)

    with pytest.raises(SystemExit) as exc:
        triggers_cli._handle_clear("unknown-id")

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
