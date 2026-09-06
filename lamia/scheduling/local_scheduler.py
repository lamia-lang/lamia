"""Local OS scheduler backend: launchd (macOS), systemd (Linux), Task Scheduler (Windows)."""

import json
import logging
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from .base import BaseScheduler, JobStatus, ScheduleJob

logger = logging.getLogger(__name__)


def _parse_cron_fields(cron_expr: str) -> dict:
    """Parse a 5-field cron expression into component parts with validation."""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression (expected 5 fields): {cron_expr}")

    minute, hour, day, month, weekday = parts
    _expand_cron_field(minute, 0, 59, "minute")
    _expand_cron_field(hour, 0, 23, "hour")
    _expand_cron_field(day, 1, 31, "day")
    _expand_cron_field(month, 1, 12, "month")
    _expand_cron_field(weekday, 0, 7, "weekday")

    return {
        "minute": minute,
        "hour": hour,
        "day": day,
        "month": month,
        "weekday": weekday,
    }


def _expand_cron_field(value: str, min_val: int, max_val: int, name: str) -> Optional[List[int]]:
    """Validate a cron field and expand it to the values it matches.

    Returns None for '*' (any value in range). Supports comma lists, ranges
    ('N-M'), steps ('*/N', 'N-M/N'), and plain integers.
    """
    if value == "*":
        return None
    values = set()
    for part in value.split(","):
        base, sep, step_str = part.partition("/")
        step = 1
        if sep:
            try:
                step = int(step_str)
            except ValueError:
                raise ValueError(f"Invalid {name} step in cron: {value}")
            if step <= 0:
                raise ValueError(f"Invalid {name} step in cron: {value}")
        if base == "*":
            low, high = min_val, max_val
        elif "-" in base:
            low_str, high_str = base.split("-", 1)
            try:
                low, high = int(low_str), int(high_str)
            except ValueError:
                raise ValueError(f"Invalid {name} value in cron: {value}")
        else:
            try:
                low = high = int(base)
            except ValueError:
                raise ValueError(f"Invalid {name} value in cron: {value}")
        if low < min_val or high > max_val or low > high:
            raise ValueError(f"Cron {name} out of range ({min_val}-{max_val}): {value}")
        values.update(range(low, high + 1, step))
    return sorted(values)


def _schedule_log_path(job: ScheduleJob) -> str:
    """Return a single log file path for a schedule job.

    Logs are grouped by schedule id for clarity:
      ~/.lamia/logs/schedules/<job_id>/schedule.log
    """
    job_id = job.schedule_id
    log_dir = Path.home() / ".lamia" / "logs" / "schedules" / job_id
    log_dir.mkdir(parents=True, exist_ok=True)
    return str(log_dir / "schedule.log")


