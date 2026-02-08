"""Interactive init wizard for `lamia init`.

Guides users through provider selection, API key setup, and model chain
configuration to produce a working config.yaml on first run.
"""

import logging
import os
import shutil
import stat
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional

import requests

from lamia.env_loader import get_global_lamia_dir, get_global_env_path

logger = logging.getLogger(__name__)

# ── Provider / model metadata (cheapest → most capable) ─────────────────

OPENAI_MODELS = [
    ("gpt-5-nano", "fastest GPT-5 variant"),
    ("gpt-4.1-nano", "fastest, most cost-efficient"),
    ("gpt-4o-mini", "fast, affordable small model"),
    ("gpt-5-mini", "cost-efficient GPT-5"),
    ("gpt-4.1-mini", "smaller, faster GPT-4.1"),
    ("o4-mini", "fast reasoning model"),
    ("gpt-5", "intelligent reasoning model"),
    ("gpt-5.1", "improved GPT-5"),
    ("gpt-5.2", "best for coding and agentic tasks"),
    ("gpt-4.1", "smartest non-reasoning model"),
    ("gpt-4o", "fast, intelligent, flexible"),
    ("gpt-5.2-pro", "smartest, most precise"),
]

ANTHROPIC_MODELS = [
    ("claude-haiku-3-5-20241022", "previous fast model"),
    ("claude-haiku-4-5-20251001", "fastest, near-frontier"),
    ("claude-sonnet-4-5-20250929", "best speed/intelligence balance"),
    ("claude-opus-4-6", "most intelligent, best for agents"),
    ("claude-opus-4-5", "previous top-tier opus"),
    ("claude-opus-4-1", "legacy opus"),
]

OLLAMA_FALLBACK_MODELS = [
    ("llama3.2:1b", "Small and fast (1B params)"),
    ("llama2", "Good all-rounder"),
    ("mistral", "Mistral AI base model"),
    ("codellama", "Optimized for code"),
    ("gemma", "Google's efficient model"),
    ("mixtral", "Mixture of experts, very capable — will be slow on most hardware"),
    ("phi", "Microsoft's small but capable model"),
]

DEFAULT_MODELS = {
    "openai": "gpt-4.1-nano",
    "anthropic": "claude-haiku-4-5-20251001",
    "ollama": "llama3.2:1b",
}

MAX_SUGGESTED_CHAIN_LENGTH = 3


# ── Helpers ──────────────────────────────────────────────────────────────

def _env_var_for_provider(provider: str) -> str:
    """Derive the env-var name from a provider name.

    Follows the same ``{PROVIDER.upper()}_API_KEY`` convention used by
    ``BaseLLMAdapter.env_var_names()`` so there is no duplicated mapping.
    """
    return f"{provider.upper()}_API_KEY"


# ── Data classes ─────────────────────────────────────────────────────────

@dataclass
class ModelChainEntry:
    """A single entry in the model chain — only user-facing fields."""
    name: str        # e.g. "anthropic:claude-haiku-4-5-20251001" or "ollama"
    max_retries: int  # e.g. 3


@dataclass
class WizardResult:
    """Output of the init wizard, consumed by scaffold functions."""
    model_chain: list[ModelChainEntry] = field(default_factory=list)
    with_extensions: bool = False


# ── Detection helpers ────────────────────────────────────────────────────

def is_ollama_installed() -> bool:
    """Check if the ollama binary is on PATH."""
    return shutil.which("ollama") is not None


def is_ollama_running(base_url: str = "http://localhost:11434") -> bool:
    """Check if the Ollama service is currently responding."""
    try:
        response = requests.get(f"{base_url}/api/version", timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False


def start_ollama_service(base_url: str = "http://localhost:11434") -> bool:
    """Attempt to start the ollama serve process. Returns True if running after attempt."""
    if is_ollama_running(base_url):
        return True
    if not is_ollama_installed():
        return False
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(10):  # Wait up to 10 seconds
            if is_ollama_running(base_url):
                return True
            time.sleep(1)
    except Exception:
        pass
    return False


def list_ollama_models(base_url: str = "http://localhost:11434") -> list[str]:
    """Query running Ollama for installed models. Returns empty list on failure."""
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=3)
        if response.status_code == 200:
            return [m["name"] for m in response.json().get("models", [])]
    except requests.RequestException:
        pass
    return []


def detect_api_key(provider: str) -> Optional[str]:
    """Check if an API key for the given provider is available in the environment."""
    env_var = _env_var_for_provider(provider)
    value = os.getenv(env_var)
    if value and not value.startswith("sk-your-"):
        return value
    return None


# ── Global key storage ───────────────────────────────────────────────────

