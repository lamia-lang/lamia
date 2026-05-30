"""Global schedule registry stored at ~/.lamia/schedules/.

Each scheduled job is persisted as a JSON file. Run status is tracked
in a companion .status.json file per job.
"""

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .base import ScheduleJob

SCHEDULES_DIR = Path.home() / ".lamia" / "schedules"


def _ensure_dir() -> Path:
    SCHEDULES_DIR.mkdir(parents=True, exist_ok=True)
    return SCHEDULES_DIR


def _job_file(job_id: str) -> Path:
    return SCHEDULES_DIR / f"{job_id}.json"


def _status_file(job_id: str) -> Path:
    return SCHEDULES_DIR / f"{job_id}.status.json"


def _generate_id(script: str, project_root: str) -> str:
    raw = f"{project_root}:{script}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def save_job(job: ScheduleJob, lamia_bin: str) -> str:
    """Persist a job to the global registry. Returns the job ID."""
    _ensure_dir()
    job_id = _generate_id(job.script, str(job.project_root))
    data = {
        "id": job_id,
        "script": job.script,
        "cron": job.cron,
        "catch_up": job.catch_up,
        "project_root": str(job.project_root),
        "lamia_bin": lamia_bin,
    }
    _job_file(job_id).write_text(json.dumps(data, indent=2))
    return job_id


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
    if path.exists():
        path.unlink()
        # Also remove status file
        status = _status_file(job_id)
        if status.exists():
            status.unlink()
        return True
    return False


def list_jobs() -> list[dict]:
    """List all registered scheduled jobs, enriched with last run status."""
    _ensure_dir()
    jobs = []
    seen_ids = set()
    for path in SCHEDULES_DIR.glob("*.json"):
        if path.name.endswith(".status.json"):
            continue
        try:
            job_data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        job_data = _normalize_job_data(path, job_data)
        if not job_data:
            continue
        status = get_last_run_status(job_data.get("id", ""))
        if status:
            job_data["last_run"] = status
        job_id = job_data.get("id")
        if not job_id or job_id in seen_ids:
            continue
        seen_ids.add(job_id)
        jobs.append(job_data)
    return jobs


def find_job_by_script(script: str, project_root: str) -> Optional[dict]:
    """Find an existing job by script + project_root combo."""
    job_id = _generate_id(script, project_root)
    return load_job(job_id)


def record_run(job_id: str, exit_code: int, error: str = "") -> None:
    """Record the result of a scheduled run."""
    _ensure_dir()
    status = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "exit_code": exit_code,
        "success": exit_code == 0,
        "error": error,
    }
    _status_file(job_id).write_text(json.dumps(status, indent=2))


def get_last_run_status(job_id: str) -> Optional[dict]:
    """Get the last run status for a job."""
    path = _status_file(job_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _normalize_job_data(path: Path, job_data: dict) -> Optional[dict]:
    """Normalize legacy schedule files and migrate to canonical registry format.

    Older scheduler backends stored files without `id` and with non-hash filenames.
    This normalizes those entries and writes a canonical `<id>.json` file.
    """
    if not isinstance(job_data, dict):
        return None

    script = job_data.get("script")
    project_root = job_data.get("project_root")
    if not script or not project_root:
        return None

    job_id = job_data.get("id")
    if not job_id:
        job_id = _generate_id(script, project_root)
        job_data["id"] = job_id

    job_data.setdefault("catch_up", True)
    job_data.setdefault("lamia_bin", "")

    canonical_path = _job_file(job_id)
    if path != canonical_path:
        try:
            canonical_path.write_text(json.dumps(job_data, indent=2))
            # Remove legacy file after successful migration.
            path.unlink(missing_ok=True)
        except OSError:
            # If migration fails, still return normalized in-memory data.
            pass

    return job_data