class LaunchdScheduler(BaseScheduler):
    """macOS launchd scheduler. Uses StartCalendarInterval for catch-up on wake."""

    @classmethod
    def name(cls) -> str:
        return "launchd"

    def _plist_path(self, job: ScheduleJob) -> Path:
        return Path.home() / "Library" / "LaunchAgents" / f"{job.label}.plist"

    def _meta_path(self, job: ScheduleJob) -> Path:
        return Path.home() / ".lamia" / "schedules-backend" / f"{job.label}.json"

    def _build_plist(self, job: ScheduleJob, lamia_bin: str) -> str:
        script_path = str(job.project_root / job.script)
        working_dir = str(job.project_root)
        log_file = _schedule_log_path(job)
        job_id = job.schedule_id

        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
            '<plist version="1.0">',
            '<dict>',
            f'    <key>Label</key>',
            f'    <string>{job.label}</string>',
            '    <key>ProgramArguments</key>',
            '    <array>',
            f'        <string>{lamia_bin}</string>',
            '        <string>--file</string>',
            f'        <string>{script_path}</string>',
            '        <string>--log-file</string>',
            f'        <string>{log_file}</string>',
            '        <string>--schedule-id</string>',
            f'        <string>{job_id}</string>',
            '    </array>',
            f'    <key>WorkingDirectory</key>',
            f'    <string>{working_dir}</string>',
        ]

        if job.cron == "@reboot":
            lines.append('    <key>RunAtLoad</key>')
            lines.append('    <true/>')
        else:
            cron = _parse_cron_fields(job.cron)
            intervals = self._cron_to_calendar_intervals(cron)
            lines.append('    <key>StartCalendarInterval</key>')
            if len(intervals) == 1:
                lines.append('    <dict>')
                lines.extend(intervals[0])
                lines.append('    </dict>')
            else:
                lines.append('    <array>')
                for interval_lines in intervals:
                    lines.append('        <dict>')
                    lines.extend(f'    {line}' for line in interval_lines)
                    lines.append('        </dict>')
                lines.append('    </array>')
            if job.catch_up:
                lines.append('    <key>RunAtLoad</key>')
                lines.append('    <true/>')

        lines.extend([
            '    <key>ExitTimeOut</key>',
            '    <integer>86400</integer>',
            '    <key>StandardOutPath</key>',
            f'    <string>{log_file}</string>',
            '    <key>StandardErrorPath</key>',
            f'    <string>{log_file}</string>',
            '</dict>',
            '</plist>',
        ])
        return "\n".join(lines) + "\n"

    def _cron_to_calendar_intervals(self, cron: dict) -> list:
        """Expand parsed cron fields into launchd StartCalendarInterval entries.

        launchd has no native step/list/range syntax, so a field naming several
        values (e.g. '*/5' or '9-17') is expanded into its explicit values and
        combined by cartesian product across fields — one dict of plist lines
        per matching point in time.
        """
        plist_keys = [
            ("minute", "Minute", 0, 59),
            ("hour", "Hour", 0, 23),
            ("day", "Day", 1, 31),
            ("month", "Month", 1, 12),
            ("weekday", "Weekday", 0, 7),
        ]
        constrained = []
        for field, key, min_val, max_val in plist_keys:
            expanded = _expand_cron_field(cron[field], min_val, max_val, field)
            if expanded is not None:
                constrained.append((key, expanded))

        combos = [[]]
        for key, values in constrained:
            combos = [combo + [f'        <key>{key}</key><integer>{value}</integer>']
                      for combo in combos for value in values]
        return combos

    def install(self, job: ScheduleJob, lamia_bin: str) -> None:
        plist_path = self._plist_path(job)
        plist_path.parent.mkdir(parents=True, exist_ok=True)

        plist_content = self._build_plist(job, lamia_bin)
        plist_path.write_text(plist_content)

        self._save_meta(job, lamia_bin)

        subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True,
        )
        result = subprocess.run(
            ["launchctl", "load", str(plist_path)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            logger.error(f"Failed to load launchd job {job.label}: {result.stderr}")
        else:
            logger.info(f"Scheduled: {job.script} ({job.cron}) via launchd")

    def uninstall(self, job: ScheduleJob) -> None:
        plist_path = self._plist_path(job)
        if plist_path.exists():
            subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
            plist_path.unlink()
            logger.info(f"Uninstalled schedule: {job.label}")
        meta_path = self._meta_path(job)
        if meta_path.exists():
            meta_path.unlink()

    def is_installed(self, job: ScheduleJob) -> bool:
        return self._plist_path(job).exists()

    def get_status(self, job: ScheduleJob) -> JobStatus:
        if not self.is_installed(job):
            return JobStatus.INACTIVE
        result = subprocess.run(
            ["launchctl", "list", job.label],
            capture_output=True, text=True,
        )
        return JobStatus.ACTIVE if result.returncode == 0 else JobStatus.INACTIVE

    def pause(self, job: ScheduleJob) -> None:
        plist_path = self._plist_path(job)
        if plist_path.exists():
            subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
            logger.info(f"Paused: {job.label}")

    def resume(self, job: ScheduleJob) -> None:
        plist_path = self._plist_path(job)
        if plist_path.exists():
            subprocess.run(["launchctl", "load", str(plist_path)], capture_output=True)
            logger.info(f"Resumed: {job.label}")

    def get_installed_config(self, job: ScheduleJob) -> Optional[dict]:
        meta_path = self._meta_path(job)
        if not meta_path.exists():
            return None
        try:
            return json.loads(meta_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def _save_meta(self, job: ScheduleJob, lamia_bin: str) -> None:
        meta_path = self._meta_path(job)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta = {
            "script": job.script,
            "cron": job.cron,
            "catch_up": job.catch_up,
            "project_root": str(job.project_root),
            "lamia_bin": lamia_bin,
        }
        meta_path.write_text(json.dumps(meta, indent=2))


class SystemdScheduler(BaseScheduler):
    """Linux systemd user timer scheduler. Uses Persistent=true for catch-up."""

    @classmethod
    def name(cls) -> str:
        return "systemd"

    def _unit_dir(self) -> Path:
        return Path.home() / ".config" / "systemd" / "user"

    def _service_name(self, job: ScheduleJob) -> str:
        return f"lamia-{job.schedule_id}"

    def _service_path(self, job: ScheduleJob) -> Path:
        return self._unit_dir() / f"{self._service_name(job)}.service"

    def _timer_path(self, job: ScheduleJob) -> Path:
        return self._unit_dir() / f"{self._service_name(job)}.timer"

    def _meta_path(self, job: ScheduleJob) -> Path:
        return Path.home() / ".lamia" / "schedules-backend" / f"{self._service_name(job)}.json"

    def _cron_to_oncalendar(self, cron_expr: str) -> str:
        """Convert 5-field cron to systemd OnCalendar format (best effort)."""
        cron = _parse_cron_fields(cron_expr)
        dow = "*" if cron["weekday"] == "*" else cron["weekday"]
        month = cron["month"]
        day = cron["day"]
        hour = cron["hour"]
        minute = cron["minute"]
        return f"{dow} *-{month}-{day} {hour}:{minute}:00"

    def install(self, job: ScheduleJob, lamia_bin: str) -> None:
        unit_dir = self._unit_dir()
        unit_dir.mkdir(parents=True, exist_ok=True)

        script_path = str(job.project_root / job.script)
        working_dir = str(job.project_root)
        svc_name = self._service_name(job)

        log_file = _schedule_log_path(job)
        job_id = job.schedule_id

        service_content = (
            "[Unit]\n"
            f"Description=Lamia scheduled: {job.script}\n\n"
            "[Service]\n"
            "Type=oneshot\n"
            f"WorkingDirectory={working_dir}\n"
            f"ExecStart={lamia_bin} --file {script_path} --log-file {log_file} --schedule-id {job_id}\n"
            f"Environment=HOME={Path.home()}\n"
        )

        if job.cron == "@reboot":
            service_content += "\n[Install]\nWantedBy=default.target\n"
            self._service_path(job).write_text(service_content)
            self._save_meta(job, lamia_bin)
            subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
            subprocess.run(
                ["systemctl", "--user", "enable", "--now", f"{svc_name}.service"],
                capture_output=True, text=True,
            )
            logger.info(f"Scheduled: {job.script} (on-wake) via systemd service")
            return

        on_calendar = self._cron_to_oncalendar(job.cron)
        persistent = "true" if job.catch_up else "false"
        timer_content = (
            "[Unit]\n"
            f"Description=Timer for lamia: {job.script}\n\n"
            "[Timer]\n"
            f"OnCalendar={on_calendar}\n"
            f"Persistent={persistent}\n\n"
            "[Install]\n"
            "WantedBy=timers.target\n"
        )

        self._service_path(job).write_text(service_content)
        self._timer_path(job).write_text(timer_content)
        self._save_meta(job, lamia_bin)

        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
        subprocess.run(
            ["systemctl", "--user", "enable", "--now", f"{svc_name}.timer"],
            capture_output=True, text=True,
        )
        logger.info(f"Scheduled: {job.script} ({job.cron}) via systemd timer")

    def uninstall(self, job: ScheduleJob) -> None:
        svc_name = self._service_name(job)
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", f"{svc_name}.timer"],
            capture_output=True,
        )
        for path in (self._service_path(job), self._timer_path(job)):
            if path.exists():
                path.unlink()
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
        meta_path = self._meta_path(job)
        if meta_path.exists():
            meta_path.unlink()
        logger.info(f"Uninstalled schedule: {svc_name}")

    def is_installed(self, job: ScheduleJob) -> bool:
        return self._timer_path(job).exists()

    def get_status(self, job: ScheduleJob) -> JobStatus:
        if not self.is_installed(job):
            return JobStatus.INACTIVE
        svc_name = self._service_name(job)
        result = subprocess.run(
            ["systemctl", "--user", "is-active", f"{svc_name}.timer"],
            capture_output=True, text=True,
        )
        return JobStatus.ACTIVE if result.stdout.strip() == "active" else JobStatus.INACTIVE

    def pause(self, job: ScheduleJob) -> None:
        svc_name = self._service_name(job)
        subprocess.run(
            ["systemctl", "--user", "stop", f"{svc_name}.timer"],
            capture_output=True,
        )
        logger.info(f"Paused: {svc_name}.timer")

    def resume(self, job: ScheduleJob) -> None:
        svc_name = self._service_name(job)
        subprocess.run(
            ["systemctl", "--user", "start", f"{svc_name}.timer"],
            capture_output=True,
        )
        logger.info(f"Resumed: {svc_name}.timer")

    def get_installed_config(self, job: ScheduleJob) -> Optional[dict]:
        meta_path = self._meta_path(job)
        if not meta_path.exists():
            return None
        try:
            return json.loads(meta_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def _save_meta(self, job: ScheduleJob, lamia_bin: str) -> None:
        meta_path = self._meta_path(job)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta = {
            "script": job.script,
            "cron": job.cron,
            "catch_up": job.catch_up,
            "project_root": str(job.project_root),
            "lamia_bin": lamia_bin,
        }
        meta_path.write_text(json.dumps(meta, indent=2))


class WindowsTaskScheduler(BaseScheduler):
    """Windows Task Scheduler via schtasks.exe."""

    @classmethod
    def name(cls) -> str:
        return "windows"

    def _task_name(self, job: ScheduleJob) -> str:
        return f"Lamia\\{job.schedule_id}"

    def _meta_path(self, job: ScheduleJob) -> Path:
        return Path.home() / ".lamia" / "schedules-backend" / f"{job.schedule_id}.json"

    def _cron_to_schtasks_args(self, cron_expr: str) -> list:
        """Convert cron to schtasks /SC /MO /ST arguments (simplified mapping)."""
        cron = _parse_cron_fields(cron_expr)

        hour = cron["hour"] if cron["hour"] != "*" else "0"
        minute = cron["minute"] if cron["minute"] != "*" else "0"
        start_time = f"{int(hour):02d}:{int(minute):02d}"

        if cron["day"] == "*" and cron["month"] == "*" and cron["weekday"] == "*":
            if cron["hour"] == "*":
                modifier = cron["minute"] if cron["minute"] != "*" else "60"
                return ["/SC", "MINUTE", "/MO", modifier]
            return ["/SC", "DAILY", "/ST", start_time]

        if cron["weekday"] != "*" and cron["day"] == "*":
            days_map = {"0": "SUN", "1": "MON", "2": "TUE", "3": "WED",
                        "4": "THU", "5": "FRI", "6": "SAT", "7": "SUN"}
            day_val = days_map.get(cron["weekday"], cron["weekday"].upper())
            return ["/SC", "WEEKLY", "/D", day_val, "/ST", start_time]

        if cron["day"] != "*":
            return ["/SC", "MONTHLY", "/D", cron["day"], "/ST", start_time]

        return ["/SC", "DAILY", "/ST", start_time]

    def install(self, job: ScheduleJob, lamia_bin: str) -> None:
        task_name = self._task_name(job)
        script_path = str(job.project_root / job.script)
        working_dir = str(job.project_root)

        log_file = _schedule_log_path(job)
        job_id = job.schedule_id

        self.uninstall(job)

        if job.cron == "@reboot":
            schedule_args = ["/SC", "ONLOGON"]
        else:
            schedule_args = self._cron_to_schtasks_args(job.cron)

        cmd = [
            "schtasks", "/Create",
            "/TN", task_name,
            "/TR", f'"{lamia_bin}" --file "{script_path}" --log-file "{log_file}" --schedule-id {job_id}',
            "/F",
            *schedule_args,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Failed to create Windows scheduled task: {result.stderr}")
        else:
            self._save_meta(job, lamia_bin)
            logger.info(f"Scheduled: {job.script} ({job.cron}) via Windows Task Scheduler")

    def uninstall(self, job: ScheduleJob) -> None:
        task_name = self._task_name(job)
        subprocess.run(
            ["schtasks", "/Delete", "/TN", task_name, "/F"],
            capture_output=True,
        )
        meta_path = self._meta_path(job)
        if meta_path.exists():
            meta_path.unlink()

    def is_installed(self, job: ScheduleJob) -> bool:
        task_name = self._task_name(job)
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", task_name],
            capture_output=True,
        )
        return result.returncode == 0

    def get_status(self, job: ScheduleJob) -> JobStatus:
        if not self.is_installed(job):
            return JobStatus.INACTIVE
        return JobStatus.ACTIVE

    def pause(self, job: ScheduleJob) -> None:
        task_name = self._task_name(job)
        subprocess.run(
            ["schtasks", "/Change", "/TN", task_name, "/DISABLE"],
            capture_output=True,
        )
        logger.info(f"Paused: {task_name}")

    def resume(self, job: ScheduleJob) -> None:
        task_name = self._task_name(job)
        subprocess.run(
            ["schtasks", "/Change", "/TN", task_name, "/ENABLE"],
            capture_output=True,
        )
        logger.info(f"Resumed: {task_name}")

    def get_installed_config(self, job: ScheduleJob) -> Optional[dict]:
        meta_path = self._meta_path(job)
        if not meta_path.exists():
            return None
        try:
            return json.loads(meta_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def _save_meta(self, job: ScheduleJob, lamia_bin: str) -> None:
        meta_path = self._meta_path(job)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta = {
            "script": job.script,
            "cron": job.cron,
            "catch_up": job.catch_up,
            "project_root": str(job.project_root),
            "lamia_bin": lamia_bin,
        }
        meta_path.write_text(json.dumps(meta, indent=2))


class LocalScheduler(BaseScheduler):
    """Auto-detecting local scheduler that delegates to the OS-appropriate backend."""

    def __init__(self):
        system = platform.system()
        if system == "Darwin":
            self._backend = LaunchdScheduler()
        elif system == "Windows":
            self._backend = WindowsTaskScheduler()
        else:
            self._backend = SystemdScheduler()

    @classmethod
    def name(cls) -> str:
        return "local"

    def install(self, job: ScheduleJob, lamia_bin: str) -> None:
        self._backend.install(job, lamia_bin)

    def uninstall(self, job: ScheduleJob) -> None:
        self._backend.uninstall(job)

    def is_installed(self, job: ScheduleJob) -> bool:
        return self._backend.is_installed(job)

    def get_status(self, job: ScheduleJob) -> JobStatus:
        return self._backend.get_status(job)

    def get_installed_config(self, job: ScheduleJob) -> Optional[dict]:
        return self._backend.get_installed_config(job)

    def pause(self, job: ScheduleJob) -> None:
        self._backend.pause(job)

    def resume(self, job: ScheduleJob) -> None:
        self._backend.resume(job)
