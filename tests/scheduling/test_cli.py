"""Tests for lamia.scheduling.cli module."""

import json
import signal
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from lamia.scheduling.base import ScheduleJob
from lamia.scheduling.cli import (
    EVERY_PRESETS,
    _cron_to_friendly,
    _format_error_line,
    _resolve_cron,
    handle_schedule,
    _handle_add,
    _handle_list,
    _handle_logs,
    _handle_remove,
    _handle_update,
)


@pytest.fixture
def temp_project(tmp_path):
    """Create a temp project with a .lm script."""
    script = tmp_path / "test_script.lm"
    script.write_text("print('hello')")
    return tmp_path, script


@pytest.fixture
def mock_scheduler():
    with patch("lamia.scheduling.cli.LocalScheduler") as mock_cls:
        instance = MagicMock()
        mock_cls.return_value = instance
        yield instance


@pytest.fixture
def mock_registry(tmp_path, monkeypatch):
    fake_dir = tmp_path / "schedules"
    fake_dir.mkdir()
    monkeypatch.setattr("lamia.scheduling.registry.SCHEDULES_DIR", fake_dir)
    monkeypatch.setattr("lamia.scheduling.cli.find_job_by_script",
                        lambda *a: None)
    return fake_dir


class TestHandleAdd:
    def test_add_creates_schedule_with_every(self, temp_project, mock_scheduler, mock_registry, capsys, monkeypatch):
        project_dir, script = temp_project
        monkeypatch.setattr("lamia.scheduling.cli.find_job_by_script", lambda *a: None)

        args = MagicMock()
        args.script = str(script)
        args.every = "day"
        args.cron = None
        args.no_catch_up = False
        args.remote = False

        _handle_add(args)
        mock_scheduler.install.assert_called_once()
        captured = capsys.readouterr()
        assert "Scheduled:" in captured.out

    def test_add_creates_schedule_with_cron(self, temp_project, mock_scheduler, mock_registry, capsys, monkeypatch):
        project_dir, script = temp_project
        monkeypatch.setattr("lamia.scheduling.cli.find_job_by_script", lambda *a: None)

        args = MagicMock()
        args.script = str(script)
        args.every = None
        args.cron = "30 14 * * *"
        args.no_catch_up = False
        args.remote = False

        _handle_add(args)
        mock_scheduler.install.assert_called_once()
        captured = capsys.readouterr()
        assert "Scheduled:" in captured.out

    def test_add_same_script_twice_reuses_id(self, temp_project, mock_scheduler, mock_registry, capsys, monkeypatch):
        """Running schedule add twice for the same script must update, not duplicate."""
        project_dir, script = temp_project
        existing = {
            "id": "existingid123",
            "script": "test_script.lm",
            "cron": "0 9 * * *",
            "catch_up": True,
            "project_root": str(project_dir),
            "backend": "local",
        }
        monkeypatch.setattr("lamia.scheduling.cli.find_job_by_script",
                            lambda s, p: existing)

        args = MagicMock()
        args.script = str(script)
        args.every = "day"
        args.cron = None
        args.no_catch_up = False
        args.remote = False

        _handle_add(args)

        installed_job = mock_scheduler.install.call_args[0][0]
        assert installed_job.schedule_id == "existingid123"
        mock_scheduler.uninstall.assert_called_once()
        captured = capsys.readouterr()
        assert "existingid123" in captured.out

    def test_add_nonexistent_script_exits(self, tmp_path, capsys):
        args = MagicMock()
        args.script = str(tmp_path / "missing.lm")
        args.every = "day"
        args.cron = None
        args.no_catch_up = False

        with pytest.raises(SystemExit):
            _handle_add(args)

    def test_add_non_lm_file_exits(self, tmp_path, capsys):
        py_file = tmp_path / "script.py"
        py_file.write_text("pass")
        args = MagicMock()
        args.script = str(py_file)
        args.every = "day"
        args.cron = None
        args.no_catch_up = False

        with pytest.raises(SystemExit):
            _handle_add(args)


