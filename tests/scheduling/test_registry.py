"""Tests for lamia.scheduling.registry module."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from lamia.id_gen import generate_unique_id
from lamia.scheduling.base import ScheduleJob
from lamia.scheduling.registry import (
    SCHEDULES_DIR,
    find_job_by_script,
    get_last_run_status,
    list_jobs,
    load_job,
    record_run,
    remove_job,
    save_job,
)


@pytest.fixture
def temp_schedules_dir(tmp_path, monkeypatch):
    """Redirect SCHEDULES_DIR to a temp directory for isolated tests."""
    fake_dir = tmp_path / "schedules"
    fake_dir.mkdir()
    monkeypatch.setattr("lamia.scheduling.registry.SCHEDULES_DIR", fake_dir)
    return fake_dir


class TestGenerateId:
    def test_twelve_char_hex(self):
        result = generate_unique_id("script.lm", "/home/user/project")
        assert len(result) == 12
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic(self):
        a = generate_unique_id("x.lm", "/p")
        b = generate_unique_id("x.lm", "/p")
        assert a == b

    def test_different_inputs_different_ids(self):
        a = generate_unique_id("x.lm", "/p")
        b = generate_unique_id("y.lm", "/p")
        assert a != b


class TestSaveAndLoadJob:
    def test_save_creates_file(self, temp_schedules_dir):
        job = ScheduleJob(
            script="test.lm",
            cron="0 9 * * *",
            schedule_id=generate_unique_id("test.lm", "/home/user/myproject"),
            catch_up=True,
            project_root=Path("/home/user/myproject"),
        )
        job_id = save_job(job, "/usr/local/bin/lamia")
        assert (temp_schedules_dir / f"{job_id}.json").exists()

    def test_load_returns_saved_data(self, temp_schedules_dir):
        job = ScheduleJob(
            script="test.lm",
            cron="0 9 * * *",
            schedule_id=generate_unique_id("test.lm", "/home/user/myproject"),
            catch_up=False,
            project_root=Path("/home/user/myproject"),
        )
        job_id = save_job(job, "/usr/local/bin/lamia")
        loaded = load_job(job_id)

        assert loaded is not None
        assert loaded["script"] == "test.lm"
        assert loaded["cron"] == "0 9 * * *"
        assert loaded["catch_up"] is False
        assert loaded["project_root"] == "/home/user/myproject"
        assert loaded["lamia_bin"] == "/usr/local/bin/lamia"

    def test_load_nonexistent_returns_none(self, temp_schedules_dir):
        assert load_job("nonexistent_id") is None

    def test_load_corrupted_file_returns_none(self, temp_schedules_dir):
        bad_file = temp_schedules_dir / "badid123456.json"
        bad_file.write_text("not valid json{{{")
        assert load_job("badid123456") is None


class TestRemoveJob:
    def test_remove_existing(self, temp_schedules_dir):
        job = ScheduleJob(
            script="r.lm", cron="0 0 * * *",
            schedule_id=generate_unique_id("r.lm", "/p"),
            project_root=Path("/p"),
        )
        job_id = save_job(job, "/bin/lamia")
        assert remove_job(job_id) is True
        assert not (temp_schedules_dir / f"{job_id}.json").exists()

    def test_remove_nonexistent_returns_false(self, temp_schedules_dir):
        assert remove_job("does_not_exist") is False


class TestListJobs:
    def test_empty_directory(self, temp_schedules_dir):
        assert list_jobs() == []

    def test_lists_all_saved_jobs(self, temp_schedules_dir):
        job1 = ScheduleJob(
            script="a.lm", cron="0 1 * * *",
            schedule_id=generate_unique_id("a.lm", "/p1"),
            project_root=Path("/p1"),
        )
        job2 = ScheduleJob(
            script="b.lm", cron="0 2 * * *",
            schedule_id=generate_unique_id("b.lm", "/p2"),
            project_root=Path("/p2"),
        )
        save_job(job1, "/bin/lamia")
        save_job(job2, "/bin/lamia")
        jobs = list_jobs()
        assert len(jobs) == 2
        scripts = {j["script"] for j in jobs}
        assert scripts == {"a.lm", "b.lm"}

    def test_skips_corrupted_files(self, temp_schedules_dir):
        job = ScheduleJob(
            script="good.lm", cron="0 0 * * *",
            schedule_id=generate_unique_id("good.lm", "/p"),
            project_root=Path("/p"),
        )
        save_job(job, "/bin/lamia")
        (temp_schedules_dir / "corrupt.json").write_text("{{bad")
        jobs = list_jobs()
        assert len(jobs) == 1
        assert jobs[0]["script"] == "good.lm"

    def test_migrates_legacy_entry_without_id(self, temp_schedules_dir):
        legacy_path = temp_schedules_dir / "com.lamia.schedule.legacy.json"
        legacy_path.write_text(
            json.dumps(
                {
                    "script": "legacy_task.lm",
                    "cron": "0 9 * * *",
                    "timezone": "UTC",
                    "catch_up": True,
                    "project_root": "/legacy/project",
                    "lamia_bin": "/usr/local/bin/lamia",
                }
            )
        )

        jobs = list_jobs()
        assert len(jobs) == 1
        assert jobs[0]["script"] == "legacy_task.lm"
        assert "id" in jobs[0]

        canonical = temp_schedules_dir / f"{jobs[0]['id']}.json"
        assert canonical.exists()
        assert not legacy_path.exists()

    def test_deduplicates_same_job_id(self, temp_schedules_dir):
        job = ScheduleJob(
            script="dup_task.lm", cron="0 9 * * *",
            schedule_id=generate_unique_id("dup_task.lm", "/dup/project"),
            project_root=Path("/dup/project"),
        )
        job_id = save_job(job, "/usr/local/bin/lamia")
        legacy_path = temp_schedules_dir / "com.lamia.schedule.dup_task.json"
        legacy_path.write_text(
            json.dumps(
                {
                    "script": "dup_task.lm",
                    "cron": "0 9 * * *",
                    "timezone": "UTC",
                    "catch_up": True,
                    "project_root": "/dup/project",
                    "lamia_bin": "/usr/local/bin/lamia",
                }
            )
        )

        jobs = list_jobs()
        assert len(jobs) == 1
        assert jobs[0]["id"] == job_id


class TestFindJobByScript:
    def test_finds_existing(self, temp_schedules_dir):
        job = ScheduleJob(
            script="find_me.lm", cron="0 5 * * *",
            schedule_id=generate_unique_id("find_me.lm", "/proj"),
            project_root=Path("/proj"),
        )
        save_job(job, "/bin/lamia")
        found = find_job_by_script("find_me.lm", "/proj")
        assert found is not None
        assert found["script"] == "find_me.lm"

    def test_not_found_returns_none(self, temp_schedules_dir):
        assert find_job_by_script("nope.lm", "/nowhere") is None


class TestRunStatus:
    def test_record_and_get_success(self, temp_schedules_dir):
        job = ScheduleJob(
            script="test.lm", cron="0 0 * * *",
            schedule_id="testjob12345",
            project_root=Path("/p"),
        )
        save_job(job, "/bin/lamia")
        record_run("testjob12345", exit_code=0)
        status = get_last_run_status("testjob12345")
        assert status is not None
        assert status["success"] is True
        assert status["exit_code"] == 0
        assert "timestamp" in status

    def test_record_and_get_failure(self, temp_schedules_dir):
        job = ScheduleJob(
            script="fail.lm", cron="0 0 * * *",
            schedule_id="failjob12345",
            project_root=Path("/p"),
        )
        save_job(job, "/bin/lamia")
        record_run("failjob12345", exit_code=1, error="script not found")
        status = get_last_run_status("failjob12345")
        assert status is not None
        assert status["success"] is False
        assert status["exit_code"] == 1
        assert status["error"] == "script not found"

    def test_get_status_nonexistent(self, temp_schedules_dir):
        assert get_last_run_status("nope") is None

    def test_list_jobs_includes_last_run(self, temp_schedules_dir):
        job = ScheduleJob(
            script="tracked.lm", cron="0 0 * * *",
            schedule_id=generate_unique_id("tracked.lm", "/p"),
            project_root=Path("/p"),
        )
        job_id = save_job(job, "/bin/lamia")
        record_run(job_id, exit_code=0)
        jobs = list_jobs()
        assert len(jobs) == 1
        assert "last_run" in jobs[0]
        assert jobs[0]["last_run"]["success"] is True

    def test_remove_job_also_removes_status(self, temp_schedules_dir):
        job = ScheduleJob(
            script="bye.lm", cron="0 0 * * *",
            schedule_id=generate_unique_id("bye.lm", "/p"),
            project_root=Path("/p"),
        )
        job_id = save_job(job, "/bin/lamia")
        record_run(job_id, exit_code=0)
        remove_job(job_id)
        assert get_last_run_status(job_id) is None


class TestAtomicWrite:
    def test_writes_content(self, tmp_path):
        target = tmp_path / "out.json"
        atomic_write(target, '{"key": "value"}')
        assert json.loads(target.read_text()) == {"key": "value"}

    def test_overwrites_existing(self, tmp_path):
        target = tmp_path / "out.json"
        target.write_text('{"old": true}')
        atomic_write(target, '{"new": true}')
        assert json.loads(target.read_text()) == {"new": True}

    def test_no_leftover_temp_files(self, tmp_path):
        target = tmp_path / "out.json"
        atomic_write(target, "hello")
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == []

    def test_record_run_preserves_job_fields(self, temp_schedules_dir):
        job = ScheduleJob(
            script="atomic.lm", cron="0 0 * * *",
            schedule_id="atomic-test1",
            project_root=Path("/p"),
        )
        save_job(job, "/bin/lamia")
        record_run("atomic-test1", exit_code=0)
        data = load_job("atomic-test1")
        assert data is not None
        assert data["script"] == "atomic.lm"
        assert data["last_run"]["success"] is True
