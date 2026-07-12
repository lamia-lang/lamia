"""Bridge between lamia's BaseScheduler and lamia-cloud's CloudScheduler.

lamia-cloud is an independent package with its own types. This module
translates between lamia's ScheduleJob/BaseScheduler and lamia-cloud's
CloudScheduleJob/CloudScheduler.
"""
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import yaml

from lamia.scheduling.base import BaseScheduler, JobStatus, ScheduleJob
from lamia.scheduling.registry import set_paused
from lamia.cli.script_analysis import analyze_script, slugify

try:
    from lamia_cloud import get_scheduler, CloudScheduleJob, CloudJobStatus
    from lamia_cloud.gcp.trigger_provider import GCPTriggerProvider
    from lamia_cloud.types import TriggerDeploymentPlan
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


def deploy_scheduled_trigger(
    script_name: str,
    project_root: Path,
    cron: str,
    stages: list,
) -> None:
    """Deploy employee-mode trigger: events accumulate, scheduler drains at cron time."""
    if not LAMIA_CLOUD_AVAILABLE:
        print(
            "Error: trigger deployment requires the lamia-cloud package.\n"
            "Install with: pip install \"lamia-lang[cloud]\"",
            file=sys.stderr,
        )
        sys.exit(1)

    config_path = project_root / "config.yaml"
    if not config_path.exists():
        config_path = project_root / "config.yml"

    cloud_cfg: dict = {}
    if config_path.exists():
        with open(config_path) as f:
            full_config = yaml.safe_load(f) or {}
        cloud_cfg = full_config.get("cloud", {})

    if not cloud_cfg.get("project_id"):
        print(
            "Error: cloud.project_id not found in config.yaml.\n"
            "Add:\n  cloud:\n    project_id: your-gcp-project",
            file=sys.stderr,
        )
        sys.exit(1)

    name = slugify(script_name)
    capabilities = analyze_script(project_root / script_name)

    plan = TriggerDeploymentPlan(
        name=name,
        stages=stages,
        capabilities=asdict(capabilities),
        mode="scheduled",
        cron=cron,
    )

    provider = GCPTriggerProvider.from_config(cloud_cfg)

    print(f"Deploying scheduled trigger: {script_name} ({len(stages)} stage(s))...")
    print(f"  mode: employee (batch drain at schedule time)")
    print(f"  cron: {cron}")
    for i, stage in enumerate(stages):
        print(f"  stage {i}: {stage.trigger_method}")

    deployment_id = provider.deploy(plan)
    print(f"\nDeployed: {deployment_id}")
    print(f"View triggers: lamia trigger list")


def fetch_cloud_statuses(cloud_jobs: list[dict]) -> dict[str, dict | None]:
    """Fetch last execution statuses from Cloud Scheduler for all cloud jobs at once."""
    results: dict[str, dict | None] = {}
    if not LAMIA_CLOUD_AVAILABLE:
        return results

    try:
        by_project: dict[str, list[dict]] = {}
        for job in cloud_jobs:
            by_project.setdefault(job["project_root"], []).append(job)

        for project_root, jobs in by_project.items():
            try:
                scheduler = get_scheduler(Path(project_root))
                for job in jobs:
                    config = scheduler.get_installed_config(
                        CloudScheduleJob(
                            script=job["script"],
                            cron=job["cron"],
                            schedule_id=job["id"],
                            project_root=Path(project_root),
                        )
                    )
                    if config:
                        state = config.get("state", "UNKNOWN")
                        if state == "PAUSED":
                            set_paused(job["id"], True)
                        last_attempt = config.get("last_attempt_time")
                        if last_attempt:
                            results[job["id"]] = {
                                "timestamp": last_attempt,
                                "success": state == "ENABLED",
                                "state": state,
                            }
            except Exception:
                pass
    except Exception:
        pass
    return results
