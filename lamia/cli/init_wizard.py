"""Interactive init wizard for ``lamia init``."""

import logging
import os
import stat
from dataclasses import dataclass, field
from typing import Optional

from lamia.adapters.llm.local.ollama_adapter import (
    is_ollama_installed,
    is_ollama_running,
    list_ollama_models_sync,
    start_ollama_service,
)
from lamia.cli.scaffold import (
    DEFAULT_MODELS,
    OLLAMA_MODELS,
    PROVIDER_ORDER,
    REMOTE_PROVIDER_MODELS,
)
from lamia.env_loader import get_global_lamia_dir, get_global_env_path
from lamia.engine.managers.llm.providers import ProviderRegistry

logger = logging.getLogger(__name__)

MAX_SUGGESTED_CHAIN_LENGTH = 3
_PROVIDER_REGISTRY = ProviderRegistry(set(PROVIDER_ORDER))


def _primary_env_var_for_provider(provider: str) -> str:
    """Return the primary env var name from provider adapter metadata."""
    env_vars = _PROVIDER_REGISTRY.get_env_var_names(provider)
    if env_vars:
        return env_vars[0]
    return f"{provider.upper()}_API_KEY"


def _is_placeholder_api_key(value: str) -> bool:
    normalized = value.strip().lower()
    placeholder_tokens = ("your-", "your_", "your ", "replace", "example", "dummy", "test-key")
    return any(token in normalized for token in placeholder_tokens)


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


def detect_api_key(provider: str) -> Optional[str]:
    """Return the key if a real API key is set in the environment, else None."""
    for env_var in _PROVIDER_REGISTRY.get_env_var_names(provider):
        value = os.getenv(env_var)
        if value and not _is_placeholder_api_key(value):
            return value
    return None


def save_global_key(provider: str, api_key: str) -> None:
    """Store an API key in ``~/.lamia/.env`` with 0600 permissions."""
    global_dir = get_global_lamia_dir()
    global_env = get_global_env_path()
    env_var = _primary_env_var_for_provider(provider)

    global_dir.mkdir(parents=True, exist_ok=True)

    existing_lines: list[str] = []
    if global_env.exists():
        existing_lines = global_env.read_text().splitlines()

    key_line = f"{env_var}={api_key}"
    updated = False
    for i, line in enumerate(existing_lines):
        if line.startswith(f"{env_var}="):
            existing_lines[i] = key_line
            updated = True
            break
    if not updated:
        if not existing_lines or existing_lines[0] != "# Lamia global API keys (shared across all projects)":
            existing_lines.insert(0, "# Lamia global API keys (shared across all projects)")
            existing_lines.insert(1, "# Security: this file should have 0600 permissions (owner-only read/write)")
        existing_lines.append(key_line)

    global_env.write_text("\n".join(existing_lines) + "\n")
    try:
        global_env.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        logger.warning("Could not set secure permissions on %s — please set manually to 600", global_env)

    os.environ[env_var] = api_key


