"""Pure-lamia helpers for remote execution — no lamia_cloud dependency."""

import os
import sys
from pathlib import Path
from typing import Optional

from lamia.git import get_remote_origin


ALLOWED_CI_EVENTS = frozenset(
    {"push", "workflow_dispatch", "schedule", "release"}
)


def is_ci() -> bool:
    """Detect CI environment for UX adjustments only.

    SECURITY: this is NEVER used for authorization decisions.
    Authorization comes from WIF OIDC token exchange verified by GCP.
    Spoofing this env var locally has no security impact -- the OIDC
    token exchange will fail without a valid GitHub Actions runtime.
    """
    return os.environ.get("GITHUB_ACTIONS") == "true"


def reject_dangerous_event() -> None:
    """Reject CI auth for events outside ALLOWED_CI_EVENTS."""
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    if event and event not in ALLOWED_CI_EVENTS:
        allowed = ", ".join(sorted(ALLOWED_CI_EVENTS))
        print(
            f"ERROR: Refusing to authenticate for '{event}' event.\n"
            "This trigger can run code that was never merged to the deploy "
            "branch, with production credentials.\n"
            f"Supported events: {allowed}.",
            file=sys.stderr,
        )
        sys.exit(1)


def connected_repo_url() -> str:
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


def validate_connected_repo(connected_repo: str) -> None:
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


def resolve_deploy_mode(
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


def declared_secret_keys(config: Optional[dict]) -> list[str]:
    """Return the secret names opted in under ``cloud.secrets`` in config."""
    return list(((config or {}).get("cloud") or {}).get("secrets") or [])


def warn_about_file_uploads(entries: list) -> None:
    if not entries:
        return
    unique_paths = sorted({e.raw_path for e in entries})
    print("  Warning: this remote run will upload local files to cloud storage.", file=sys.stderr)
    for raw in unique_paths:
        print(f"    - {raw}", file=sys.stderr)
