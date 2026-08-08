"""Tests for lamia.triggers.local.orchestrator — local trigger execution engine."""

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lamia.triggers.local import registry
from lamia.triggers.constants import EXIT_CODE_REJECT, MAX_EXCEPTION_RETRIES
from lamia.triggers.local.event_sources.base import BaseEventSource
from lamia.triggers.local.orchestrator import (
    _create_event_source,
    _handle_execution,
    _run_stage_with_retry,
    _wait_for_continuation,
)
from lamia.triggers.types import TriggerStage


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    """Point registry at a temp directory."""
    monkeypatch.setattr(registry, "TRIGGERS_DIR", tmp_path)


class MockEventSource(BaseEventSource):
    """Controllable event source for testing."""

    def __init__(self, events=None):
        self.events = list(events or [])
        self.started = False
        self.stopped = False

    def start(self, trigger_config: dict) -> None:
        self.started = True

    def wait_for_event(self, timeout_seconds: int):
        if self.events:
            return self.events.pop(0)
        return None

    def stop(self) -> None:
        self.stopped = True


class TestContinuationIsolation:
    """Issue #2: multiple concurrent continuation waits on the same trigger config
    must share a single event source and route events FIFO — no fanout, no dup."""

    def test_no_fanout_across_concurrent_waiters(self):
        """3 executions waiting → 3 events fired → each execution gets exactly one
        distinct event (no execution receives the same event twice, no execution
        misses an event that another already consumed)."""
        from queue import Queue
        from lamia.triggers.local.orchestrator import _ContinuationBroker

        # A stub event source we push events into by hand.
        source = MockEventSource(events=[])
        source.pending = Queue()

        def _wait(timeout_seconds):
            try:
                return source.pending.get(timeout=timeout_seconds)
            except Exception:
                return None

        source.wait_for_event = _wait  # type: ignore

        broker = _ContinuationBroker(source, trigger_config={})
        results: list = []
        results_lock = threading.Lock()

        def waiter():
            ev = broker.wait_for_event(timeout_seconds=5)
            with results_lock:
                results.append(ev)

        threads = [threading.Thread(target=waiter) for _ in range(3)]
        for t in threads:
            t.start()
        time.sleep(0.1)  # let all threads register with the broker

        source.pending.put({"n": 1})
        source.pending.put({"n": 2})
        source.pending.put({"n": 3})

        for t in threads:
            t.join(timeout=5)

        broker.stop()

        assert len(results) == 3
        assert all(r is not None for r in results), f"a waiter missed an event: {results}"
        distinct = {r["n"] for r in results}
        assert distinct == {1, 2, 3}, (
            f"expected each waiter to get a distinct event, got {results}"
        )


class TestGetEmailConfig:
    """Issue #10: email config must be read from project_root, not cwd."""

    def test_reads_from_project_root_not_cwd(self, tmp_path, monkeypatch):
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "config.yaml").write_text(
            "triggers:\n  email:\n    host: imap.project.example\n    username: proj-user\n"
        )
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)  # cwd is somewhere else

        from lamia.triggers.local.orchestrator import _get_email_config

        cfg = _get_email_config(project_root=project_root)
        assert cfg.get("host") == "imap.project.example"
        assert cfg.get("username") == "proj-user"


class TestCreateEventSource:
    def test_file_created(self):
        source = _create_event_source("file_created", "trig-1")
        assert source is not None

    def test_file_modified(self):
        source = _create_event_source("file_modified", "trig-1")
        assert source is not None

    def test_email_received(self):
        source = _create_event_source("email_received", "trig-1")
        assert source is not None

    def test_unsupported_raises(self):
        with pytest.raises(ValueError, match="Unsupported trigger method"):
            _create_event_source("webhook_received", "trig-1")


class TestRunStageWithRetry:
    def test_success_on_first_try(self, tmp_path):
        stopped = threading.Event()
        with patch("lamia.triggers.local.orchestrator._spawn_stage", return_value=0):
            result = _run_stage_with_retry(
                script_path=Path("test.lm"),
                stage_index=0,
                event_data={"x": 1},
                stage_context=None,
                exec_id="abc",
                trigger_id="test-1234",
                stopped=stopped,
            )
        assert result == 0

    def test_reject_returns_immediately(self, tmp_path):
        stopped = threading.Event()
        with patch("lamia.triggers.local.orchestrator._spawn_stage", return_value=EXIT_CODE_REJECT):
            result = _run_stage_with_retry(
                script_path=Path("test.lm"),
                stage_index=0,
                event_data={"x": 1},
                stage_context=None,
                exec_id="abc",
                trigger_id="test-1234",
                stopped=stopped,
            )
        assert result == EXIT_CODE_REJECT

    def test_retries_on_failure(self, tmp_path):
        stopped = threading.Event()
        call_count = {"n": 0}

        def mock_spawn(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] < 3:
                return 1
            return 0

        with patch("lamia.triggers.local.orchestrator._spawn_stage", side_effect=mock_spawn):
            result = _run_stage_with_retry(
                script_path=Path("test.lm"),
                stage_index=0,
                event_data={"x": 1},
                stage_context=None,
                exec_id="abc",
                trigger_id="test-1234",
                stopped=stopped,
            )
        assert result == 0
        assert call_count["n"] == 3

    def test_exhausts_retries_and_records_failed_event(self, tmp_path):
        stopped = threading.Event()
        with patch("lamia.triggers.local.orchestrator._spawn_stage", return_value=1):
            result = _run_stage_with_retry(
                script_path=Path("test.lm"),
                stage_index=0,
                event_data={"email": "a@b.com"},
                stage_context=None,
                exec_id="abc",
                trigger_id="test-1234",
                stopped=stopped,
            )
        assert result == 1
        failed = registry.get_failed_events("test-1234")
        assert len(failed) == 1
        assert failed[0]["payload"]["email"] == "a@b.com"

    def test_respects_stopped_flag(self):
        stopped = threading.Event()
        stopped.set()
        with patch("lamia.triggers.local.orchestrator._spawn_stage", return_value=1) as mock_sp:
            result = _run_stage_with_retry(
                script_path=Path("test.lm"),
                stage_index=0,
                event_data={},
                stage_context=None,
                exec_id="abc",
                trigger_id="test-1234",
                stopped=stopped,
            )
        assert result == 1
        mock_sp.assert_not_called()


