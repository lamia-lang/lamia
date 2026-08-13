"""Handle `lamia <script> --remote` — one-shot remote cloud execution."""

import hashlib
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from lamia.git import get_remote_origin
from lamia.id_gen import generate_deterministic_id
from lamia.interpreter.ast_analyzer import extract_script_file_refs
from lamia.triggers.extraction import extract_all_triggers
from lamia.cli.script_analysis import analyze_script
from lamia_cloud import get_connector, get_deployer, get_trigger_provider
from lamia_cloud.file_sync import build_file_sync_plan
from lamia_cloud.types import TriggerDeploymentPlan


def _is_ci() -> bool:
    """Detect CI environment for UX adjustments only.

    SECURITY: this is NEVER used for authorization decisions.
    Authorization comes from WIF OIDC token exchange verified by GCP.
    Spoofing this env var locally has no security impact -- the OIDC
    token exchange will fail without a valid GitHub Actions runtime.
    """
    return os.environ.get("GITHUB_ACTIONS") == "true"


# Events that run only code already merged into the target branch.
_ALLOWED_CI_EVENTS = frozenset(
    {"push", "workflow_dispatch", "schedule", "release"}
)


def _reject_dangerous_event() -> None:
    """Reject CI auth for events outside _ALLOWED_CI_EVENTS."""
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    if event and event not in _ALLOWED_CI_EVENTS:
        allowed = ", ".join(sorted(_ALLOWED_CI_EVENTS))
        print(
            f"ERROR: Refusing to authenticate for '{event}' event.\n"
            "This trigger can run code that was never merged to the deploy "
            "branch, with production credentials.\n"
            f"Supported events: {allowed}.",
            file=sys.stderr,
        )
        sys.exit(1)


def _connected_repo_url() -> str:
    """Repository URL for this CI run, from GITHUB_REPOSITORY."""
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not repository:
        print(
            "ERROR: GITHUB_REPOSITORY is not set.\n"
            "Lamia CI authentication requires a GitHub Actions runner.",
            file=sys.stderr,
        )
        sys.exit(1)
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    return f"{server}/{repository}"


def _validate_connected_repo(connected_repo: str) -> None:
    """Verify the workspace git remote matches the repository being built."""
    from lamia.git import canonical_remote_identity
    workspace_remote = get_remote_origin(os.getcwd())
    if not workspace_remote:
        return

    expected = canonical_remote_identity(connected_repo)
    actual = canonical_remote_identity(workspace_remote)
    if expected and actual and expected != actual:
        print(
            f"ERROR: Git remote mismatch.\n"
            f"  GitHub Actions repository: {expected}\n"
            f"  workspace git remote:      {actual}\n"
            f"Refusing to authenticate. This could indicate a tampered "
            f"git remote.",
            file=sys.stderr,
        )
        sys.exit(1)


def _validate_connection_matches_repo(connection_id: str, connected_repo: str) -> None:
    """Reject a connection ID whose repository digest is not this repo."""
    from lamia_cloud import connection_suffix_for_repo, parse_connection_id

    _, suffix = parse_connection_id(connection_id)
    if suffix != connection_suffix_for_repo(connected_repo):
        print(
            "ERROR: LAMIA_CONNECTION_ID was issued for a different repository.\n"
            f"  this repository: {connected_repo}\n"
            "Run `lamia cloud connect` in this repository.",
            file=sys.stderr,
        )
        sys.exit(1)


def _setup_ci_auth_if_needed(project_root: Path) -> None:
    """In CI, authenticate using LAMIA_CONNECTION_ID. No-op otherwise."""
    if not _is_ci():
        return

    _reject_dangerous_event()

    connected_repo = _connected_repo_url()
    connection_id = os.environ.get("LAMIA_CONNECTION_ID", "")

    if not connection_id:
        print(
            "ERROR: Missing CI auth variable LAMIA_CONNECTION_ID.\n"
            "Add it to the deploy job:\n"
            "  env:\n"
            "    LAMIA_CONNECTION_ID: ${{ vars.LAMIA_CONNECTION_ID }}\n"
            "`lamia cloud connect` stores the value as a repository variable; "
            "the workflow only has to reference it.",
            file=sys.stderr,
        )
        sys.exit(1)

    _validate_connection_matches_repo(connection_id, connected_repo)
    _validate_connected_repo(connected_repo)

    try:
        get_connector(project_root).configure_ci_auth(connected_repo, connection_id)
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: CI authentication failed: {exc}", file=sys.stderr)
        sys.exit(1)


