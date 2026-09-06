"""Tests for lamia.scheduling.local_scheduler module."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from lamia.id_gen import generate_unique_id
from lamia.scheduling.base import ScheduleJob
from lamia.scheduling.local_scheduler import (
    LaunchdScheduler,
    LocalScheduler,
    SystemdScheduler,
    WindowsTaskScheduler,
    _expand_cron_field,
    _parse_cron_fields,
)


class TestParseCronFields:
    def test_valid_expression(self):
        result = _parse_cron_fields("0 9 * * *")
        assert result == {
            "minute": "0",
            "hour": "9",
            "day": "*",
            "month": "*",
            "weekday": "*",
        }

    def test_all_stars(self):
        result = _parse_cron_fields("* * * * *")
        assert all(v == "*" for v in result.values())

    def test_specific_values(self):
        result = _parse_cron_fields("30 14 1 6 3")
        assert result == {
            "minute": "30",
            "hour": "14",
            "day": "1",
            "month": "6",
            "weekday": "3",
        }

    def test_invalid_field_count_raises(self):
        with pytest.raises(ValueError, match="expected 5 fields"):
            _parse_cron_fields("0 9 *")

    def test_too_many_fields_raises(self):
        with pytest.raises(ValueError, match="expected 5 fields"):
            _parse_cron_fields("0 9 * * * *")

    def test_step_expression_is_valid(self):
        result = _parse_cron_fields("*/5 * * * *")
        assert result["minute"] == "*/5"


class TestExpandCronField:
    def test_star_returns_none(self):
        assert _expand_cron_field("*", 0, 59, "minute") is None

    def test_single_value(self):
        assert _expand_cron_field("30", 0, 59, "minute") == [30]

    def test_range(self):
        assert _expand_cron_field("9-11", 0, 23, "hour") == [9, 10, 11]

    def test_step(self):
        assert _expand_cron_field("*/5", 0, 59, "minute") == [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]

    def test_range_with_step(self):
        assert _expand_cron_field("0-20/10", 0, 59, "minute") == [0, 10, 20]

    def test_comma_list(self):
        assert _expand_cron_field("1,3,5", 0, 7, "weekday") == [1, 3, 5]

    def test_out_of_range_raises(self):
        with pytest.raises(ValueError, match="out of range"):
            _expand_cron_field("99", 0, 59, "minute")

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError, match="Invalid minute value"):
            _expand_cron_field("abc", 0, 59, "minute")

    def test_zero_step_raises(self):
        with pytest.raises(ValueError, match="Invalid minute step"):
            _expand_cron_field("*/0", 0, 59, "minute")


class TestLaunchdScheduler:
    @pytest.fixture
    def scheduler(self):
        return LaunchdScheduler()

    @pytest.fixture
    def job(self):
        sid = generate_unique_id()
        return ScheduleJob(
            script="daily_task.lm",
            cron="0 9 * * *",
            schedule_id=sid,
            project_root=Path("/Users/test/project"),
        )

    def test_plist_path(self, scheduler, job):
        path = scheduler._plist_path(job)
        assert path.name == f"com.lamia.schedule.{job.schedule_id}.plist"
        assert "LaunchAgents" in str(path)

    def test_build_plist_contains_label(self, scheduler, job, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        (tmp_path / ".lamia" / "logs").mkdir(parents=True)
        plist = scheduler._build_plist(job, "/usr/local/bin/lamia")
        assert f"com.lamia.schedule.{job.schedule_id}" in plist

    def test_build_plist_contains_script_path(self, scheduler, job, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        (tmp_path / ".lamia" / "logs").mkdir(parents=True)
        plist = scheduler._build_plist(job, "/usr/local/bin/lamia")
        assert "/Users/test/project/daily_task.lm" in plist

    def test_build_plist_contains_log_file_arg(self, scheduler, job, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        (tmp_path / ".lamia" / "logs").mkdir(parents=True)
        plist = scheduler._build_plist(job, "/usr/local/bin/lamia")
        assert "--log-file" in plist
        assert "/.lamia/logs/schedules/" in plist
        assert "/schedule.log" in plist

    def test_build_plist_uses_start_calendar_interval(self, scheduler, job, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        (tmp_path / ".lamia" / "logs").mkdir(parents=True)
        plist = scheduler._build_plist(job, "/usr/local/bin/lamia")
        assert "<key>StartCalendarInterval</key>" in plist
        assert "StartInterval" not in plist
        assert "<key>Hour</key>" in plist
        assert "<key>Minute</key>" in plist

    def test_build_plist_catch_up_adds_run_at_load(self, scheduler, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        (tmp_path / ".lamia" / "logs").mkdir(parents=True)
        job = ScheduleJob(
            script="daily_task.lm",
            cron="0 9 * * *",
            schedule_id="test_catchup_1",
            catch_up=True,
            project_root=Path("/Users/test/project"),
        )
        plist = scheduler._build_plist(job, "/usr/local/bin/lamia")
        assert "<key>RunAtLoad</key>" in plist
        assert "<key>StartCalendarInterval</key>" in plist

    def test_build_plist_no_catch_up_omits_run_at_load(self, scheduler, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        (tmp_path / ".lamia" / "logs").mkdir(parents=True)
        job = ScheduleJob(
            script="daily_task.lm",
            cron="0 9 * * *",
            schedule_id="test_no_catchup",
            catch_up=False,
            project_root=Path("/Users/test/project"),
        )
        plist = scheduler._build_plist(job, "/usr/local/bin/lamia")
        assert "<key>RunAtLoad</key>" not in plist

    def test_cron_to_calendar_intervals_all_stars(self, scheduler):
        cron = {"minute": "*", "hour": "*", "day": "*", "month": "*", "weekday": "*"}
        intervals = scheduler._cron_to_calendar_intervals(cron)
        assert intervals == [[]]

    def test_cron_to_calendar_intervals_specific(self, scheduler):
        cron = {"minute": "30", "hour": "14", "day": "*", "month": "*", "weekday": "1"}
        intervals = scheduler._cron_to_calendar_intervals(cron)
        assert len(intervals) == 1
        lines = intervals[0]
        assert any("Minute" in l and "30" in l for l in lines)
        assert any("Hour" in l and "14" in l for l in lines)
        assert any("Weekday" in l and "1" in l for l in lines)

    def test_cron_to_calendar_intervals_step_expands_to_multiple_entries(self, scheduler):
        cron = {"minute": "*/5", "hour": "*", "day": "*", "month": "*", "weekday": "*"}
        intervals = scheduler._cron_to_calendar_intervals(cron)
        minutes = sorted(int(lines[0].split("<integer>")[1].split("<")[0]) for lines in intervals)
        assert minutes == [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]

    def test_build_plist_step_cron_uses_array(self, scheduler, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        (tmp_path / ".lamia" / "logs").mkdir(parents=True)
        job = ScheduleJob(
            script="probe.lm",
            cron="*/5 * * * *",
            schedule_id="test_step_cron",
            project_root=Path("/Users/test/project"),
        )
        plist = scheduler._build_plist(job, "/usr/local/bin/lamia")
        assert "<key>StartCalendarInterval</key>" in plist
        assert "<array>" in plist
        assert plist.count("<key>Minute</key><integer>") == 12

    def test_build_plist_on_wake_uses_run_at_load(self, scheduler, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        (tmp_path / ".lamia" / "logs").mkdir(parents=True)
        job = ScheduleJob(
            script="wake.lm",
            cron="@reboot",
            schedule_id="test_wake_id",
            project_root=Path("/Users/test/project"),
        )
        plist = scheduler._build_plist(job, "/usr/local/bin/lamia")
        assert "<key>RunAtLoad</key>" in plist
        assert "StartCalendarInterval" not in plist


class TestSystemdScheduler:
    @pytest.fixture
    def scheduler(self):
        return SystemdScheduler()

    def test_service_name(self, scheduler):
        job = ScheduleJob(script="daily.lm", cron="0 0 * * *", schedule_id="abc123def456", project_root=Path("/p"))
        assert scheduler._service_name(job) == "lamia-abc123def456"

    def test_service_name_with_path(self, scheduler):
        job = ScheduleJob(script="scripts/run.lm", cron="0 0 * * *", schedule_id="xyz789aaa111", project_root=Path("/p"))
        assert scheduler._service_name(job) == "lamia-xyz789aaa111"

    def test_cron_to_oncalendar_daily_9am(self, scheduler):
        result = scheduler._cron_to_oncalendar("0 9 * * *")
        assert result == "* *-*-* 9:0:00"

    def test_cron_to_oncalendar_weekly(self, scheduler):
        result = scheduler._cron_to_oncalendar("0 9 * * 1")
        assert result == "1 *-*-* 9:0:00"


class TestWindowsTaskScheduler:
    @pytest.fixture
    def scheduler(self):
        return WindowsTaskScheduler()

    def test_task_name(self, scheduler):
        job = ScheduleJob(script="daily.lm", cron="0 0 * * *", schedule_id="win_task_id12", project_root=Path("/p"))
        assert scheduler._task_name(job) == "Lamia\\win_task_id12"

    def test_cron_to_schtasks_daily(self, scheduler):
        args = scheduler._cron_to_schtasks_args("0 9 * * *")
        assert "/SC" in args
        assert "DAILY" in args
        assert "/ST" in args
        assert "09:00" in args

    def test_cron_to_schtasks_weekly(self, scheduler):
        args = scheduler._cron_to_schtasks_args("0 9 * * 1")
        assert "WEEKLY" in args
        assert "MON" in args

    def test_cron_to_schtasks_every_minute(self, scheduler):
        args = scheduler._cron_to_schtasks_args("* * * * *")
        assert "MINUTE" in args

    def test_on_wake_not_passed_to_cron_parser(self, scheduler):
        """@reboot is handled in install(), not _cron_to_schtasks_args."""
        with pytest.raises(ValueError):
            scheduler._cron_to_schtasks_args("@reboot")


class TestLocalScheduler:
    @patch("lamia.scheduling.local_scheduler.platform.system", return_value="Darwin")
    def test_macos_uses_launchd(self, mock_system):
        scheduler = LocalScheduler()
        assert isinstance(scheduler._backend, LaunchdScheduler)

    @patch("lamia.scheduling.local_scheduler.platform.system", return_value="Linux")
    def test_linux_uses_systemd(self, mock_system):
        scheduler = LocalScheduler()
        assert isinstance(scheduler._backend, SystemdScheduler)

    @patch("lamia.scheduling.local_scheduler.platform.system", return_value="Windows")
    def test_windows_uses_task_scheduler(self, mock_system):
        scheduler = LocalScheduler()
        assert isinstance(scheduler._backend, WindowsTaskScheduler)

    def test_name(self):
        assert LocalScheduler.name() == "local"
