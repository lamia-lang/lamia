"""
Environment variable loader for Lamia.

Loading priority (highest to lowest):
1. Actual environment variables (set in shell)
2. Project-level .env file (in current directory)
3. Global ~/.lamia/.env file (shared across all projects)
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Global Lamia config directory name (not a magic string)
LAMIA_GLOBAL_DIR_NAME = ".lamia"
LAMIA_GLOBAL_ENV_FILENAME = ".env"


def get_global_lamia_dir() -> Path:
    """Get the path to the global Lamia config directory (~/.lamia)."""
    return Path.home() / LAMIA_GLOBAL_DIR_NAME


def get_global_env_path() -> Path:
    """Get the path to the global Lamia .env file (~/.lamia/.env)."""
    return get_global_lamia_dir() / LAMIA_GLOBAL_ENV_FILENAME


try:
    from dotenv import load_dotenv

    # 1. Load project-level .env first (does NOT override existing shell env vars)
    load_dotenv()

    # 2. Load global ~/.lamia/.env as fallback (does NOT override anything already set)
    global_env_path = get_global_env_path()
    if global_env_path.exists():
        load_dotenv(global_env_path)
    elif global_env_path.parent.exists():
        # ~/.lamia dir exists but no .env file — that's fine, user may not have set up global keys yet
        pass
    else:
        # ~/.lamia dir doesn't exist — first-time user, nothing to warn about
        pass

except ImportError:
    # python-dotenv not installed, skip loading
    pass