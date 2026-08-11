"""Shared ID generation for schedules, triggers, and all named resources.

Format: bare 12-character hex string, e.g. ``a3f7c2e1b9d0``.
IDs are generated once at creation time and stored in the registry.
The ``lamia-`` prefix for GCP resource names is added by lamia-cloud.
"""

import hashlib
import re
import subprocess
import uuid
from urllib.parse import urlparse


def generate_unique_id() -> str:
    """Generate a globally unique 12-hex resource ID."""
    return uuid.uuid4().hex[:12]


def _normalize_remote_path(path: str) -> str:
    """Normalize repository path portion from a remote URL."""
    normalized = path.strip().lstrip("/").rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    return normalized


def _canonical_git_remote(remote_url: str) -> str | None:
    """Return canonical host/path identity for git remotes.

    Supports:
      - https://host/org/repo(.git)
      - ssh://git@host/org/repo(.git)
      - git@host:org/repo(.git)

    Returns None for local-only remotes (e.g. file://, relative paths).
    """
    raw = remote_url.strip()
    if not raw:
        return None

    # SCP-like syntax: git@host:org/repo.git
    scp_match = re.match(r"^[^@]+@([^:]+):(.+)$", raw)
    if scp_match:
        host = scp_match.group(1).lower()
        path = _normalize_remote_path(scp_match.group(2))
        return f"{host}/{path}" if path else None

    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https", "ssh", "git"} and parsed.hostname:
        host = parsed.hostname.lower()
        # Preserve explicit non-default port because enterprise instances may use it.
        if parsed.port is not None and parsed.port not in {80, 443}:
            host = f"{host}:{parsed.port}"
        path = _normalize_remote_path(parsed.path)
        return f"{host}/{path}" if path else None

    # file:// and local paths are machine-specific; avoid using them as shared anchors.
    return None


def _get_git_remote_origin(path: str) -> str | None:
    """Return canonical git remote identity, or None if unavailable."""
    try:
        result = subprocess.run(
            ["git", "-C", path, "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return _canonical_git_remote(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def generate_deterministic_id(script: str, project_root: str) -> str:
    """Deterministic 12-hex ID for a (script, project_root) pair.

    When inside a git repo with a network remote, the canonical remote
    identity (host/path) is used instead of the local path so that the same
    repo checked out at different locations (developer machine vs CI)
    produces the same ID. Local-only remotes fall back to project_root.
    """
    anchor = _get_git_remote_origin(project_root) or project_root
    raw = f"{script}:{anchor}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


generate_id = generate_unique_id
