"""
Environment variable loader for Lamia.

Loading priority (highest → lowest):
1. Shell environment variables (already set by the user)
2. Project-level ``.env`` in the current working directory
3. Global Lamia ``.env`` (shared across all projects)

SECURITY: We always pass an explicit path to ``load_dotenv`` because the
default behaviour walks up the directory tree, which can leak secrets from
parent directories in multi-tenant environments.
"""

import logging
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

LAMIA_GLOBAL_DIR_NAME = ".lamia"
ENV_FILENAME = ".env"


def get_global_lamia_dir() -> Path:
    """Return the path to the global Lamia config directory."""
    return Path.home() / LAMIA_GLOBAL_DIR_NAME


def get_global_env_path() -> Path:
    """Return the path to the global Lamia env file."""
    return get_global_lamia_dir() / ENV_FILENAME


def get_project_env_path(project_dir: Path) -> Path:
    """Return the path to the project-level env file."""
    return project_dir / ENV_FILENAME


def load_env_files() -> None:
    """Load project-level and global env files with explicit paths only."""
    project_env = get_project_env_path(Path.cwd())
    if project_env.is_file():
        load_dotenv(project_env)

    global_env = get_global_env_path()
    if global_env.is_file():
        load_dotenv(global_env)