class TestHandleList:
    def test_list_empty(self, mock_registry, capsys, monkeypatch):
        monkeypatch.setattr("lamia.scheduling.cli.list_jobs", lambda: [])
        args = MagicMock()
        _handle_list(args)
        captured = capsys.readouterr()
        assert "No scheduled jobs" in captured.out

    def test_list_shows_jobs(self, mock_registry, capsys, monkeypatch):
        monkeypatch.setattr("lamia.scheduling.cli.list_jobs", lambda: [
            {"id": "abc123", "script": "daily.lm", "cron": "0 9 * * *",
             "catch_up": True, "project_root": "/home/user/proj"},
        ])
        args = MagicMock()
        _handle_list(args)
        captured = capsys.readouterr()
        assert "abc123" in captured.out
        assert "daily.lm" in captured.out

    def test_list_shows_source_missing_status(self, mock_registry, capsys, monkeypatch):
        monkeypatch.setattr("lamia.scheduling.cli.list_jobs", lambda: [
            {
                "id": "orph123",
                "script": "deleted.lm",
                "cron": "0 9 * * *",
                "catch_up": True,
                "project_root": "/home/user/proj",
                "source_missing": True,
            },
        ])
        args = MagicMock()
        _handle_list(args)
        captured = capsys.readouterr()
        assert "SOURCE_MISSING" in captured.out
        assert "source: MISSING" in captured.out


class TestHandleRemove:
    def test_remove_existing_job(self, mock_scheduler, capsys, monkeypatch):
        monkeypatch.setattr("lamia.scheduling.cli.load_job", lambda job_id: {
            "id": "abc123",
            "script": "daily.lm",
            "cron": "0 9 * * *",
            "catch_up": True,
            "project_root": "/home/user/proj",
        })
        monkeypatch.setattr("lamia.scheduling.cli.remove_job", lambda x: True)

        args = MagicMock()
        args.id = "abc123"
        args.orphaned = False
        _handle_remove(args)

        mock_scheduler.uninstall.assert_called_once()
        captured = capsys.readouterr()
        assert "Removed" in captured.out

    def test_remove_nonexistent_exits(self, capsys, monkeypatch):
        monkeypatch.setattr("lamia.scheduling.cli.load_job", lambda x: None)
        args = MagicMock()
        args.id = "nope"
        args.orphaned = False

        with pytest.raises(SystemExit):
            _handle_remove(args)

    def test_remove_orphaned(self, mock_scheduler, capsys, monkeypatch):
        monkeypatch.setattr("lamia.scheduling.cli.list_jobs", lambda: [
            {
                "id": "orph-1",
                "script": "missing.lm",
                "cron": "0 9 * * *",
                "catch_up": True,
                "project_root": "/home/user/proj",
                "source_missing": True,
            }
        ])
        monkeypatch.setattr("lamia.scheduling.cli.remove_job", lambda x: True)
        args = MagicMock()
        args.id = None
        args.orphaned = True

        _handle_remove(args)

        out = capsys.readouterr().out
        assert "Removed orphaned schedule" in out


class TestHandleUpdate:
    def test_update_existing_job(self, mock_scheduler, capsys, monkeypatch):
        monkeypatch.setattr("lamia.scheduling.cli.load_job", lambda job_id: {
            "id": "abc123",
            "script": "daily.lm",
            "cron": "0 9 * * *",
            "catch_up": True,
            "project_root": "/home/user/proj",
        })
        monkeypatch.setattr("lamia.scheduling.cli.save_job", lambda *a, **kw: "abc123")

        args = MagicMock()
        args.id = "abc123"
        args.every = None
        args.cron = "15 10 * * *"
        args.catch_up = False
        args.no_catch_up = True

        _handle_update(args)
        mock_scheduler.uninstall.assert_called_once()
        mock_scheduler.install.assert_called_once()
        captured = capsys.readouterr()
        assert "Updated schedule" in captured.out

    def test_update_nonexistent_exits(self, monkeypatch):
        monkeypatch.setattr("lamia.scheduling.cli.load_job", lambda x: None)
        args = MagicMock()
        args.id = "nope"
        args.every = "day"
        args.cron = None
        args.catch_up = False
        args.no_catch_up = False

        with pytest.raises(SystemExit):
            _handle_update(args)


