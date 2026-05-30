"""Tests for lamia.scheduling.base module."""

from pathlib import Path

import pytest

from lamia.scheduling.base import BaseScheduler, JobStatus, ScheduleJob


class TestScheduleJob:
    def test_job_id_is_stable(self):
        job = ScheduleJob(
            script="daily_task.lm",
            cron="0 9 * * *",
            project_root=Path("/home/user/project"),
        )
        assert job.job_id == job.job_id

    def test_job_id_differs_for_different_scripts(self):
        job1 = ScheduleJob(script="a.lm", cron="0 9 * * *", project_root=Path("/p"))
        job2 = ScheduleJob(script="b.lm", cron="0 9 * * *", project_root=Path("/p"))
        assert job1.job_id != job2.job_id

    def test_job_id_differs_for_different_roots(self):
        job1 = ScheduleJob(script="a.lm", cron="0 9 * * *", project_root=Path("/p1"))
        job2 = ScheduleJob(script="a.lm", cron="0 9 * * *", project_root=Path("/p2"))
        assert job1.job_id != job2.job_id

    def test_label_format(self):
        job = ScheduleJob(script="daily_task.lm", cron="0 9 * * *", project_root=Path("/p"))
        assert job.label == "com.lamia.schedule.daily_task"

    def test_label_with_subdirectory(self):
        job = ScheduleJob(script="scripts/daily.lm", cron="0 9 * * *", project_root=Path("/p"))
        assert job.label == "com.lamia.schedule.scripts.daily"

    def test_defaults(self):
        job = ScheduleJob(script="x.lm", cron="* * * * *")
        assert job.catch_up is True
        assert job.project_root == Path()


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
        job = ScheduleJob(script="x.lm", cron="0 0 * * *")
        with pytest.raises(NotImplementedError):
            s.install(job, "/usr/bin/lamia")

    def test_uninstall_not_implemented(self):
        s = BaseScheduler()
        job = ScheduleJob(script="x.lm", cron="0 0 * * *")
        with pytest.raises(NotImplementedError):
            s.uninstall(job)

    def test_is_installed_not_implemented(self):
        s = BaseScheduler()
        job = ScheduleJob(script="x.lm", cron="0 0 * * *")
        with pytest.raises(NotImplementedError):
            s.is_installed(job)

    def test_get_status_not_implemented(self):
        s = BaseScheduler()
        job = ScheduleJob(script="x.lm", cron="0 0 * * *")
        with pytest.raises(NotImplementedError):
            s.get_status(job)
