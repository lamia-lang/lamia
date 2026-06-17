"""Base scheduler interface and data models."""

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


def _slugify(name: str) -> str:
    """Convert a script filename into a clean kebab-case slug.

    'publish_pins.lm' → 'publish-pins'
    'My Complex Script (v2).lm' → 'my-complex-script-v2'
    """
    stem = name.rsplit(".", 1)[0] if "." in name else name
    slug = stem.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    if len(slug) > 16:
        slug = slug[:16].rstrip("-")
    return slug if slug else "script"


def generate_schedule_id(script: str, project_root: str) -> str:
    """Generate a human-readable schedule ID from script name + project hash.

    Format: <script-slug>-<4-char-hash>
    Example: 'publish-pins-a3f2', 'test-vertex-7bc1'

    The short hash suffix ensures uniqueness when the same script name
    is scheduled from different project directories.
    """
    slug = _slugify(script)
    root_hash = hashlib.sha256(project_root.encode()).hexdigest()[:4]
    return f"{slug}-{root_hash}"


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

    def pause(self, job: ScheduleJob) -> None:
        """Pause a scheduled job (stop triggering without removing it)."""
        raise NotImplementedError

    def resume(self, job: ScheduleJob) -> None:
        """Resume a previously paused job."""
        raise NotImplementedError
