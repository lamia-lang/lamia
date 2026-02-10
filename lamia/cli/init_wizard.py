"""Interactive init wizard for ``lamia init``."""

import asyncio
import logging
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from lamia.adapters.llm.local.ollama_adapter import OllamaAdapter
from lamia.cli.scaffold import (
    DEFAULT_MODELS,
    OLLAMA_SUGGESTED_MODELS,
    PROVIDER_ORDER,
    REMOTE_PROVIDER_MODELS,
)
from lamia.env_loader import get_global_lamia_dir, get_global_env_path, get_project_env_path
from lamia.engine.managers.llm.providers import ProviderRegistry

logger = logging.getLogger(__name__)

_MAX_SUGGESTED_CHAIN_LENGTH = 3
_PROVIDER_REGISTRY = ProviderRegistry(set(PROVIDER_ORDER))
_PLACEHOLDER_TOKENS = ("your-", "your_", "your ", "replace", "example", "dummy", "test-key")


@dataclass
class ModelChainEntry:
    """A single entry in the model chain."""
    name: str        # e.g. "anthropic:claude-haiku-4-5-20251001"
    max_retries: int  # e.g. 2


@dataclass
class WizardResult:
    """Output of the init wizard, consumed by scaffold functions."""
    model_chain: list[ModelChainEntry] = field(default_factory=list)
    with_extensions: bool = False


def run_init_wizard(project_dir: str, with_extensions: bool = False) -> WizardResult:
    """Run the interactive init wizard."""
    result = WizardResult(with_extensions=with_extensions)
    print("\n=== Lamia Project Setup ===\n")

    # Detect remote providers
    print("Detected providers:")
    provider_list: list[tuple[str, str]] = []
    for provider in REMOTE_PROVIDER_MODELS:
        key, env_var, source = _detect_api_key(provider, project_dir)
        label = f"{env_var} found via {source}" if key else "no API key"
        provider_list.append((provider, label))
        print(f"  - {provider:<11}({label})")

    # Detect Ollama
    ollama_models: list[str] = []
    adapter = OllamaAdapter()
    if adapter.is_ollama_installed():
        if not adapter.is_ollama_running():
            print("Starting Ollama service...")
            started = adapter.start_ollama_service()
            print("  Ollama service started." if started else "  Could not start Ollama — it may need to be started manually.")
        if adapter.is_ollama_running():
            ollama_models = asyncio.run(adapter.get_available_models())
        status = f"installed, {len(ollama_models)} models" if ollama_models else "installed"
        provider_list.append(("ollama", status))
    else:
        provider_list.append(("ollama", "not installed"))
    print(f"  - {'ollama':<11}({provider_list[-1][1]})")

    print("\nConfigure your default model and optional fallback models.")
    print("The default model handles all requests. Fallbacks are tried if it fails after retries.")
    print("(You can always override the model per-call in Lamia scripts — for advanced usage.)")
    print("(Not sure which models to pick? Terminate this process and run 'lamia eval' to see which model works best for your script/commands.)\n")

    default_provider_idx = 0

    entry = _pick_chain_entry(project_dir, "Default model", provider_list, default_provider_idx, ollama_models)
    result.model_chain.append(entry)

    fallback_num = 1
    while True:
        if fallback_num < _MAX_SUGGESTED_CHAIN_LENGTH:
            add = _input_yes_no(f"\n  Add {'a' if fallback_num == 1 else 'another'} fallback model?", default=True)
        else:
            add = _input_yes_no(f"\n  Add another fallback? ({fallback_num - 1} fallback(s) is usually sufficient)", default=False)
        if not add:
            break
        entry = _pick_chain_entry(project_dir, f"Fallback model {fallback_num}", provider_list, default_provider_idx, ollama_models)
        result.model_chain.append(entry)
        fallback_num += 1

    print("\n=== Configuration Summary ===\n")
    for i, e in enumerate(result.model_chain):
        label = "Default:" if i == 0 else f"Fallback {i}:"
        print(f"  {label:12s} {e.name} (retries: {e.max_retries})")
    print()
    return result


# ── Chain entry picker ───────────────────────────────────────────────────