def _resolve_deploy_mode(
    config: Optional[dict], project_root: Path,
) -> tuple[str, str | None]:
    """Determine deploy_mode and repo_url from config and git state.

    Returns (deploy_mode, repo_url).
    """
    cloud_cfg = (config or {}).get("cloud", {})
    explicit_mode = cloud_cfg.get("deploy_mode")

    if explicit_mode == "local":
        return "local", None

    repo_url = get_remote_origin(str(project_root))

    if explicit_mode == "git":
        if not repo_url:
            print(
                "Warning: deploy_mode is 'git' but no git remote found. "
                "Falling back to local mode.",
                file=sys.stderr,
            )
            return "local", None
        return "git", repo_url

    if repo_url:
        return "git", repo_url

    return "local", None


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

    root = Path(project_root)

    _setup_ci_auth_if_needed(root)

    deployer = get_deployer(root)
    deployer.ensure_apis_enabled()

    script_path = Path(script)
    if script_path.is_absolute():
        script_name = str(script_path.relative_to(root))
    else:
        script_name = str(script_path)

    stages = extract_all_triggers(root / script_name)
    if stages:
        _deploy_trigger(script_name, root, stages)
        return

    deploy_mode, repo_url = _resolve_deploy_mode(config, root)
    run_name = _run_service_name(script_name, str(root))
    target = deployer.deployment_name(run_name)

    print(f"Remote execution: {script_name} (source: {deploy_mode})", file=sys.stderr)

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

    sync_feedback = deployer.sync_runtime_files(entries=entries)
    for overwrite in sync_feedback.get("overwrite_warnings", []):
        print(f"  Warning: {overwrite}", file=sys.stderr)
    if sync_feedback.get("uploaded", 0):
        print(
            f"  Synced files: uploaded={sync_feedback['uploaded']}, "
            f"skipped={sync_feedback.get('skipped', 0)}",
            file=sys.stderr,
        )

    source_hash = _compute_source_hash(root, deployer)
    deployed_hash = deployer.get_deployed_source_hash(target)

    uses_files = capabilities.uses_files or capabilities.uses_file_context

    if source_hash == deployed_hash:
        print("  Container up to date, skipping build.", file=sys.stderr)
    else:
        print("  Building and deploying...", file=sys.stderr)
        deployer.deploy(
            project_root=root,
            script_name=script_name,
            name=run_name,
            capabilities=asdict(capabilities),
            uses_files=uses_files,
            deploy_mode=deploy_mode,
            repo_url=repo_url,
        )
        deployer.set_deployed_source_hash(target, source_hash)

    print("  Running...", file=sys.stderr)
    result = {}
    run_error = None
    try:
        result = deployer.run_job(target=target, verbose=verbose)
    except Exception as exc:
        run_error = exc

    logs_unavailable = False
    try:
        stdout, stderr = deployer.fetch_execution_logs(
            target=target,
            execution_name=result.get("execution_name", ""),
        )
    except Exception as log_error:
        stdout, stderr = "", ""
        logs_unavailable = True
        print(f"  Failed to fetch container logs: {log_error}", file=sys.stderr)

    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)

    exit_code = result.get("exit_code", 1)
    elapsed = result.get("elapsed_seconds", 0)
    logs_url = result.get("logs_url", "")

    if elapsed:
        print(f"\n  Completed in {elapsed:.1f}s", file=sys.stderr)
    if logs_url and (exit_code != 0 or logs_unavailable):
        print(f"  Logs: {logs_url}", file=sys.stderr)

    try:
        cleaned = deployer.cleanup_stale_resources()
        for name in cleaned:
            print(f"  Cleaned up stale resource: {name}", file=sys.stderr)
    except Exception:
        pass

    if run_error:
        raise run_error

    sys.exit(exit_code)


def _deploy_trigger(
    script_name: str,
    project_root: Path,
    stages: list,
) -> None:
    """Deploy always-reactive trigger infrastructure for a script with trigger.* calls.

    Uses a deterministic name so re-deploying the same script updates
    existing cloud resources instead of creating duplicates.
    """
    name = generate_deterministic_id(script_name, str(project_root))
    capabilities = analyze_script(project_root / script_name)

    plan = TriggerDeploymentPlan(
        name=name,
        stages=stages,
        capabilities=asdict(capabilities),
        mode="reactive",
        script_name=script_name,
    )

    provider = get_trigger_provider(project_root)

    print(f"Deploying trigger: {script_name} ({len(stages)} stage(s))...", file=sys.stderr)
    print(f"  mode: always-reactive (event -> immediate execution)", file=sys.stderr)
    for i, stage in enumerate(stages):
        print(f"  stage {i}: {stage.trigger_method}", file=sys.stderr)

    deployment_id = provider.deploy(plan)
    print(f"\nDeployed: {deployment_id}", file=sys.stderr)
    print(f"View triggers: lamia trigger list", file=sys.stderr)


def _compute_source_hash(project_root: Path, deployer) -> str:
    hasher = hashlib.sha256()
    for f in sorted(deployer.collect_project_files(project_root)):
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


def _run_service_name(script: str, project_root: str) -> str:
    """Deterministic service name for one-shot remote runs.

    Derived from script + project_root so the same script always reuses
    the same cloud resource (enables container caching). This is an
    internal resource name, not a user-facing resource ID.
    """
    raw = f"{script}:{project_root}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
