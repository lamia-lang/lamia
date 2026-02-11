"""Interactive init wizard for ``lamia init``."""

import asyncio
import logging
from dataclasses import dataclass, field

from lamia.adapters.llm.local.ollama_adapter import OllamaAdapter
from lamia.cli.api_key_utils import detect_api_key, handle_api_key
from lamia.cli.prompts import input_number, input_yes_no, pick_from_list
from lamia.cli.scaffold import (
    DEFAULT_MODELS,
    OLLAMA_SUGGESTED_MODELS,
    REMOTE_PROVIDER_MODELS,
)

logger = logging.getLogger(__name__)

_MAX_SUGGESTED_CHAIN_LENGTH = 3


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
        key, env_var, source = detect_api_key(provider, project_dir)
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
            add = input_yes_no(f"\n  Add {'a' if fallback_num == 1 else 'another'} fallback model?", default=True)
        else:
            add = input_yes_no(f"\n  Add another fallback? ({fallback_num - 1} fallback(s) is usually sufficient)", default=False)
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


def _pick_chain_entry(
    project_dir: str,
    label: str,
    provider_list: list[tuple[str, str]],
    default_provider_idx: int,
    ollama_models: list[str],
) -> ModelChainEntry:
    """Interactively pick one provider + model + retries."""
    print(f"\n--- {label} ---")
    provider = pick_from_list("Provider", provider_list, default_provider_idx)

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
    model = pick_from_list("Model", models, default_model_idx)

    retries = input_number("  Max retries [default: 2]: ", max_val=10, default=2)
    handle_api_key(project_dir, provider)
    return ModelChainEntry(name=f"{provider}:{model}", max_retries=retries)