"""Tests for lamia.triggers.local.event_sources.file_watcher — FileEventSource."""

import os
import time

import pytest

pytest.importorskip("watchdog", reason="watchdog not installed")

from lamia.triggers.local.event_sources.file_watcher import FileEventSource


class TestFileEventSource:
    def test_invalid_trigger_method_raises(self):
        with pytest.raises(ValueError, match="Unsupported file trigger"):
            FileEventSource("webhook_received")

    def test_start_raises_if_path_missing(self, tmp_path):
        """A misconfigured trigger path must fail loudly, not silently create it."""
        watch_dir = tmp_path / "does_not_exist"
        source = FileEventSource("file_created")
        with pytest.raises(FileNotFoundError, match="does_not_exist"):
            source.start({"path": str(watch_dir)})
        assert not watch_dir.exists(), "should not have created the missing path"

    def test_start_raises_if_path_is_a_file(self, tmp_path):
        """Watching a file (not a directory) must error, not silently proceed."""
        f = tmp_path / "not_a_dir.txt"
        f.write_text("x")
        source = FileEventSource("file_created")
        with pytest.raises(NotADirectoryError, match="not_a_dir.txt"):
            source.start({"path": str(f)})

    def test_wait_for_event_returns_none_on_timeout(self, tmp_path):
        source = FileEventSource("file_created")
        source.start({"path": str(tmp_path)})
        try:
            result = source.wait_for_event(timeout_seconds=1)
            assert result is None
        finally:
            source.stop()

    def test_detects_file_created(self, tmp_path):
        source = FileEventSource("file_created")
        source.start({"path": str(tmp_path)})
        try:
            time.sleep(0.3)
            test_file = tmp_path / "hello.txt"
            test_file.write_text("hi")

            result = source.wait_for_event(timeout_seconds=5)
            assert result is not None
            assert result["name"] == "hello.txt"
            assert "timestamp" in result
            assert result["metadata"]["path"] == str(test_file)
        finally:
            source.stop()

    def test_detects_file_modified(self, tmp_path):
        test_file = tmp_path / "existing.txt"
        test_file.write_text("original")

        source = FileEventSource("file_modified")
        source.start({"path": str(tmp_path)})
        try:
            time.sleep(0.3)
            test_file.write_text("modified content")

            result = source.wait_for_event(timeout_seconds=5)
            assert result is not None
            assert result["name"] == "existing.txt"
        finally:
            source.stop()

    def test_detects_file_deleted(self, tmp_path):
        test_file = tmp_path / "doomed.txt"
        test_file.write_text("bye")

        source = FileEventSource("file_deleted")
        source.start({"path": str(tmp_path)})
        try:
            time.sleep(0.3)
            test_file.unlink()

            result = source.wait_for_event(timeout_seconds=5)
            assert result is not None
            assert result["name"] == "doomed.txt"
        finally:
            source.stop()

    def test_ignores_directory_events(self, tmp_path):
        source = FileEventSource("file_created")
        source.start({"path": str(tmp_path)})
        try:
            time.sleep(0.3)
            (tmp_path / "subdir").mkdir()
            result = source.wait_for_event(timeout_seconds=1)
            assert result is None
        finally:
            source.stop()

    def test_stop_is_idempotent(self, tmp_path):
        source = FileEventSource("file_created")
        source.start({"path": str(tmp_path)})
        source.stop()
        source.stop()
