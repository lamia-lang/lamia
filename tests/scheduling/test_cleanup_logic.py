"""Tests for local registry cleanup business logic.

Covers edge cases in SOURCE_MISSING detection and --orphaned removal.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lamia.id_gen import generate_unique_id
from lamia.scheduling.base import ScheduleJob
from lamia.scheduling.registry import (
    SCHEDULES_DIR,
    list_jobs,
    save_job,
    remove_job,
)


@pytest.fixture
def temp_schedules_dir(tmp_path, monkeypatch):
    fake_dir = tmp_path / "schedules"
    fake_dir.mkdir()
    monkeypatch.setattr("lamia.scheduling.registry.SCHEDULES_DIR", fake_dir)
    return fake_dir


class TestCloudScheduleNotMarkedMissing:
    """Cloud-backend schedules should never be marked SOURCE_MISSING
    based on local filesystem checks."""

    def test_cloud_backend_not_marked_source_missing(self, temp_schedules_dir):
        entry = temp_schedules_dir / "cloud-abc123.json"
        entry.write_text(json.dumps({
            "id": "cloud-abc123",
            "script": "daily_task.lm",
            "cron": "0 9 * * *",
            "catch_up": False,
            "project_root": "/Users/original-dev/project",
            "lamia_bin": "/usr/local/bin/lamia",
            "backend": "cloud",
        }))

        jobs = list_jobs()
        assert len(jobs) == 1
        assert jobs[0]["source_missing"] is False


class TestRemoveOrphanedSkipsCloudEntries:
    """remove --orphaned must never touch cloud-backend entries."""

    def test_does_not_uninstall_cloud_schedule(
        self, temp_schedules_dir, monkeypatch
    ):
        entry = temp_schedules_dir / "cloud-xyz789.json"
        entry.write_text(json.dumps({
            "id": "cloud-xyz789",
            "script": "analytics.lm",
            "cron": "0 */6 * * *",
            "catch_up": False,
            "project_root": "/Users/teammate/analytics-project",
            "lamia_bin": "/usr/local/bin/lamia",
            "backend": "cloud",
        }))

        mock_scheduler = MagicMock()
        monkeypatch.setattr(
            "lamia.scheduling.cli._scheduler_for_job",
            lambda *a: mock_scheduler,
        )
        monkeypatch.setattr(
            "lamia.scheduling.cli.remove_job",
            lambda x: True,
        )

        from lamia.scheduling.cli import _handle_remove_orphaned
        _handle_remove_orphaned()

        mock_scheduler.uninstall.assert_not_called()

    def test_does_not_delete_cloud_cache_entry(self, temp_schedules_dir):
        entry = temp_schedules_dir / "cloud-xyz789.json"
        entry.write_text(json.dumps({
            "id": "cloud-xyz789",
            "script": "analytics.lm",
            "cron": "0 */6 * * *",
            "catch_up": False,
            "project_root": "/Users/teammate/analytics-project",
            "lamia_bin": "/usr/local/bin/lamia",
            "backend": "cloud",
        }))

        mock_scheduler = MagicMock()

        with patch("lamia.scheduling.cli._scheduler_for_job", return_value=mock_scheduler):
            from lamia.scheduling.cli import _handle_remove_orphaned
            _handle_remove_orphaned()

        assert entry.exists()


class TestRecentlyActiveScheduleProtected:
    """remove --orphaned should skip entries that ran recently, even if failing."""

    def test_recently_successful_not_removed(self, temp_schedules_dir, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        script = project / "task.lm"
        script.write_text("print('ok')")

        job = ScheduleJob(
            script="task.lm", cron="0 9 * * *",
            schedule_id=generate_unique_id(),
            project_root=project,
        )
        job_id = save_job(job, "/bin/lamia")

        from lamia.scheduling.registry import record_run
        record_run(job_id, exit_code=0)

        script.unlink()

        from lamia.scheduling.cli import _handle_remove_orphaned
        mock_scheduler = MagicMock()
        with patch("lamia.scheduling.cli._scheduler_for_job", return_value=mock_scheduler):
            _handle_remove_orphaned()

        assert (temp_schedules_dir / f"{job_id}.json").exists()

    def test_recently_failing_not_removed(self, temp_schedules_dir, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        script = project / "task.lm"
        script.write_text("print('ok')")

        job = ScheduleJob(
            script="task.lm", cron="0 9 * * *",
            schedule_id=generate_unique_id(),
            project_root=project,
        )
        job_id = save_job(job, "/bin/lamia")

        from lamia.scheduling.registry import record_run
        record_run(job_id, exit_code=1, error="script not found")

        script.unlink()

        from lamia.scheduling.cli import _handle_remove_orphaned
        mock_scheduler = MagicMock()
        with patch("lamia.scheduling.cli._scheduler_for_job", return_value=mock_scheduler):
            _handle_remove_orphaned()

        assert (temp_schedules_dir / f"{job_id}.json").exists()


class TestLocalRegistryPersistence:
    """Local entries are never auto-removed — clutter over data loss."""

    def test_stale_entries_persist_after_list(self, temp_schedules_dir, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        script = project / "old.lm"
        script.write_text("print('old')")

        job = ScheduleJob(
            script="old.lm", cron="0 0 * * *",
            schedule_id=generate_unique_id(),
            project_root=project,
        )
        job_id = save_job(job, "/bin/lamia")

        script.unlink()

        list_jobs()
        list_jobs()
        list_jobs()

        assert (temp_schedules_dir / f"{job_id}.json").exists()
