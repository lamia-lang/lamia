"""Tests for lamia.triggers.local.registry — local trigger state persistence."""

import json
import threading

import pytest

from lamia.triggers.local import registry


class TestThreadSafety:
    """Issue #3: concurrent read-modify-write on registry JSON files must not lose entries."""

    def test_concurrent_append_failed_event_no_lost_writes(self):
        trigger_id = "concurrent-fail-1"
        n_threads = 12
        per_thread = 20
        expected = n_threads * per_thread
        barrier = threading.Barrier(n_threads)

        def worker(t_idx):
            barrier.wait()  # maximize contention
            for i in range(per_thread):
                registry.append_failed_event(trigger_id, {"t": t_idx, "i": i}, "err")

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        events = registry.get_failed_events(trigger_id)
        assert len(events) == expected, (
            f"lost writes under contention: got {len(events)} of {expected} "
            f"({expected - len(events)} lost)"
        )

    def test_concurrent_save_active_trigger_no_lost_entries(self):
        n_threads = 12
        barrier = threading.Barrier(n_threads)

        def worker(t_idx):
            barrier.wait()
            registry.save_active_trigger(
                f"trig-{t_idx:02d}", f"s{t_idx}.lm", "/proj", "reactive", 1000 + t_idx,
            )

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        entries = registry.list_active_triggers()
        ids = {e["id"] for e in entries}
        expected_ids = {f"trig-{t:02d}" for t in range(n_threads)}
        assert ids == expected_ids, (
            f"lost active triggers: missing {expected_ids - ids}, extra {ids - expected_ids}"
        )


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    """Point registry at a temp directory instead of ~/.lamia/triggers."""
    monkeypatch.setattr(registry, "TRIGGERS_DIR", tmp_path)


class TestActiveTriggersLifecycle:
    def test_empty_by_default(self):
        assert registry.list_active_triggers() == []

    def test_save_and_list(self):
        registry.save_active_trigger("pricing-a3f2", "pricing.lm", "/proj", "reactive", 1234)

        entries = registry.list_active_triggers()
        assert len(entries) == 1
        assert entries[0]["id"] == "pricing-a3f2"
        assert entries[0]["pid"] == 1234

    def test_save_replaces_existing(self):
        registry.save_active_trigger("pricing-a3f2", "pricing.lm", "/proj", "reactive", 1234)
        registry.save_active_trigger("pricing-a3f2", "pricing.lm", "/proj", "reactive", 5678)

        entries = registry.list_active_triggers()
        assert len(entries) == 1
        assert entries[0]["pid"] == 5678

    def test_remove(self):
        registry.save_active_trigger("pricing-a3f2", "pricing.lm", "/proj", "reactive", 1234)
        assert registry.remove_active_trigger("pricing-a3f2") is True
        assert registry.list_active_triggers() == []

    def test_remove_nonexistent_returns_false(self):
        assert registry.remove_active_trigger("nope") is False

    def test_get_active_trigger(self):
        registry.save_active_trigger("abc-1234", "abc.lm", "/x", "scheduled", 99)
        entry = registry.get_active_trigger("abc-1234")
        assert entry is not None
        assert entry["script"] == "abc.lm"

    def test_get_active_trigger_returns_none_when_missing(self):
        assert registry.get_active_trigger("nope") is None


class TestFailedEvents:
    def test_empty_by_default(self):
        assert registry.get_failed_events("pricing-a3f2") == []

    def test_append_and_get(self):
        registry.append_failed_event("pricing-a3f2", {"sender": "x@y.com"}, "timeout")
        events = registry.get_failed_events("pricing-a3f2")
        assert len(events) == 1
        assert events[0]["payload"]["sender"] == "x@y.com"
        assert events[0]["error"] == "timeout"
        assert "timestamp" in events[0]

    def test_clear(self):
        registry.append_failed_event("pricing-a3f2", {"a": 1}, "err1")
        registry.append_failed_event("pricing-a3f2", {"b": 2}, "err2")
        count = registry.clear_failed_events("pricing-a3f2")
        assert count == 2
        assert registry.get_failed_events("pricing-a3f2") == []

    def test_clear_returns_zero_when_empty(self):
        assert registry.clear_failed_events("pricing-a3f2") == 0


class TestExecutionState:
    def test_save_and_get(self):
        state = {"exec_id": "abc123", "current_stage": 1, "deadline": "2026-07-10T10:00:00Z"}
        registry.save_execution("pricing-a3f2", "abc123", state)
        loaded = registry.get_execution("pricing-a3f2", "abc123")
        assert loaded == state

    def test_get_nonexistent_returns_none(self):
        assert registry.get_execution("pricing-a3f2", "nope") is None

    def test_remove_execution(self):
        registry.save_execution("pricing-a3f2", "abc123", {"exec_id": "abc123"})
        registry.remove_execution("pricing-a3f2", "abc123")
        assert registry.get_execution("pricing-a3f2", "abc123") is None

    def test_list_executions(self):
        registry.save_execution("pricing-a3f2", "aaa", {"exec_id": "aaa"})
        registry.save_execution("pricing-a3f2", "bbb", {"exec_id": "bbb"})
        results = registry.list_executions("pricing-a3f2")
        assert len(results) == 2
        ids = {r["exec_id"] for r in results}
        assert ids == {"aaa", "bbb"}

    def test_list_executions_empty(self):
        assert registry.list_executions("nonexistent") == []


class TestSeenMessages:
    def test_empty_by_default(self):
        assert registry.get_seen_message_ids("pricing-a3f2") == set()

    def test_add_and_get(self):
        registry.add_seen_message_id("pricing-a3f2", "msg1")
        registry.add_seen_message_id("pricing-a3f2", "msg2")
        ids = registry.get_seen_message_ids("pricing-a3f2")
        assert ids == {"msg1", "msg2"}

    def test_no_duplicates(self):
        registry.add_seen_message_id("pricing-a3f2", "msg1")
        registry.add_seen_message_id("pricing-a3f2", "msg1")
        ids = registry.get_seen_message_ids("pricing-a3f2")
        assert len(ids) == 1