class TestHandleLogs:
    def test_local_backend_prints_log_file(self, tmp_path, capsys, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        log_dir = tmp_path / ".lamia" / "logs" / "schedules" / "abc123"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "schedule.log"
        log_file.write_text("run output line 1\nrun output line 2\n")

        monkeypatch.setattr("lamia.scheduling.cli.load_job", lambda job_id: {
            "id": "abc123",
            "script": "daily.lm",
            "cron": "0 9 * * *",
            "catch_up": True,
            "project_root": "/home/user/proj",
            "backend": "local",
        })

        args = MagicMock()
        args.id = "abc123"
        _handle_logs(args)

        captured = capsys.readouterr()
        assert captured.out == "run output line 1\nrun output line 2\n"
        assert captured.err == ""

    def test_local_backend_no_log_file(self, tmp_path, capsys, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setattr("lamia.scheduling.cli.load_job", lambda job_id: {
            "id": "abc123",
            "script": "daily.lm",
            "cron": "0 9 * * *",
            "catch_up": True,
            "project_root": "/home/user/proj",
            "backend": "local",
        })

        args = MagicMock()
        args.id = "abc123"
        _handle_logs(args)

        captured = capsys.readouterr()
        assert captured.out == "No logs found\n"

    def test_cloud_backend_fetches_logs(self, capsys, monkeypatch):
        mock_scheduler = MagicMock()
        mock_scheduler.fetch_logs.return_value = {
            "stdout": "cloud stdout\n",
            "stderr": "cloud stderr\n",
            "logs_url": "https://console.cloud.google.com/logs/query",
        }
        monkeypatch.setattr("lamia.scheduling.cli._scheduler_for_job", lambda *a: mock_scheduler)
        monkeypatch.setattr("lamia.scheduling.cli.load_job", lambda job_id: {
            "id": "cloud-1",
            "script": "daily.lm",
            "cron": "0 9 * * *",
            "catch_up": False,
            "project_root": "/home/user/proj",
            "backend": "cloud",
        })

        args = MagicMock()
        args.id = "cloud-1"
        _handle_logs(args)

        mock_scheduler.fetch_logs.assert_called_once()
        captured = capsys.readouterr()
        assert captured.out == "cloud stdout\n\nLogs: https://console.cloud.google.com/logs/query\n"
        assert captured.err == "cloud stderr\n"

    def test_nonexistent_job_exits(self, monkeypatch):
        monkeypatch.setattr("lamia.scheduling.cli.load_job", lambda x: None)
        args = MagicMock()
        args.id = "missing"

        with pytest.raises(SystemExit):
            _handle_logs(args)



class TestResolveCron:
    def test_every_day(self):
        args = MagicMock(every="day", cron=None)
        assert _resolve_cron(args) == "0 9 * * *"

    def test_every_hour(self):
        args = MagicMock(every="hour", cron=None)
        assert _resolve_cron(args) == "0 * * * *"

    def test_every_weekday(self):
        args = MagicMock(every="weekday", cron=None)
        assert _resolve_cron(args) == "0 9 * * 1-5"

    def test_every_week(self):
        args = MagicMock(every="week", cron=None)
        assert _resolve_cron(args) == "0 9 * * 1"

    def test_every_aliases_still_work(self):
        assert _resolve_cron(MagicMock(every="daily", cron=None)) == "0 9 * * *"
        assert _resolve_cron(MagicMock(every="hourly", cron=None)) == "0 * * * *"
        assert _resolve_cron(MagicMock(every="weekdays", cron=None)) == "0 9 * * 1-5"
        assert _resolve_cron(MagicMock(every="weekly", cron=None)) == "0 9 * * 1"

    def test_every_on_wake(self):
        args = MagicMock(every="on-wake", cron=None)
        assert _resolve_cron(args) == "@reboot"

    def test_cron_passthrough(self):
        args = MagicMock(every=None, cron="30 14 * * *")
        assert _resolve_cron(args) == "30 14 * * *"

    def test_neither_errors(self, capsys):
        args = MagicMock(every=None, cron=None)
        with pytest.raises(SystemExit):
            _resolve_cron(args)

    def test_unknown_preset_errors(self, capsys):
        args = MagicMock(every="biweekly", cron=None)
        with pytest.raises(SystemExit):
            _resolve_cron(args)


class TestCronToFriendly:
    def test_known_presets(self):
        assert _cron_to_friendly("0 9 * * *") == "day"
        assert _cron_to_friendly("0 * * * *") == "hour"
        assert _cron_to_friendly("@reboot") == "on-wake"

    def test_custom_cron_returned_as_is(self):
        assert _cron_to_friendly("30 14 1 * *") == "30 14 1 * *"


class TestHandleScheduleDispatch:
    def test_no_action_prints_help(self, capsys):
        with patch("sys.argv", ["lamia", "schedule"]):
            with pytest.raises(SystemExit):
                handle_schedule()

    def test_add_without_args_prints_add_help(self, capsys):
        with patch("sys.argv", ["lamia", "schedule", "add"]):
            with pytest.raises(SystemExit):
                handle_schedule()
        captured = capsys.readouterr()
        assert "usage: lamia schedule add" in captured.out
        assert "--every PRESET" in captured.out


class TestFormatErrorLine:
    """Error messages in schedule list must be one readable line."""

    def test_short_error_unchanged(self):
        job = {"id": "test-1234", "backend": "local"}
        result = _format_error_line("connection refused", job)
        assert result == "connection refused"

    def test_multiline_error_truncated_to_first_line(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        job = {"id": "test-1234", "backend": "local"}
        error = "Message: invalid session id\nStacktrace:\n0  chromedriver 0x12345\n1  chromedriver 0x67890"
        result = _format_error_line(error, job)
        assert result.startswith("Message: invalid session id")
        assert "Stacktrace" not in result
        assert "schedule.log" in result

    def test_very_long_single_line_truncated(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        job = {"id": "test-1234", "backend": "local"}
        error = "x" * 200
        result = _format_error_line(error, job)
        assert len(result.split("  (see")[0]) <= 123
        assert "..." in result
        assert "schedule.log" in result

    def test_local_job_shows_log_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        job = {"id": "my-job-abc1", "backend": "local"}
        error = "line1\nline2\nline3"
        result = _format_error_line(error, job)
        assert "my-job-abc1" in result
        assert "schedule.log" in result

    def test_cloud_job_shows_cloud_logs(self):
        job = {"id": "cloud-job-1", "backend": "cloud"}
        error = "line1\nline2"
        result = _format_error_line(error, job)
        assert "cloud logs" in result

    def test_single_line_within_limit_no_reference(self):
        job = {"id": "test-1234", "backend": "local"}
        result = _format_error_line("simple error", job)
        assert "schedule.log" not in result
        assert result == "simple error"


class TestGracefulShutdownRecordsRun:
    """_graceful_shutdown must always record the run before cleanup."""

    @pytest.fixture(autouse=True)
    def _reset_cli_globals(self):
        """Reset module-level state before each test."""
        import lamia.cli.cli as cli_mod
        original_schedule_id = cli_mod._active_schedule_id
        original_run_recorded = cli_mod._run_recorded
        yield
        cli_mod._active_schedule_id = original_schedule_id
        cli_mod._run_recorded = original_run_recorded

    @pytest.fixture
    def temp_schedules_dir(self, tmp_path, monkeypatch):
        fake_dir = tmp_path / "schedules"
        fake_dir.mkdir()
        monkeypatch.setattr("lamia.scheduling.registry.SCHEDULES_DIR", fake_dir)
        return fake_dir

    def test_graceful_shutdown_records_success(self, temp_schedules_dir):
        """A normal successful run must persist exit_code=0."""
        import lamia.cli.cli as cli_mod
        from lamia.scheduling.registry import save_job, get_last_run_status

        job = ScheduleJob(
            script="pins.lm", cron="0 19 * * *",
            schedule_id="pins-test-01",
            project_root=Path("/p"),
        )
        save_job(job, "/bin/lamia")

        cli_mod._active_schedule_id = "pins-test-01"
        cli_mod._run_recorded = False

        with pytest.raises(SystemExit) as exc_info:
            cli_mod._graceful_shutdown(None, exit_code=0)
        assert exc_info.value.code == 0

        status = get_last_run_status("pins-test-01")
        assert status is not None
        assert status["success"] is True
        assert status["exit_code"] == 0
        assert status["error"] == ""

    def test_graceful_shutdown_records_failure_with_error(self, temp_schedules_dir):
        """A failed run must persist exit_code=1 and the error message."""
        import lamia.cli.cli as cli_mod
        from lamia.scheduling.registry import save_job, get_last_run_status

        job = ScheduleJob(
            script="pins.lm", cron="0 19 * * *",
            schedule_id="pins-test-02",
            project_root=Path("/p"),
        )
        save_job(job, "/bin/lamia")

        cli_mod._active_schedule_id = "pins-test-02"
        cli_mod._run_recorded = False

        with pytest.raises(SystemExit):
            cli_mod._graceful_shutdown(None, exit_code=1, error_msg="chromedriver died")

        status = get_last_run_status("pins-test-02")
        assert status is not None
        assert status["success"] is False
        assert status["error"] == "chromedriver died"

    def test_graceful_shutdown_skips_when_already_recorded(self, temp_schedules_dir):
        """If signal handler already recorded, _graceful_shutdown must not overwrite."""
        import lamia.cli.cli as cli_mod
        from lamia.scheduling.registry import save_job, record_run, get_last_run_status

        job = ScheduleJob(
            script="pins.lm", cron="0 19 * * *",
            schedule_id="pins-test-03",
            project_root=Path("/p"),
        )
        save_job(job, "/bin/lamia")
        record_run("pins-test-03", exit_code=0, error="killed by signal 15")

        cli_mod._active_schedule_id = "pins-test-03"
        cli_mod._run_recorded = True

        with pytest.raises(SystemExit):
            cli_mod._graceful_shutdown(None, exit_code=1, error_msg="some cleanup error")

        status = get_last_run_status("pins-test-03")
        assert status["success"] is True
        assert status["error"] == "killed by signal 15"

    def test_no_schedule_id_means_no_recording(self, temp_schedules_dir):
        """Non-scheduled runs must not attempt to record."""
        import lamia.cli.cli as cli_mod

        cli_mod._active_schedule_id = None
        cli_mod._run_recorded = False

        with pytest.raises(SystemExit):
            cli_mod._graceful_shutdown(None, exit_code=0)


class TestRecordRunOnSignal:
    """_record_run_on_signal must persist the result before os._exit."""

    @pytest.fixture(autouse=True)
    def _reset_cli_globals(self):
        import lamia.cli.cli as cli_mod
        original_schedule_id = cli_mod._active_schedule_id
        original_run_recorded = cli_mod._run_recorded
        yield
        cli_mod._active_schedule_id = original_schedule_id
        cli_mod._run_recorded = original_run_recorded

    @pytest.fixture
    def temp_schedules_dir(self, tmp_path, monkeypatch):
        fake_dir = tmp_path / "schedules"
        fake_dir.mkdir()
        monkeypatch.setattr("lamia.scheduling.registry.SCHEDULES_DIR", fake_dir)
        return fake_dir

    def test_sigterm_records_success(self, temp_schedules_dir):
        import lamia.cli.cli as cli_mod
        from lamia.scheduling.registry import save_job, get_last_run_status

        job = ScheduleJob(
            script="pins.lm", cron="0 19 * * *",
            schedule_id="sig-test-01",
            project_root=Path("/p"),
        )
        save_job(job, "/bin/lamia")

        cli_mod._active_schedule_id = "sig-test-01"
        cli_mod._run_recorded = False

        cli_mod._record_run_on_signal(signal.SIGTERM)

        assert cli_mod._run_recorded is True
        status = get_last_run_status("sig-test-01")
        assert status is not None
        assert status["exit_code"] == 0

    def test_sigint_records_failure(self, temp_schedules_dir):
        import lamia.cli.cli as cli_mod
        from lamia.scheduling.registry import save_job, get_last_run_status

        job = ScheduleJob(
            script="pins.lm", cron="0 19 * * *",
            schedule_id="sig-test-02",
            project_root=Path("/p"),
        )
        save_job(job, "/bin/lamia")

        cli_mod._active_schedule_id = "sig-test-02"
        cli_mod._run_recorded = False

        cli_mod._record_run_on_signal(signal.SIGINT)

        status = get_last_run_status("sig-test-02")
        assert status is not None
        assert status["exit_code"] == 1

    def test_skips_when_already_recorded(self, temp_schedules_dir):
        import lamia.cli.cli as cli_mod
        from lamia.scheduling.registry import save_job, record_run, get_last_run_status

        job = ScheduleJob(
            script="pins.lm", cron="0 19 * * *",
            schedule_id="sig-test-03",
            project_root=Path("/p"),
        )
        save_job(job, "/bin/lamia")
        record_run("sig-test-03", exit_code=1, error="real failure")

        cli_mod._active_schedule_id = "sig-test-03"
        cli_mod._run_recorded = True

        cli_mod._record_run_on_signal(signal.SIGTERM)

        status = get_last_run_status("sig-test-03")
        assert status["exit_code"] == 1
        assert status["error"] == "real failure"

    def test_noop_without_schedule_id(self, temp_schedules_dir):
        import lamia.cli.cli as cli_mod

        cli_mod._active_schedule_id = None
        cli_mod._run_recorded = False

        cli_mod._record_run_on_signal(signal.SIGTERM)
        assert cli_mod._run_recorded is False


class TestSchedulerInvocationFlow:
    """End-to-end: schedule fires → script runs → record_run persists."""

    @pytest.fixture(autouse=True)
    def _reset_cli_globals(self):
        import lamia.cli.cli as cli_mod
        original_schedule_id = cli_mod._active_schedule_id
        original_run_recorded = cli_mod._run_recorded
        yield
        cli_mod._active_schedule_id = original_schedule_id
        cli_mod._run_recorded = original_run_recorded

    @pytest.fixture
    def temp_schedules_dir(self, tmp_path, monkeypatch):
        fake_dir = tmp_path / "schedules"
        fake_dir.mkdir()
        monkeypatch.setattr("lamia.scheduling.registry.SCHEDULES_DIR", fake_dir)
        return fake_dir

    def test_successful_run_then_catchup_skip(self, temp_schedules_dir):
        """After a successful run, catch-up invocations must be skipped."""
        import lamia.cli.cli as cli_mod
        from lamia.scheduling.registry import save_job, get_last_run_status
        from datetime import datetime

        job = ScheduleJob(
            script="pins.lm", cron="0 19 * * *",
            schedule_id="flow-test-01",
            project_root=Path("/p"),
        )
        save_job(job, "/bin/lamia")

        cli_mod._active_schedule_id = "flow-test-01"
        cli_mod._run_recorded = False
        with pytest.raises(SystemExit):
            cli_mod._graceful_shutdown(None, exit_code=0)

        status = get_last_run_status("flow-test-01")
        assert status["success"] is True

        should_skip = cli_mod._should_skip_catchup_run("flow-test-01")
        now = datetime.now()
        scheduled_hour = 19
        if now.hour > scheduled_hour or (now.hour == scheduled_hour and now.minute >= 0):
            assert should_skip is True
        else:
            assert should_skip is True

    def test_failed_run_does_not_block_next_catchup(self, temp_schedules_dir):
        """A failure must NOT prevent the next catch-up from running."""
        import lamia.cli.cli as cli_mod
        from lamia.scheduling.registry import save_job, record_run
        from datetime import datetime, timezone, timedelta

        job = ScheduleJob(
            script="pins.lm", cron="0 19 * * *",
            schedule_id="flow-test-02",
            project_root=Path("/p"),
        )
        save_job(job, "/bin/lamia")

        old_ts = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        path = temp_schedules_dir / "flow-test-02.json"
        data = json.loads(path.read_text())
        data["last_run"] = {
            "timestamp": old_ts,
            "exit_code": 1,
            "success": False,
            "error": "old failure",
        }
        path.write_text(json.dumps(data, indent=2))

        should_skip = cli_mod._should_skip_catchup_run("flow-test-02")
        assert should_skip is False