def _pick_chain_entry(
    project_dir: str,
    label: str,
    provider_list: list[tuple[str, str]],
    default_provider_idx: int,
    ollama_models: list[str],
) -> ModelChainEntry:
    """Interactively pick one provider + model + retries."""
    print(f"\n--- {label} ---")
    provider = _pick_from_list("Provider", provider_list, default_provider_idx)

    if provider == "ollama":
        if ollama_models:
            models = [(m, "installed") for m in ollama_models]
        else:
            models = OLLAMA_SUGGESTED_MODELS
        default_model = ollama_models[0] if ollama_models else DEFAULT_MODELS["ollama"]
    else:
        models = REMOTE_PROVIDER_MODELS.get(provider, [])
        default_model = DEFAULT_MODELS.get(provider, models[0][0] if models else "")

    default_model_idx = next((i for i, (n, _) in enumerate(models) if n == default_model), 0)
    model = _pick_from_list("Model", models, default_model_idx)

    retries = _input_number("  Max retries [default: 2]: ", max_val=10, default=2)
    _handle_api_key(project_dir, provider)
    return ModelChainEntry(name=f"{provider}:{model}", max_retries=retries)


# ── Generic numbered-list picker ─────────────────────────────────────────

def _pick_from_list(heading: str, items: list[tuple[str, str]], default_idx: int = 0) -> str:
    """Show a numbered list of ``(value, description)`` tuples and return the chosen value."""
    print(f"  {heading}:")
    for i, (name, desc) in enumerate(items, 1):
        marker = " (default)" if i == default_idx + 1 else ""
        suffix = f" ({desc})" if desc else ""
        print(f"    {i}. {name}{suffix}{marker}")
    idx = _input_number(f"  Select number [default: {default_idx + 1}]: ", len(items), default_idx + 1)
    return items[idx - 1][0]


# ── Primitive input helpers ──────────────────────────────────────────────

def _input_yes_no(prompt: str, default: bool = True) -> bool:
    suffix = " [Y/n]: " if default else " [y/N]: "
    while True:
        raw = input(prompt + suffix).strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  Please answer yes or no (y/n).")


def _input_number(prompt: str, max_val: int, default: int = 1) -> int:
    """Ask user to pick a 1-based number."""
    while True:
        raw = input(prompt).strip()
        if not raw:
            return default
        if raw.lower() in ("q", "quit", "exit"):
            return default
        try:
            val = int(raw)
            if 1 <= val <= max_val:
                return val
        except ValueError:
            pass
        print(f"  Please enter a number between 1 and {max_val}.")


# ── API key detection ────────────────────────────────────────────────────

def _detect_api_key(provider: str, project_dir: str) -> tuple[Optional[str], str, Optional[str]]:
    """Return ``(value, env_var_name, source_label)`` or ``(None, var, None)``."""
    env_vars = _PROVIDER_REGISTRY.get_env_var_names(provider)
    if not env_vars:
        return None, provider, None
    project_env = get_project_env_path(Path(project_dir))
    global_env = get_global_env_path()
    for env_var in env_vars:
        value = os.getenv(env_var)
        if not value or _is_placeholder(value):
            continue
        project_val = _read_env_var_from_file(project_env, env_var)
        if project_val and not _is_placeholder(project_val) and project_val == value:
            return value, env_var, str(project_env)
        global_val = _read_env_var_from_file(global_env, env_var)
        if global_val and not _is_placeholder(global_val) and global_val == value:
            return value, env_var, str(global_env)
        return value, env_var, "shell environment"
    return None, env_vars[0], None


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


# ── API key storage ──────────────────────────────────────────────────────

def _primary_env_var_for_provider(provider: str) -> str:
    """Return the primary env var name from provider adapter metadata.

    Raises ``ValueError`` if no adapter defines env vars for *provider*.
    """
    env_vars = _PROVIDER_REGISTRY.get_env_var_names(provider)
    if not env_vars:
        raise ValueError(f"No env var defined for unknown provider '{provider}' — register an adapter first")
    return env_vars[0]


def _handle_api_key(project_dir: str, provider: str) -> bool:
    """Check / ask for an API key.  Returns True if the provider is usable."""
    if provider == "ollama":
        return True
    key, _, _ = _detect_api_key(provider, project_dir)
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
    if _input_yes_no(f"  Store this key globally in {global_env} for all Lamia projects?\n  (It will be available even for already existing projects)"):
        _save_key(global_env, env_var, api_key, secure=True)
        print(f"  Saved {provider} key to {global_env} (available for all projects).")
    else:
        local_env = get_project_env_path(Path(project_dir))
        _save_key(local_env, env_var, api_key, secure=True)
        print(f"  Saved {provider} key to {local_env}.")
    return True


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