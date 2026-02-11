"""Shared API key detection and storage utilities."""

import logging
import os
import stat
from pathlib import Path
from typing import Optional

from lamia.cli.prompts import input_yes_no
from lamia.cli.scaffold import PROVIDER_ORDER
from lamia.engine.managers.llm.providers import ProviderRegistry
from lamia.env_loader import get_global_env_path, get_project_env_path

logger = logging.getLogger(__name__)

_PROVIDER_REGISTRY = ProviderRegistry(set(PROVIDER_ORDER))
_PLACEHOLDER_TOKENS = ("your-", "your_", "your ", "replace", "example", "dummy", "test-key")


def detect_api_key(provider: str, project_dir: str) -> tuple[Optional[str], str, Optional[str]]:
    """Return ``(value, env_var_name, source_label)`` or ``(None, var, None)``."""
    env_vars = _PROVIDER_REGISTRY.get_env_var_names(provider)
    if not env_vars:
        return None, provider, None
    project_env = get_project_env_path(Path(project_dir))
    global_env = get_global_env_path()
    for env_var in env_vars:
        project_val = _read_env_var_from_file(project_env, env_var)
        if project_val and not _is_placeholder(project_val):
            return project_val, env_var, str(project_env)
        global_val = _read_env_var_from_file(global_env, env_var)
        if global_val and not _is_placeholder(global_val):
            return global_val, env_var, str(global_env)
        shell_val = os.getenv(env_var)
        if shell_val and not _is_placeholder(shell_val):
            return shell_val, env_var, "shell environment"
    return None, env_vars[0], None


def handle_api_key(project_dir: str, provider: str) -> bool:
    """Check / ask for an API key.  Returns True if the provider is usable."""
    if provider == "ollama":
        return True
    key, _, _ = detect_api_key(provider, project_dir)
    if key:
        print(f"  {provider}: API key already configured.")
        return True
    env_var = _primary_env_var_for_provider(provider)
    print(f"\n  No {env_var} found in your environment.")
    api_key = input(f"  Enter your {provider} API key (or press Enter to skip): ").strip()
    if not api_key:
        print(f"  Warning: {provider} will fail at runtime without a key. Set {env_var} before running.")
        return True
    global_env = get_global_env_path()
    if input_yes_no(f"  Store this key globally in {global_env} for all Lamia projects?\n  (It will be available even for already existing projects)"):
        _save_key(global_env, env_var, api_key, secure=True)
        print(f"  Saved {provider} key to {global_env} (available for all projects).")
    else:
        local_env = get_project_env_path(Path(project_dir))
        _save_key(local_env, env_var, api_key, secure=True)
        print(f"  Saved {provider} key to {local_env}.")
    return True


def _is_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    return any(token in normalized for token in _PLACEHOLDER_TOKENS)


def _read_env_var_from_file(env_path: Path, env_var: str) -> Optional[str]:
    """Read a single env var value from a .env file without loading it."""
    if not env_path.is_file():
        return None
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() == env_var:
            return value.strip()
    return None


def _primary_env_var_for_provider(provider: str) -> str:
    """Return the primary env var name from provider adapter metadata."""
    env_vars = _PROVIDER_REGISTRY.get_env_var_names(provider)
    if not env_vars:
        raise ValueError(f"No env var defined for unknown provider '{provider}' — register an adapter first")
    return env_vars[0]


def _save_key(env_path: Path, env_var: str, api_key: str, secure: bool = False) -> None:
    """Upsert ``env_var=api_key`` into *env_path* and set it in the process env."""
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = env_path.read_text().splitlines() if env_path.is_file() else []
    key_line = f"{env_var}={api_key}"
    replaced = False
    for i, line in enumerate(lines):
        if line.startswith(f"{env_var}="):
            lines[i] = key_line
            replaced = True
            break
    if not replaced:
        if not lines or lines[0] != "# Lamia global API keys (shared across all projects)":
            lines.insert(0, "# Lamia global API keys (shared across all projects)")
        lines.append(key_line)
    env_path.write_text("\n".join(lines) + "\n")
    if secure:
        try:
            env_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            logger.warning("Could not set secure permissions on %s — please set manually to 600", env_path)
    os.environ[env_var] = api_key