def save_global_key(provider: str, api_key: str) -> None:
    """Append or update an API key in ~/.lamia/.env with secure permissions.

    Security: The file is created with 0600 permissions (owner read/write only).
    API keys are stored in plain text, following the same convention as
    ~/.aws/credentials and ~/.docker/config.json.
    """
    global_dir = get_global_lamia_dir()
    global_env = get_global_env_path()
    env_var = _env_var_for_provider(provider)

    # Create directory if needed
    global_dir.mkdir(parents=True, exist_ok=True)

    # Read existing content
    existing_lines: list[str] = []
    if global_env.exists():
        existing_lines = global_env.read_text().splitlines()

    # Update or append the key
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

    # Set secure file permissions (0600 = owner read/write only)
    # On Windows this is a no-op effectively, but won't error
    try:
        global_env.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        logger.warning("Could not set secure permissions on %s — please set manually to 600", global_env)

    # Also set in current process environment so it's immediately available
    os.environ[env_var] = api_key


# ── Interactive prompts ──────────────────────────────────────────────────

def _input_choice(prompt: str, options: list[str], default: Optional[str] = None) -> str:
    """Prompt user to pick one option by number."""
    for i, opt in enumerate(options, 1):
        marker = " (default)" if opt == default else ""
        print(f"  {i}. {opt}{marker}")
    while True:
        raw = input(prompt).strip()
        if not raw and default:
            return default
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except ValueError:
            # Allow typing the option name directly
            if raw in options:
                return raw
        print(f"  Please enter a number between 1 and {len(options)}.")


def _input_yes_no(prompt: str, default: bool = True) -> bool:
    """Prompt user for yes/no."""
    suffix = " [Y/n]: " if default else " [y/N]: "
    raw = input(prompt + suffix).strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def _input_model(provider: str, models: list[tuple[str, str]], default_model: str) -> str:
    """Let user pick a model from a list (shown cheapest to most capable)."""
    print(f"\n  Available {provider} models (cheapest to most capable):")
    for i, (name, desc) in enumerate(models, 1):
        marker = " <-- default" if name == default_model else ""
        print(f"    {i}. {name}  — {desc}{marker}")
    while True:
        raw = input(f"  Select model [default: {default_model}]: ").strip()
        if not raw:
            return default_model
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(models):
                return models[idx][0]
        except ValueError:
            # Allow typing model name directly
            model_names = [m[0] for m in models]
            if raw in model_names:
                return raw
        print(f"  Please enter a number between 1 and {len(models)} or a model name.")


def _save_local_key(project_dir: str, provider: str, api_key: str) -> None:
    """Save an API key to the project-local .env file with secure permissions."""
    env_path = os.path.join(project_dir, ".env")
    env_var = _env_var_for_provider(provider)

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


def _ask_for_api_key(provider: str) -> tuple[str, bool]:
    """Ask user for an API key and whether to store it globally.

    Returns:
        (api_key, store_globally) tuple
    """
    env_var = _env_var_for_provider(provider)
    print(f"\n  No {env_var} found in your environment.")
    api_key = input(f"  Enter your {provider} API key (or press Enter to skip {provider}): ").strip()
    if not api_key:
        return "", False
    
    store_globally = _input_yes_no(
        f"  Store this key globally in ~/.lamia/.env for all Lamia projects?\n"
        f"  (It will be available even for already existing projects)"
    )
    return api_key, store_globally


def _ask_retries() -> int:
    """Ask user for max retries with a sensible default."""
    raw = input("  Max retries [default: 2]: ").strip()
    if not raw:
        return 2
    try:
        val = int(raw)
        return max(1, min(val, 10))
    except ValueError:
        return 2


# ── Main wizard ──────────────────────────────────────────────────────────

