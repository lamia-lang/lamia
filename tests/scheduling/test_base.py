"""Tests for lamia.scheduling.base module."""

from pathlib import Path

import pytest

from lamia.scheduling.base import BaseScheduler, JobStatus, ScheduleJob, generate_schedule_id


class TestGenerateScheduleId:
    def test_produces_12_char_hex(self):
        result = generate_schedule_id("script.lm", "/home/user/project")
        assert len(result) == 12
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic(self):
        a = generate_schedule_id("x.lm", "/p")
        b = generate_schedule_id("x.lm", "/p")
        assert a == b

    def test_different_scripts_different_ids(self):
        a = generate_schedule_id("a.lm", "/p")
        b = generate_schedule_id("b.lm", "/p")
        assert a != b

    def test_different_roots_different_ids(self):
        a = generate_schedule_id("a.lm", "/p1")
        b = generate_schedule_id("a.lm", "/p2")
        assert a != b


class TestScheduleJob:
    def test_label_uses_schedule_id(self):
        job = ScheduleJob(
            script="daily_task.lm", cron="0 9 * * *",
            schedule_id="abc123def456",
            project_root=Path("/p"),
        )
        assert job.label == "com.lamia.schedule.abc123def456"

    def test_defaults(self):
        job = ScheduleJob(script="x.lm", cron="* * * * *", schedule_id="test_id_1234")
        assert job.catch_up is True
        assert job.project_root == Path()

    def test_schedule_id_is_stored_field(self):
        sid = generate_schedule_id("task.lm", "/project")
        job = ScheduleJob(script="task.lm", cron="0 0 * * *", schedule_id=sid, project_root=Path("/project"))
        assert job.schedule_id == sid


class TestJobStatus:
    def test_status_values(self):
        assert JobStatus.ACTIVE.value == "active"
        assert JobStatus.INACTIVE.value == "inactive"
        assert JobStatus.UNKNOWN.value == "unknown"


class TestBaseScheduler:
    def test_name_not_implemented(self):
        with pytest.raises(NotImplementedError):
            BaseScheduler.name()

    def test_install_not_implemented(self):
        s = BaseScheduler()
        job = ScheduleJob(script="x.lm", cron="0 0 * * *", schedule_id="test_id_0000")
        with pytest.raises(NotImplementedError):
            s.install(job, "/usr/bin/lamia")

    def test_uninstall_not_implemented(self):
        s = BaseScheduler()
        job = ScheduleJob(script="x.lm", cron="0 0 * * *", schedule_id="test_id_0000")
        with pytest.raises(NotImplementedError):
            s.uninstall(job)

    def test_is_installed_not_implemented(self):
        s = BaseScheduler()
        job = ScheduleJob(script="x.lm", cron="0 0 * * *", schedule_id="test_id_0000")
        with pytest.raises(NotImplementedError):
            s.is_installed(job)

    def test_get_status_not_implemented(self):
        s = BaseScheduler()
        job = ScheduleJob(script="x.lm", cron="0 0 * * *", schedule_id="test_id_0000")
        with pytest.raises(NotImplementedError):
            s.get_status(job)
