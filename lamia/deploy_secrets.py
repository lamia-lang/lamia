"""Resolve the environment values a cloud deploy carries.

Secrets live in the project's ``.env``. Cloud containers never receive that
file, so a script that needs one in the cloud names it under ``cloud.secrets``
in ``config.yaml``; the value is resolved here and handed to the cloud
provider, which stores it and injects it as an environment variable at
runtime. Nothing that is not named there ever leaves the machine.
"""

import hashlib
import os
from pathlib import Path
from typing import Optional

from lamia.env_loader import get_global_env_path, get_project_env_path


def project_scope_id(project_dir: Path) -> str:
    """Return the namespace that separates one project's secrets from another's."""
    resolved = str(Path(project_dir).resolve())
    return hashlib.sha256(resolved.encode()).hexdigest()[:12]


def resolve_deploy_secrets(
    project_root: Path, declared_keys: Optional[list[str]] = None
) -> dict[str, str]:
    """Return values for the keys named in ``cloud.secrets``.

    Each value is taken from the project's ``.env``, then the global one, then
    the shell — the order :func:`lamia.cli.api_key_utils.detect_api_key` uses.
    Keys with no value are skipped.
    """
    if not declared_keys:
        return {}

    project_values = read_env_file(get_project_env_path(Path(project_root)))
    global_values = read_env_file(get_global_env_path())

    resolved: dict[str, str] = {}
    for key in sorted(declared_keys):
        value = project_values.get(key) or global_values.get(key) or os.getenv(key)
        if value:
            resolved[key] = value
    return resolved


def read_env_file(path: Path) -> dict[str, str]:
    """Return every ``KEY=value`` pair in a .env file, ignoring comments."""
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values
