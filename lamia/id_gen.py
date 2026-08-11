"""Shared ID generation for schedules, triggers, and all named resources.

Format: bare 12-character hex string, e.g. ``a3f7c2e1b9d0``.
IDs are generated once at creation time and stored in the registry.
The ``lamia-`` prefix for GCP resource names is added by lamia-cloud.
"""

import hashlib
import uuid

from lamia.git import get_canonical_remote


def generate_unique_id() -> str:
    """Generate a globally unique 12-hex resource ID."""
    return uuid.uuid4().hex[:12]


def generate_deterministic_id(script: str, project_root: str) -> str:
    """Deterministic 12-hex ID for a (script, project_root) pair.

    When inside a git repo with a network remote, the canonical remote
    identity (host/path) is used instead of the local path so that the same
    repo checked out at different locations (developer machine vs CI)
    produces the same ID. Local-only remotes fall back to project_root.
    """
    anchor = get_canonical_remote(project_root) or project_root
    raw = f"{script}:{anchor}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


generate_id = generate_unique_id
