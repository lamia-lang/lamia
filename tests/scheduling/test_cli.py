"""Tests for lamia.scheduling.cli module."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from lamia.scheduling.cli import (
    EVERY_PRESETS,
    _cron_to_friendly,
    _resolve_cron,
    handle_schedule,
    _handle_add,
    _handle_list,
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
        args.timezone = "UTC"
        args.no_catch_up = False

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
        args.timezone = "UTC"
        args.no_catch_up = False

        _handle_add(args)
        mock_scheduler.install.assert_called_once()
        captured = capsys.readouterr()
        assert "Scheduled:" in captured.out

    def test_add_nonexistent_script_exits(self, tmp_path, capsys):
        args = MagicMock()
        args.script = str(tmp_path / "missing.lm")
        args.every = "day"
        args.cron = None
        args.timezone = "UTC"
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
        args.timezone = "UTC"
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
             "timezone": "UTC", "catch_up": True, "project_root": "/home/user/proj"},
        ])
        args = MagicMock()
        _handle_list(args)
        captured = capsys.readouterr()
        assert "abc123" in captured.out
        assert "daily.lm" in captured.out


class TestHandleRemove:
    def test_remove_existing_job(self, mock_scheduler, capsys, monkeypatch):
        monkeypatch.setattr("lamia.scheduling.cli.load_job", lambda job_id: {
            "id": "abc123",
            "script": "daily.lm",
            "cron": "0 9 * * *",
            "timezone": "UTC",
            "catch_up": True,
            "project_root": "/home/user/proj",
        })
        monkeypatch.setattr("lamia.scheduling.cli.remove_job", lambda x: True)

        args = MagicMock()
        args.id = "abc123"
        _handle_remove(args)

        mock_scheduler.uninstall.assert_called_once()
        captured = capsys.readouterr()
        assert "Removed" in captured.out

    def test_remove_nonexistent_exits(self, capsys, monkeypatch):
        monkeypatch.setattr("lamia.scheduling.cli.load_job", lambda x: None)
        args = MagicMock()
        args.id = "nope"

        with pytest.raises(SystemExit):
            _handle_remove(args)


class TestHandleUpdate:
    def test_update_existing_job(self, mock_scheduler, capsys, monkeypatch):
        monkeypatch.setattr("lamia.scheduling.cli.load_job", lambda job_id: {
            "id": "abc123",
            "script": "daily.lm",
            "cron": "0 9 * * *",
            "timezone": "UTC",
            "catch_up": True,
            "project_root": "/home/user/proj",
        })
        monkeypatch.setattr("lamia.scheduling.cli.save_job", lambda *a: "abc123")

        args = MagicMock()
        args.id = "abc123"
        args.every = None
        args.cron = "15 10 * * *"
        args.timezone = "Europe/Berlin"
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
        args.timezone = None
        args.catch_up = False
        args.no_catch_up = False

        with pytest.raises(SystemExit):
            _handle_update(args)


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
