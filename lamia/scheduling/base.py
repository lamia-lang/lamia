"""Base scheduler interface and data models."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional
from datetime import datetime


class JobStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNKNOWN = "unknown"


@dataclass
class ScheduleJob:
    script: str
    cron: str
    timezone: str = "UTC"
    catch_up: bool = True
    project_root: Path = field(default_factory=Path)

    @property
    def job_id(self) -> str:
        """Stable identifier derived from project root + script path."""
        safe_root = str(self.project_root).replace("/", "_").replace("\\", "_").strip("_")
        safe_script = self.script.replace("/", "_").replace("\\", "_").replace(".", "_")
        return f"lamia_{safe_root}_{safe_script}"

    @property
    def label(self) -> str:
        """Human-readable label for OS scheduler entries."""
        return f"com.lamia.schedule.{self.script.replace('/', '.').replace('.lm', '')}"


class BaseScheduler:
    """Interface that all scheduler backends must implement."""

    @classmethod
    def name(cls) -> str:
        raise NotImplementedError

    def install(self, job: ScheduleJob, lamia_bin: str) -> None:
        raise NotImplementedError

    def uninstall(self, job: ScheduleJob) -> None:
        raise NotImplementedError

    def is_installed(self, job: ScheduleJob) -> bool:
        raise NotImplementedError

    def get_status(self, job: ScheduleJob) -> JobStatus:
        raise NotImplementedError

    def get_installed_config(self, job: ScheduleJob) -> Optional[dict]:
        """Return the currently installed config for comparison, or None if not installed."""
        raise NotImplementedError