class TestWaitForContinuation:
    def test_returns_event_immediately(self):
        stage = TriggerStage(stage_index=1, trigger_method="file_created", trigger_config={"path": "/tmp"})
        stopped = threading.Event()

        mock_source = MockEventSource(events=[{"name": "report.pdf"}])

        from datetime import datetime, timezone, timedelta
        deadline = datetime.now(timezone.utc) + timedelta(seconds=10)

        with patch("lamia.triggers.local.orchestrator._create_event_source", return_value=mock_source):
            result = _wait_for_continuation(
                stage=stage,
                trigger_id="test-1234",
                exec_id="abc",
                deadline=deadline,
                stopped=stopped,
            )

        assert result == {"name": "report.pdf"}
        assert mock_source.stopped

    def test_returns_none_on_timeout(self):
        stage = TriggerStage(stage_index=1, trigger_method="file_created", trigger_config={"path": "/tmp"})
        stopped = threading.Event()

        mock_source = MockEventSource(events=[])

        from datetime import datetime, timezone, timedelta
        deadline = datetime.now(timezone.utc) + timedelta(seconds=1)

        with patch("lamia.triggers.local.orchestrator._create_event_source", return_value=mock_source):
            result = _wait_for_continuation(
                stage=stage,
                trigger_id="test-1234",
                exec_id="abc",
                deadline=deadline,
                stopped=stopped,
            )

        assert result is None

    def test_returns_none_when_stopped(self):
        stage = TriggerStage(stage_index=1, trigger_method="file_created", trigger_config={"path": "/tmp"})
        stopped = threading.Event()
        stopped.set()

        mock_source = MockEventSource(events=[{"name": "should_not_get"}])

        from datetime import datetime, timezone, timedelta
        deadline = datetime.now(timezone.utc) + timedelta(seconds=60)

        with patch("lamia.triggers.local.orchestrator._create_event_source", return_value=mock_source):
            result = _wait_for_continuation(
                stage=stage,
                trigger_id="test-1234",
                exec_id="abc",
                deadline=deadline,
                stopped=stopped,
            )

        assert result is None


class TestHandleExecution:
    def test_single_stage_success(self, tmp_path):
        stages = [TriggerStage(stage_index=0, trigger_method="file_created", trigger_config={})]
        stopped = threading.Event()

        with patch("lamia.triggers.local.orchestrator._spawn_stage", return_value=0):
            _handle_execution(
                script_path=Path("test.lm"),
                stages=stages,
                trigger_id="test-1234",
                initial_event={"name": "report.pdf"},
                stopped=stopped,
            )

        assert registry.list_executions("test-1234") == []

    def test_single_stage_reject(self, tmp_path):
        stages = [TriggerStage(stage_index=0, trigger_method="file_created", trigger_config={})]
        stopped = threading.Event()

        with patch("lamia.triggers.local.orchestrator._spawn_stage", return_value=EXIT_CODE_REJECT):
            _handle_execution(
                script_path=Path("test.lm"),
                stages=stages,
                trigger_id="test-1234",
                initial_event={"name": "wrong.txt"},
                stopped=stopped,
            )

        assert registry.list_executions("test-1234") == []
        assert registry.get_failed_events("test-1234") == []

    def test_continuation_timeout_records_failed_event(self, tmp_path):
        """Issue #7: When stage N (N>=1) times out waiting for continuation, the
        initial event must land in failed_events so it's not silently dropped."""
        stages = [
            TriggerStage(stage_index=0, trigger_method="file_created", trigger_config={}),
            TriggerStage(stage_index=1, trigger_method="email_received", trigger_config={}),
        ]
        stopped = threading.Event()

        with patch("lamia.triggers.local.orchestrator._spawn_stage", return_value=0), \
             patch("lamia.triggers.local.orchestrator._wait_for_continuation", return_value=None):
            _handle_execution(
                script_path=Path("test.lm"),
                stages=stages,
                trigger_id="test-timeout",
                initial_event={"name": "starter.pdf"},
                stopped=stopped,
            )

        failed = registry.get_failed_events("test-timeout")
        assert len(failed) == 1, f"expected 1 failed event, got {len(failed)}"
        assert failed[0]["payload"] == {"name": "starter.pdf"}
        assert "timeout" in failed[0]["error"].lower()
