"""Handle `lamia <script> --remote` — one-shot remote cloud execution."""

import hashlib
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from lamia.id_gen import generate_id, slugify
from lamia.interpreter.ast_analyzer import extract_script_file_refs
from lamia.triggers.extraction import extract_all_triggers
from lamia.cli.script_analysis import analyze_script
from lamia_cloud.file_sync import build_file_sync_plan
from lamia_cloud.gcp.deployer import (
    collect_project_files,
    deployment_name,
    deploy,
    fetch_execution_logs,
    get_deployed_source_hash,
    run_job,
    set_deployed_source_hash,
    sync_runtime_files,
)
from lamia_cloud.gcp.trigger_provider import GCPTriggerProvider
from lamia_cloud.types import TriggerDeploymentPlan


def handle_remote_run(
    script: str,
    project_root: str,
    config: Optional[dict],
    verbose: bool,
) -> None:
    """Execute a .lm script remotely, or deploy trigger infrastructure if script has triggers."""
    if not script:
        print("Error: --remote requires a script file", file=sys.stderr)
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
    script_path = Path(script)
    if script_path.is_absolute():
        script_name = str(script_path.relative_to(root))
    else:
        script_name = str(script_path)

    stages = extract_all_triggers(root / script_name)
    if stages:
        _deploy_trigger(script_name, root, cloud_cfg, stages)
        return

    run_name = slugify(script_name)
    target = deployment_name(run_name)

    print(f"Remote execution: {script_name}", file=sys.stderr)

    capabilities = analyze_script(root / script_name)
    try:
        entries = build_file_sync_plan(
            files_context_paths=extract_script_file_refs(root / script_name),
            project_root=root,
            local_home=Path.home(),
        )
    except Exception as exc:
        print(f"Error: file sync planning failed: {exc}", file=sys.stderr)
        sys.exit(1)
    _warn_about_file_uploads(entries)

    sync_feedback = sync_runtime_files(
        project_id=project_id,
        location=location,
        entries=entries,
    )
    for overwrite in sync_feedback.get("overwrite_warnings", []):
        print(f"  Warning: {overwrite}", file=sys.stderr)
    if sync_feedback.get("uploaded", 0):
        print(
            f"  Synced files: uploaded={sync_feedback['uploaded']}, "
            f"skipped={sync_feedback.get('skipped', 0)}",
            file=sys.stderr,
        )

    source_hash = _compute_source_hash(root)
    deployed_hash = get_deployed_source_hash(project_id, location, target)

    uses_files = capabilities.uses_files or capabilities.uses_file_context

    if source_hash == deployed_hash:
        print("  Container up to date, skipping build.", file=sys.stderr)
    else:
        print("  Building and deploying...", file=sys.stderr)
        deploy(
            project_id=project_id,
            location=location,
            project_root=root,
            script_name=script_name,
            name=run_name,
            capabilities=asdict(capabilities),
            uses_files=uses_files,
        )
        set_deployed_source_hash(project_id, location, target, source_hash)

    print("  Running...", file=sys.stderr)
    result = run_job(
        project_id=project_id,
        location=location,
        target=target,
        verbose=verbose,
    )

    stdout, stderr = fetch_execution_logs(
        project_id=project_id,
        target=target,
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


def _deploy_trigger(
    script_name: str,
    project_root: Path,
    cloud_cfg: dict,
    stages: list,
) -> None:
    """Deploy always-reactive trigger infrastructure for a script with trigger.* calls."""
    name = generate_id(script_name, str(project_root))
    capabilities = analyze_script(project_root / script_name)

    plan = TriggerDeploymentPlan(
        name=name,
        stages=stages,
        capabilities=asdict(capabilities),
        mode="reactive",
    )

    provider = GCPTriggerProvider.from_config(cloud_cfg)

    print(f"Deploying trigger: {script_name} ({len(stages)} stage(s))...", file=sys.stderr)
    print(f"  mode: always-reactive (event -> immediate execution)", file=sys.stderr)
    for i, stage in enumerate(stages):
        print(f"  stage {i}: {stage.trigger_method}", file=sys.stderr)

    deployment_id = provider.deploy(plan)
    print(f"\nDeployed: {deployment_id}", file=sys.stderr)
    print(f"View triggers: lamia trigger list", file=sys.stderr)


def _compute_source_hash(project_root: Path) -> str:
    hasher = hashlib.sha256()
    for f in sorted(collect_project_files(project_root)):
        hasher.update(str(f.relative_to(project_root)).encode())
        hasher.update(f.read_bytes())
    return hasher.hexdigest()[:16]


def _warn_about_file_uploads(entries: list) -> None:
    if not entries:
        return
    unique_paths = sorted({e.raw_path for e in entries})
    print("  Warning: this remote run will upload local files to cloud storage.", file=sys.stderr)
    for raw in unique_paths:
        print(f"    - {raw}", file=sys.stderr)


