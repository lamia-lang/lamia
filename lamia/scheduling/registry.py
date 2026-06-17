"""Global schedule registry stored at ~/.lamia/schedules/.

Each scheduled job is persisted as a single JSON file (<id>.json) that holds
both the job configuration and its last run status.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .base import ScheduleJob, generate_schedule_id

SCHEDULES_DIR = Path.home() / ".lamia" / "schedules"


def _ensure_dir() -> Path:
    SCHEDULES_DIR.mkdir(parents=True, exist_ok=True)
    return SCHEDULES_DIR


def _job_file(job_id: str) -> Path:
    return SCHEDULES_DIR / f"{job_id}.json"


def save_job(job: ScheduleJob, lamia_bin: str, *, backend: str = "local") -> str:
    """Persist a job to the global registry. Returns the job ID."""
    _ensure_dir()
    path = _job_file(job.schedule_id)

    existing = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            existing = {}

    data = {
        "id": job.schedule_id,
        "script": job.script,
        "cron": job.cron,
        "catch_up": job.catch_up,
        "project_root": str(job.project_root),
        "lamia_bin": lamia_bin,
        "backend": backend,
    }
    if "last_run" in existing:
        data["last_run"] = existing["last_run"]

    path.write_text(json.dumps(data, indent=2))
    return job.schedule_id


def load_job(job_id: str) -> Optional[dict]:
    """Load a job by ID from the registry."""
    path = _job_file(job_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def remove_job(job_id: str) -> bool:
    """Remove a job from the registry. Returns True if it existed."""
    path = _job_file(job_id)
    if not path.exists():
        return False
    path.unlink()
    return True


def list_jobs() -> list[dict]:
    """List all registered scheduled jobs."""
    _ensure_dir()
    jobs = []
    seen_ids = set()
    for path in SCHEDULES_DIR.glob("*.json"):
        try:
            job_data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        job_data = _normalize_job_data(path, job_data)
        if not job_data:
            continue
        job_id = job_data.get("id")
        if not job_id or job_id in seen_ids:
            continue
        seen_ids.add(job_id)
        jobs.append(job_data)
    return jobs


def find_job_by_script(script: str, project_root: str) -> Optional[dict]:
    """Find an existing job by script + project_root combo.

    Checks both the current ID format and legacy hash-based IDs.
    """
    job_id = generate_schedule_id(script, project_root)
    result = load_job(job_id)
    if result:
        return result
    legacy_id = hashlib.sha256(f"{project_root}:{script}".encode()).hexdigest()[:12]
    return load_job(legacy_id)


def record_run(job_id: str, exit_code: int, error: str = "") -> None:
    """Record the result of a scheduled run into the job file."""
    _ensure_dir()
    path = _job_file(job_id)

    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}

    data["last_run"] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "exit_code": exit_code,
        "success": exit_code == 0,
        "error": error,
    }
    path.write_text(json.dumps(data, indent=2))


def set_paused(job_id: str, paused: bool) -> bool:
    """Set the paused flag on a job. Returns True if job exists."""
    path = _job_file(job_id)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    data["paused"] = paused
    path.write_text(json.dumps(data, indent=2))
    return True


def get_last_run_status(job_id: str) -> Optional[dict]:
    """Get the last run status for a job."""
    job_data = load_job(job_id)
    if not job_data:
        return None
    return job_data.get("last_run")


def _normalize_job_data(path: Path, job_data: dict) -> Optional[dict]:
    """Normalize legacy schedule files that lack an 'id' field."""
    if not isinstance(job_data, dict):
        return None

    script = job_data.get("script")
    project_root = job_data.get("project_root")
    if not script or not project_root:
        return None

    job_id = job_data.get("id")
    if not job_id:
        job_id = generate_schedule_id(script, project_root)
        job_data["id"] = job_id

    job_data.setdefault("catch_up", True)
    job_data.setdefault("lamia_bin", "")

    canonical_path = _job_file(job_id)
    if path != canonical_path:
        try:
            canonical_path.write_text(json.dumps(job_data, indent=2))
            path.unlink(missing_ok=True)
        except OSError:
            pass

    return job_data
