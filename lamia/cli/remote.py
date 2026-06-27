"""Handle `lamia <script> --remote` — one-shot remote cloud execution."""

import hashlib
import sys
from pathlib import Path
from typing import Optional


def handle_remote_run(
    script: str,
    project_root: str,
    config: Optional[dict],
    verbose: bool,
) -> None:
    """Execute a .lm script remotely and report results."""
    if not script:
        print("Error: --remote requires a script file", file=sys.stderr)
        sys.exit(1)

    try:
        from lamia_cloud.gcp.deployer import (
            _collect_project_files, _job_name, deploy, run_job, fetch_execution_logs,
        )
    except ImportError:
        print(
            'Error: lamia-cloud not installed.\n'
            'Install with: pip install "lamia-lang[cloud]"',
            file=sys.stderr,
        )
        sys.exit(1)

    cloud_cfg = (config or {}).get("cloud", {})
    project_id = cloud_cfg.get("project_id")
    location = cloud_cfg.get("location", "us-central1")

    if not project_id:
        print(
            "Error: cloud.project_id not set in config.yaml.\n"
            "Add:\n  cloud:\n    project_id: your-gcp-project",
            file=sys.stderr,
        )
        sys.exit(1)

    root = Path(project_root)
    script_name = Path(script).name
    schedule_id = f"run-{_slugify(script_name)}"
    job_name = _job_name(schedule_id)

    print(f"Remote execution: {script_name}", file=sys.stderr)

    source_hash = _compute_source_hash(root, _collect_project_files)
    deployed_hash = _get_deployed_hash(project_id, location, job_name)

    if source_hash == deployed_hash:
        print("  Container up to date, skipping build.", file=sys.stderr)
    else:
        print("  Building and deploying...", file=sys.stderr)
        deploy(
            project_id=project_id,
            location=location,
            project_root=root,
            script_name=script_name,
            schedule_id=schedule_id,
        )
        _set_deployed_hash(project_id, location, job_name, source_hash)

    print("  Running...", file=sys.stderr)
    result = run_job(
        project_id=project_id,
        location=location,
        job_name=job_name,
        verbose=verbose,
    )

    stdout, stderr = fetch_execution_logs(
        project_id=project_id,
        job_name=job_name,
        execution_name=result.get("execution_name", ""),
    )

    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)

    exit_code = result.get("exit_code", 1)
    elapsed = result.get("elapsed_seconds", 0)
    logs_url = result.get("logs_url", "")

    if elapsed:
        print(f"\n  Completed in {elapsed:.1f}s", file=sys.stderr)
    if logs_url:
        print(f"  Logs: {logs_url}", file=sys.stderr)

    sys.exit(exit_code)


def _slugify(name: str) -> str:
    stem = Path(name).stem
    slug = "".join(c if c.isalnum() else "-" for c in stem.lower()).strip("-")
    return slug[:20]


def _compute_source_hash(project_root: Path, collect_fn) -> str:
    """SHA256 of all project source files for change detection."""
    hasher = hashlib.sha256()
    for f in sorted(collect_fn(project_root)):
        hasher.update(str(f.relative_to(project_root)).encode())
        hasher.update(f.read_bytes())
    return hasher.hexdigest()[:16]


def _get_deployed_hash(project_id: str, location: str, job_name: str) -> Optional[str]:
    """Read source hash from deployed container metadata."""
    try:
        from google.cloud import run_v2
        client = run_v2.JobsClient()
        name = f"projects/{project_id}/locations/{location}/jobs/{job_name}"
        job = client.get_job(request={"name": name})
        return (job.labels or {}).get("lamia-source-hash")
    except Exception:
        return None


def _set_deployed_hash(project_id: str, location: str, job_name: str, hash_val: str) -> None:
    """Store source hash in deployed container metadata."""
    try:
        from google.cloud import run_v2
        client = run_v2.JobsClient()
        name = f"projects/{project_id}/locations/{location}/jobs/{job_name}"
        job = client.get_job(request={"name": name})
        if job.labels is None:
            job.labels = {}
        job.labels["lamia-source-hash"] = hash_val
        client.update_job(job=job)
    except Exception:
        pass
