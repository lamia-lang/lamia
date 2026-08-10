"""Global schedule registry stored at ~/.lamia/schedules/.

Each scheduled job is persisted as a single JSON file (<id>.json) that holds
both the job configuration and its last run status.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from lamia.id_gen import generate_unique_id
from lamia.persistence import atomic_write
from .base import ScheduleJob

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

    atomic_write(path, json.dumps(data, indent=2))
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
    """List all registered scheduled jobs.

    Deduplicates by (script, project_root) — if a legacy file and a
    canonical UUID file describe the same job, only the canonical one
    (whose filename matches its own id) is kept.

    Marks entries whose script file no longer exists on disk as orphaned.
    """
    _ensure_dir()
    jobs = []
    seen_keys: set[tuple[str, str]] = set()
    for path in SCHEDULES_DIR.glob("*.json"):
        try:
            job_data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        job_data = _normalize_job_data(path, job_data)
        if not job_data:
            continue

        backend = job_data.get("backend", "local")
        project_root = job_data.get("project_root", "")
        script = job_data.get("script", "")
        script_missing = False
        if backend == "local" and project_root and script:
            script_missing = not (Path(project_root) / script).exists()
        job_data["source_missing"] = script_missing
        if script_missing:
            job_data["last_status"] = "SOURCE_MISSING"

        key = (job_data.get("script", ""), job_data.get("project_root", ""))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        jobs.append(job_data)
    return jobs


def find_job_by_script(script: str, project_root: str) -> Optional[dict]:
    """Find an existing job by script + project_root combo.

    Scans all stored jobs since IDs are UUIDs and can't be regenerated.
    """
    for job in list_jobs():
        if job.get("script") == script and job.get("project_root") == project_root:
            return job
    return None


def record_run(job_id: str, exit_code: int, error: str = "") -> None:
    """Record the result of a scheduled run into the job file.

    Uses atomic write (temp file + rename) so a concurrent reader or a
    signal arriving mid-write never sees a half-written file.
    """
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
    atomic_write(path, json.dumps(data, indent=2))


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
    atomic_write(path, json.dumps(data, indent=2))
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
        job_id = generate_unique_id()
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
