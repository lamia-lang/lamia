"""Shared ID generation for schedules and triggers."""

import hashlib


def generate_unique_id(script: str, project_root: str) -> str:
    """Stable alphanumeric ID from script + project root.

    Format: 12-char hex hash, e.g. 'a3f2c8b1d4e5'.
    """
    raw = f"{project_root}:{script}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]
