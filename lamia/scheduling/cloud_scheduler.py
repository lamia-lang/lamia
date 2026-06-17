"""Bridge between lamia's BaseScheduler and lamia-cloud's CloudScheduler.

lamia-cloud is an independent package with its own types. This module
translates between lamia's ScheduleJob/BaseScheduler and lamia-cloud's
CloudScheduleJob/CloudScheduler.
"""
import sys
from pathlib import Path
from typing import Optional

from lamia.scheduling.base import BaseScheduler, JobStatus, ScheduleJob

try:
    from lamia_cloud import get_scheduler, CloudScheduleJob, CloudJobStatus
    LAMIA_CLOUD_AVAILABLE = True
except ImportError:
    LAMIA_CLOUD_AVAILABLE = False


def _to_cloud_job(job: ScheduleJob) -> "CloudScheduleJob":
    """Convert lamia's ScheduleJob to lamia-cloud's CloudScheduleJob."""
    return CloudScheduleJob(
        script=job.script,
        cron=job.cron,
        schedule_id=job.schedule_id,
        catch_up=job.catch_up,
        project_root=job.project_root,
    )


def _to_lamia_status(status: "CloudJobStatus") -> JobStatus:
    """Convert lamia-cloud's CloudJobStatus to lamia's JobStatus."""
    return JobStatus(status.value)


class CloudSchedulerBridge(BaseScheduler):
    """Wraps lamia-cloud's CloudScheduler to implement lamia's BaseScheduler."""

    def __init__(self, cloud_scheduler):
        self._scheduler = cloud_scheduler

    @classmethod
    def name(cls) -> str:
        return "cloud"

    def install(self, job: ScheduleJob, lamia_bin: str) -> None:
        self._scheduler.install(_to_cloud_job(job), lamia_bin)

    def uninstall(self, job: ScheduleJob) -> None:
        self._scheduler.uninstall(_to_cloud_job(job))

    def is_installed(self, job: ScheduleJob) -> bool:
        return self._scheduler.is_installed(_to_cloud_job(job))

    def get_status(self, job: ScheduleJob) -> JobStatus:
        cloud_status = self._scheduler.get_status(_to_cloud_job(job))
        return _to_lamia_status(cloud_status)

    def get_installed_config(self, job: ScheduleJob) -> Optional[dict]:
        return self._scheduler.get_installed_config(_to_cloud_job(job))

    def pause(self, job: ScheduleJob) -> None:
        self._scheduler.pause(_to_cloud_job(job))

    def resume(self, job: ScheduleJob) -> None:
        self._scheduler.resume(_to_cloud_job(job))


def get_cloud_scheduler(project_root: Path) -> BaseScheduler:
    """Load the cloud scheduler from lamia-cloud and wrap it as BaseScheduler.

    Returns a CloudSchedulerBridge that implements lamia's BaseScheduler
    by delegating to lamia-cloud's independent CloudScheduler.
    """
    if not LAMIA_CLOUD_AVAILABLE:
        print(
            "Error: cloud scheduling requires the lamia-cloud package.\n"
            "Install with: pip install \"lamia-lang[cloud]\"\n"
            "See: https://lamia-lang.github.io/lamia/advanced/lamia-cloud/",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        cloud_scheduler = get_scheduler(project_root)
        return CloudSchedulerBridge(cloud_scheduler)
    except Exception as e:
        print(f"Error: cloud scheduler configuration failed: {e}", file=sys.stderr)
        sys.exit(1)
