"""Shared ID generation for schedules, triggers, and all named resources.

Format: bare 12-character hex string, e.g. ``a3f7c2e1b9d0``.
IDs are generated once at creation time and stored in the registry.
The ``lamia-`` prefix for GCP resource names is added by lamia-cloud.
"""

import hashlib
import uuid


def generate_unique_id() -> str:
    """Generate a globally unique 12-hex resource ID."""
    return uuid.uuid4().hex[:12]


def generate_deterministic_id(script: str, project_root: str) -> str:
    """Deterministic 12-hex ID for a (script, project_root) pair.

    Same inputs always produce the same ID, enabling idempotent deploys:
    re-deploying the same script reuses existing cloud resources instead
    of creating duplicates.
    """
    raw = f"{script}:{project_root}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


generate_id = generate_unique_id