def _save_local_key(project_dir: str, provider: str, api_key: str) -> None:
    """Save an API key to the project-local ``.env`` with 0600 permissions."""
    env_path = os.path.join(project_dir, ".env")
    env_var = _primary_env_var_for_provider(provider)

    lines: list[str] = []
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            lines = f.read().splitlines()

    key_line = f"{env_var}={api_key}"
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{env_var}="):
            lines[i] = key_line
            updated = True
            break
    if not updated:
        lines.append(key_line)

    with open(env_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    try:
        os.chmod(env_path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    os.environ[env_var] = api_key


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


def _pick_provider(available: list[tuple[str, str]], default_idx: int = 0) -> str:
    """Show numbered provider list and let the user pick one.

    ``available`` is a list of ``(name, status_label)`` tuples.
    """
    print("  Provider:")
    for i, (name, label) in enumerate(available, 1):
        marker = " (default)" if i == default_idx + 1 else ""
        suffix = f" ({label})" if label else ""
        print(f"    {i}. {name}{suffix}{marker}")
    idx = _input_number(f"  Select [{default_idx + 1}]: ", len(available), default_idx + 1)
    return available[idx - 1][0]


def _pick_model(provider: str, models: list[tuple[str, str]], default_model: str) -> str:
    """Show numbered model list and let the user pick one."""
    print(f"\n  Available {provider} models (cheapest → most capable):")
    for i, (name, desc) in enumerate(models, 1):
        marker = "  <-- default" if name == default_model else ""
        print(f"    {i}. {name}  — {desc}{marker}")
    while True:
        raw = input(f"  Select [default: {default_model}]: ").strip()
        if not raw:
            return default_model
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(models):
                return models[idx][0]
        except ValueError:
            model_names = [m[0] for m in models]
            if raw in model_names:
                return raw
        print(f"  Please enter a number between 1 and {len(models)} or a model name.")


def _pick_retries() -> int:
    return _input_number("  Max retries [default: 2]: ", max_val=10, default=2)


def _handle_api_key(project_dir: str, provider: str) -> bool:
    """Check / ask for an API key.  Returns True if the provider is usable."""
    if provider == "ollama":
        return True
    existing = detect_api_key(provider)
    if existing:
        print(f"  {provider}: API key already configured.")
        return True
    env_var = _primary_env_var_for_provider(provider)
    print(f"\n  No {env_var} found in your environment.")
    api_key = input(f"  Enter your {provider} API key (or press Enter to skip): ").strip()
    if not api_key:
        print(f"  Warning: {provider} will fail at runtime without a key. Set {env_var} before running.")
        return True  # still add to chain; user can set later
    store_globally = _input_yes_no(
        f"  Store this key globally in ~/.lamia/.env for all Lamia projects?\n"
        f"  (It will be available even for already existing projects)"
    )
    if store_globally:
        save_global_key(provider, api_key)
        print(f"  Saved {provider} key to ~/.lamia/.env (available for all projects).")
    else:
        _save_local_key(project_dir, provider, api_key)
        print(f"  Saved {provider} key to project .env file.")
    return True


def _build_provider_list(
    ollama_available: bool,
    ollama_model_count: int,
    openai_key: Optional[str],
    anthropic_key: Optional[str],
) -> list[tuple[str, str]]:
    """Build the available-providers list with status labels."""
    key_status: dict[str, Optional[str]] = {
        "openai": openai_key,
        "anthropic": anthropic_key,
    }
    providers: list[tuple[str, str]] = []
    for provider in PROVIDER_ORDER:
        if provider == "ollama":
            label = "not installed"
            if ollama_available:
                label = f"installed, {ollama_model_count} models" if ollama_model_count else "installed"
            providers.append((provider, label))
            continue
        providers.append((provider, "API key found" if key_status.get(provider) else ""))
    return providers


def _default_provider_index(
    provider_list: list[tuple[str, str]],
    openai_key: Optional[str],
    anthropic_key: Optional[str],
    ollama_available: bool,
) -> int:
    preferred: list[str] = []
    if openai_key:
        preferred.append("openai")
    if anthropic_key:
        preferred.append("anthropic")
    if ollama_available:
        preferred.append("ollama")
    preferred.extend(PROVIDER_ORDER)
    for provider in preferred:
        for idx, (candidate, _) in enumerate(provider_list):
            if candidate == provider:
                return idx
    return 0


def _pick_chain_entry(
    project_dir: str,
    label: str,
    provider_list: list[tuple[str, str]],
    default_provider_idx: int,
    ollama_installed_models: list[str],
) -> ModelChainEntry:
    """Interactively pick one provider + model + retries."""
    print(f"\n--- {label} ---")
    provider = _pick_provider(provider_list, default_provider_idx)

    if provider == "ollama":
        if ollama_installed_models:
            ollama_models = [(m, "installed") for m in ollama_installed_models]
            print(f"\n  Found {len(ollama_installed_models)} installed Ollama model(s):")
            model = _pick_model("ollama", ollama_models, ollama_installed_models[0])
        else:
            if is_ollama_installed():
                print("\n  No Ollama models installed yet. Showing common models:")
            else:
                print("\n  Ollama not available. Showing common models for when you install it:")
            model = _pick_model("ollama", OLLAMA_MODELS, DEFAULT_MODELS["ollama"])
    else:
        models = REMOTE_PROVIDER_MODELS.get(provider, [])
        default_model = DEFAULT_MODELS.get(provider, models[0][0] if models else "")
        model = _pick_model(provider, models, default_model)

    retries = _pick_retries()
    _handle_api_key(project_dir, provider)

    chain_name = f"{provider}:{model}"
    return ModelChainEntry(name=chain_name, max_retries=retries)


def run_init_wizard(project_dir: str, with_extensions: bool = False) -> WizardResult:
    """Run the interactive init wizard."""
    result = WizardResult(with_extensions=with_extensions)

    print("\n=== Lamia Project Setup ===\n")

    # Detect providers
    ollama_available = is_ollama_installed()
    openai_key = detect_api_key("openai")
    anthropic_key = detect_api_key("anthropic")

    if ollama_available and not is_ollama_running():
        print("Starting Ollama service...")
        if start_ollama_service():
            print("  Ollama service started.")
        else:
            print("  Could not start Ollama — it may need to be started manually.")

    ollama_models: list[str] = []
    if ollama_available and is_ollama_running():
        ollama_models = list_ollama_models_sync()

    # Show detection summary
    print("Detected providers:")
    if openai_key:
        print(f"  - openai     ({_primary_env_var_for_provider('openai')} found)")
    else:
        print("  - openai     (no API key)")
    if anthropic_key:
        print(f"  - anthropic  ({_primary_env_var_for_provider('anthropic')} found)")
    else:
        print("  - anthropic  (no API key)")
    if ollama_available:
        status = f"installed, {len(ollama_models)} models" if ollama_models else "installed"
        print(f"  - ollama     ({status})")
    else:
        print("  - ollama     (not installed)")

    # Intro
    print("\nConfigure your default model and optional fallback models.")
    print("The default model handles all requests. Fallbacks are tried if it fails after retries.")
    print("(You can always override the model per-call in Lamia scripts — for advanced usage.)")
    print("(Not sure which models to pick? Terminate this process and run 'lamia eval' to see which model works best for your script/commands.)\n")

    provider_list = _build_provider_list(ollama_available, len(ollama_models), openai_key, anthropic_key)

    default_idx = _default_provider_index(provider_list, openai_key, anthropic_key, ollama_available)

    # Default model (required)
    entry = _pick_chain_entry(project_dir, "Default model", provider_list, default_idx, ollama_models)
    result.model_chain.append(entry)

    # Fallback models
    fallback_num = 1
    while True:
        if fallback_num < MAX_SUGGESTED_CHAIN_LENGTH:
            add = _input_yes_no(f"\n  Add {'a' if fallback_num == 1 else 'another'} fallback model?", default=True)
        else:
            add = _input_yes_no(
                f"\n  Add another fallback? ({fallback_num - 1} fallback(s) is usually sufficient)",
                default=False,
            )
        if not add:
            break
        entry = _pick_chain_entry(
            project_dir, f"Fallback model {fallback_num}", provider_list, default_idx, ollama_models,
        )
        result.model_chain.append(entry)
        fallback_num += 1

    # Summary
    print("\n=== Configuration Summary ===\n")
    for i, e in enumerate(result.model_chain):
        label = "Default:" if i == 0 else f"Fallback {i}:"
        print(f"  {label:12s} {e.name} (retries: {e.max_retries})")
    print()
    return result