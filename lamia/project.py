"""Project-level utilities — config discovery, project root detection.

This module intentionally has **no** imports from the lamia package itself
so it can be used from both ``lamia.cli`` and ``lamia.engine`` without
circular-import issues.
"""

import os
from pathlib import Path

CONFIG_NAMES = ("config.yaml", "config.yml")


def find_config_file(start_path: str | None = None) -> str | None:
    """Walk up from *start_path* (or CWD) looking for config.yaml / config.yml.

    Returns the absolute path to the first config file found, or ``None``.
    """
    current = Path(start_path).resolve() if start_path else Path.cwd()
    if current.is_file():
        current = current.parent
    for directory in [current, *current.parents]:
        for name in CONFIG_NAMES:
            candidate = directory / name
            if candidate.is_file():
                return str(candidate)
    return None


def find_project_root(start_path: str) -> str | None:
    """Walk up from *start_path* looking for a project root (directory with config.yaml/yml)."""
    config = find_config_file(start_path)
    if config:
        return str(Path(config).parent)
    return None
