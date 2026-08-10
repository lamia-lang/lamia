"""Tests for lamia.triggers.local.provider — LocalTriggerProvider."""

import json
import os
from pathlib import Path

import pytest

from lamia.triggers.local import registry
from lamia.triggers.local.provider import LocalTriggerProvider, _is_pid_alive


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    """Point registry at a temp directory."""
    monkeypatch.setattr(registry, "TRIGGERS_DIR", tmp_path)


@pytest.fixture
def fake_project(tmp_path):
    """Create a fake project directory with a test script."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "test.lm").write_text("print('test')")
    (proj / "t.lm").write_text("print('t')")
    return proj


class TestLocalTriggerProvider:
    def test_list_deployments_empty(self):
        provider = LocalTriggerProvider()
        assert provider.list_deployments() == []

    def test_list_deployments_shows_active(self, fake_project):
        registry.save_active_trigger("test-ab12", "test.lm", str(fake_project), "reactive", os.getpid())
        provider = LocalTriggerProvider()
        result = provider.list_deployments()
        assert len(result) == 1
        assert result[0]["name"] == "test-ab12"
        assert result[0]["last_status"] == "running"
        assert result[0]["location"] == "local"

    def test_list_deployments_shows_stopped_for_dead_pid(self, fake_project):
        registry.save_active_trigger("test-ab12", "test.lm", str(fake_project), "reactive", 99999999)
        provider = LocalTriggerProvider()
        result = provider.list_deployments()
        assert result[0]["last_status"] == "stopped"

    def test_get_failed_events(self):
        registry.append_failed_event("test-ab12", {"x": 1}, "boom")
        provider = LocalTriggerProvider()
        events = provider.get_failed_events("test-ab12")
        assert len(events) == 1
        assert events[0]["payload"] == {"x": 1}

    def test_clear_failed_events(self):
        registry.append_failed_event("test-ab12", {"x": 1}, "boom")
        registry.append_failed_event("test-ab12", {"x": 2}, "crash")
        provider = LocalTriggerProvider()
        count = provider.clear_failed_events("test-ab12")
        assert count == 2
        assert provider.get_failed_events("test-ab12") == []

    def test_clear_trigger_removes_from_registry(self, fake_project):
        registry.save_active_trigger("test-ab12", "test.lm", str(fake_project), "reactive", 99999999)
        provider = LocalTriggerProvider()
        result = provider.clear_trigger("test-ab12")
        assert result["cleared"] is True
        assert registry.list_active_triggers() == []

    def test_clear_trigger_nonexistent(self):
        provider = LocalTriggerProvider()
        result = provider.clear_trigger("nope")
        assert result["cleared"] is False

    def test_clear_trigger_reports_was_running_true_when_pid_alive(self, fake_project):
        """Issue #13: caller must be able to tell we actually killed a live process."""
        import subprocess
        proc = subprocess.Popen(["sleep", "30"])
        try:
            registry.save_active_trigger("test-alive", "t.lm", str(fake_project), "reactive", proc.pid)
            result = LocalTriggerProvider().clear_trigger("test-alive")
            assert result["cleared"] is True
            assert result["was_running"] is True
        finally:
            proc.kill()
            proc.wait(timeout=5)

    def test_clear_trigger_reports_was_running_false_when_pid_dead(self, fake_project):
        """Issue #13: cleaning stale registry state must not look like we killed something."""
        registry.save_active_trigger("test-dead", "t.lm", str(fake_project), "reactive", 99999999)
        result = LocalTriggerProvider().clear_trigger("test-dead")
        assert result["cleared"] is True
        assert result["was_running"] is False

    def test_list_deployments_stopped_when_pid_reused_by_unrelated_process(self, fake_project):
        """Issue #14: a live PID that was created AFTER the trigger's started_at is
        a reused PID (unrelated process) and must not read as 'running'."""
        import subprocess
        proc = subprocess.Popen(["sleep", "30"])
        try:
            registry.save_active_trigger("test-reused", "t.lm", str(fake_project), "reactive", proc.pid)
            # Rewrite started_at to 24h in the past — before the proc was created.
            from datetime import datetime, timedelta, timezone
            entries = registry.list_active_triggers()
            entries[0]["started_at"] = (
                datetime.now(timezone.utc) - timedelta(days=1)
            ).isoformat()
            (registry.TRIGGERS_DIR / "active.json").write_text(
                json.dumps(entries, indent=2)
            )

            result = LocalTriggerProvider().list_deployments()
            assert result[0]["last_status"] == "stopped", (
                "a PID with process-start > registry-started_at is a reused PID; "
                f"must not read as running, got {result[0]['last_status']}"
            )
        finally:
            proc.kill()
            proc.wait(timeout=5)


    def test_list_deployments_marks_stale_missing_script(self, fake_project):
        """Trigger entries for deleted scripts remain visible as SOURCE_MISSING."""
        registry.save_active_trigger("stale-1", "deleted.lm", str(fake_project), "reactive", 99999999)
        provider = LocalTriggerProvider()
        result = provider.list_deployments()
        assert len(result) == 1
        assert result[0]["name"] == "stale-1"
        assert result[0]["source_missing"] is True
        assert result[0]["last_status"] == "SOURCE_MISSING"
        assert registry.get_active_trigger("stale-1") is not None


class TestIsPidAlive:
    def test_current_process_is_alive(self):
        assert _is_pid_alive(os.getpid()) is True

    def test_dead_pid(self):
        assert _is_pid_alive(99999999) is False