def run_init_wizard(project_dir: str, with_extensions: bool = False) -> WizardResult:
    """Run the interactive init wizard. Returns a WizardResult.

    Args:
        project_dir: Absolute path to the project directory (for saving local .env).
        with_extensions: Whether to scaffold the extensions folder.
    """
    result = WizardResult(with_extensions=with_extensions)

    print("\n=== Lamia Project Setup ===\n")

    # ── Step 1: Detect available providers ────────────────────────────
    ollama_available = is_ollama_installed()
    openai_key = detect_api_key("openai")
    anthropic_key = detect_api_key("anthropic")

    if ollama_available:
        # Try to start ollama if installed but not running
        if not is_ollama_running():
            print("Starting Ollama service...")
            if start_ollama_service():
                print("  Ollama service started.")
            else:
                print("  Could not start Ollama service — it may need to be started manually.")

    # Show detection results
    print("Detected providers:")
    if anthropic_key:
        print(f"  - anthropic  ({_env_var_for_provider('anthropic')} found)")
    else:
        print("  - anthropic  (no API key)")
    if openai_key:
        print(f"  - openai     ({_env_var_for_provider('openai')} found)")
    else:
        print("  - openai     (no API key)")
    if ollama_available:
        running = is_ollama_running()
        status = "installed, running" if running else "installed, not running"
        print(f"  - ollama     ({status})")
    else:
        print("  - ollama     (not installed)")

    # ── Step 2: Provider selection ────────────────────────────────────
    print("\nSelect providers for your model chain.")
    print("Models in the chain are tried in order; if one fails, the next is used.\n")

    selected_providers: list[str] = []

    # Ask about each provider
    for provider in ["anthropic", "openai", "ollama"]:
        if provider == "ollama":
            if not ollama_available:
                want = _input_yes_no(f"  Add {provider} to model chain? (not installed — will be skipped until installed)", default=False)
                if want:
                    selected_providers.append(provider)
                    print("  Warning: Ollama added to model chain but will be skipped until installed.")
                    print("  Install from https://ollama.ai/download")
                continue
            want = _input_yes_no(f"  Add {provider} to model chain?", default=True)
        else:
            has_key = detect_api_key(provider) is not None
            default = has_key  # Pre-select if key available
            want = _input_yes_no(f"  Add {provider} to model chain?", default=default)

        if want:
            selected_providers.append(provider)

    if not selected_providers:
        print("\n  No providers selected. At least one provider is needed.")
        print("  Adding ollama as default (free, local).\n")
        selected_providers.append("ollama")
        if not ollama_available:
            print("  Warning: Ollama added to model chain but will be skipped until installed.")
            print("  Install from https://ollama.ai/download")

    # ── Step 3: API keys for cloud providers ──────────────────────────
    for provider in selected_providers:
        if provider == "ollama":
            continue
        existing_key = detect_api_key(provider)
        if existing_key:
            print(f"\n  {provider}: API key already configured.")
            continue
        api_key, store_globally = _ask_for_api_key(provider)
        if not api_key:
            env_var = _env_var_for_provider(provider)
            print(f"  Skipping {provider} — no API key provided. It will fail at runtime without a key.")
            print(f"  Set {env_var} before running.")
            continue
        if store_globally:
            save_global_key(provider, api_key)
            print(f"  Saved {provider} key to ~/.lamia/.env (available for all projects).")
        else:
            _save_local_key(project_dir, provider, api_key)
            print(f"  Saved {provider} key to project .env file.")

    # ── Step 4: Model selection per provider ──────────────────────────
    print("\nSelect a model for each provider in your chain.")
    print("(Shown from cheapest to most capable)\n")

    for provider in selected_providers:
        if provider == "openai":
            model = _input_model("openai", OPENAI_MODELS, DEFAULT_MODELS["openai"])
            chain_name = f"openai:{model}"
        elif provider == "anthropic":
            model = _input_model("anthropic", ANTHROPIC_MODELS, DEFAULT_MODELS["anthropic"])
            chain_name = f"anthropic:{model}"
        elif provider == "ollama":
            # Try to list installed models
            installed = []
            if ollama_available and is_ollama_running():
                installed = list_ollama_models()

            if installed:
                ollama_models = [(m, "installed") for m in installed]
                print(f"\n  Found {len(installed)} installed Ollama model(s):")
                model = _input_model("ollama", ollama_models, installed[0])
            else:
                if ollama_available:
                    print("\n  No Ollama models installed yet. Showing common models:")
                    print("  (Larger models will be slow on most hardware)")
                else:
                    print("\n  Ollama not available. Showing common models for when you install it:")
                model = _input_model("ollama", OLLAMA_FALLBACK_MODELS, DEFAULT_MODELS["ollama"])
            chain_name = f"ollama:{model}"
        else:
            continue

        retries = _ask_retries()
        result.model_chain.append(ModelChainEntry(name=chain_name, max_retries=retries))

        # Suggest stopping after MAX_SUGGESTED_CHAIN_LENGTH models
        if len(result.model_chain) >= MAX_SUGGESTED_CHAIN_LENGTH and provider != selected_providers[-1]:
            remaining = selected_providers[selected_providers.index(provider) + 1:]
            if remaining:
                keep_going = _input_yes_no(
                    f"\n  You have {len(result.model_chain)} models in the chain "
                    f"(usually sufficient). Continue adding {', '.join(remaining)}?",
                    default=False,
                )
                if not keep_going:
                    break

    # ── Step 5: Print summary ─────────────────────────────────────────
    print("\n=== Configuration Summary ===\n")
    print("Model chain:")
    for entry in result.model_chain:
        print(f"  - {entry.name} (max_retries: {entry.max_retries})")

    print()
    return result