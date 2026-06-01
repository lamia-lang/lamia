"""Base scheduler interface and data models."""

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


def generate_schedule_id(script: str, project_root: str) -> str:
    """Generate a stable short hash ID from project_root + script.

    Called once when a job is first created. After that, the ID is stored
    and never regenerated.
    """
    raw = f"{project_root}:{script}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


class JobStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNKNOWN = "unknown"


@dataclass
class ScheduleJob:
    script: str
    cron: str
    schedule_id: str
    catch_up: bool = True
    project_root: Path = field(default_factory=Path)

    @property
    def label(self) -> str:
        """OS scheduler entry label — based on schedule_id for uniqueness."""
        return f"com.lamia.schedule.{self.schedule_id}"


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
