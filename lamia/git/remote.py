"""Git remote detection and canonical identity parsing.

Works with any git host: GitHub, GitLab, Bitbucket, self-hosted Gitea,
enterprise instances, etc.  The canonical identity is ``host/path``
(no scheme, no credentials, no ``.git`` suffix) so that the same repo
cloned via HTTPS, SSH, or SCP-syntax all resolve to a single string.
"""

import re
import subprocess
from urllib.parse import urlparse


def _normalize_remote_path(path: str) -> str:
    """Normalize the path portion of a remote URL."""
    normalized = path.strip().lstrip("/").rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    return normalized


def canonical_remote_identity(remote_url: str) -> str | None:
    """Return canonical ``host/path`` identity for a git remote URL.

    Supports:
      - https://host/org/repo(.git)
      - ssh://git@host/org/repo(.git)
      - git@host:org/repo(.git)   (SCP-like)

    Returns None for local-only remotes (``file://``, relative paths)
    because those are machine-specific and cannot serve as shared anchors.
    """
    raw = remote_url.strip()
    if not raw:
        return None

    scp_match = re.match(r"^[^@]+@([^:]+):(.+)$", raw)
    if scp_match:
        host = scp_match.group(1).lower()
        path = _normalize_remote_path(scp_match.group(2))
        return f"{host}/{path}" if path else None

    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https", "ssh", "git"} and parsed.hostname:
        host = parsed.hostname.lower()
        if parsed.port is not None and parsed.port not in {80, 443}:
            host = f"{host}:{parsed.port}"
        path = _normalize_remote_path(parsed.path)
        return f"{host}/{path}" if path else None

    return None


def get_remote_origin(path: str) -> str | None:
    """Return the raw remote origin URL for the repo at *path*, or None."""
    try:
        result = subprocess.run(
            ["git", "-C", path, "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def get_canonical_remote(path: str) -> str | None:
    """Return the canonical ``host/path`` identity for the repo at *path*.

    Combines ``get_remote_origin`` and ``canonical_remote_identity``.
    Returns None if not a git repo or the remote is local-only.
    """
    raw = get_remote_origin(path)
    if raw is None:
        return None
    return canonical_remote_identity(raw)
