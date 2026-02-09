import os
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from lamia.cli.init_wizard import WizardResult


OPENAI_MODELS: list[tuple[str, str]] = [
    ("gpt-5-nano", "fastest GPT-5 variant"),
    ("gpt-4.1-nano", "fastest, most cost-efficient"),
    ("gpt-4o-mini", "fast, affordable small model"),
    ("gpt-5-mini", "cost-efficient GPT-5"),
    ("gpt-4.1-mini", "smaller, faster GPT-4.1"),
    ("o4-mini", "fast reasoning model"),
    ("o3-mini", "small reasoning model"),
    ("gpt-5", "intelligent reasoning model"),
    ("gpt-5.1", "improved GPT-5"),
    ("gpt-5.2", "best for coding and agentic tasks"),
    ("o3", "reasoning model for complex tasks"),
    ("gpt-4.1", "smartest non-reasoning model"),
    ("gpt-4o", "fast, intelligent, flexible"),
    ("gpt-5.2-codex", "optimized for agentic coding"),
    ("gpt-5.1-codex", "optimized for agentic coding"),
    ("gpt-5.3-codex", "latest codex model"),
    ("o1", "previous full reasoning model"),
    ("gpt-5.2-pro", "smartest, most precise"),
]

ANTHROPIC_MODELS: list[tuple[str, str]] = [
    ("claude-haiku-3-5-20241022", "previous fast model"),
    ("claude-haiku-4-5-20251001", "fastest, near-frontier"),
    ("claude-sonnet-4-5-20250929", "best speed/intelligence balance"),
    ("claude-opus-4-6", "most intelligent, best for agents"),
    ("claude-opus-4-5", "previous top-tier opus"),
    ("claude-opus-4-1", "legacy opus"),
]

OLLAMA_MODELS: list[tuple[str, str]] = [
    ("llama3.2:1b", "Small and fast (1B params)"),
    ("llama2", "Good all-rounder"),
    ("mixtral", "Mixture of experts, very capable — will be slow on most hardware"),
    ("codellama", "Optimized for code"),
    ("gemma", "Google's efficient model"),
    ("mistral", "Mistral AI base model"),
    ("phi", "Microsoft's small but capable model"),
]

DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4.1-nano",
    "anthropic": "claude-haiku-4-5-20251001",
    "ollama": "llama3.2:1b",
}

REMOTE_PROVIDER_MODELS: dict[str, list[tuple[str, str]]] = {
    "openai": OPENAI_MODELS,
    "anthropic": ANTHROPIC_MODELS,
}

PROVIDER_ORDER: tuple[str, ...] = tuple(DEFAULT_MODELS.keys())


def create_minimal_config(config_path: str, with_extensions: bool = False, extensions_folder_name: str = "extensions") -> bool:
    """Create a minimal config.yaml if it does not exist."""
    if os.path.exists(config_path):
        return False  # Already exists
    config: dict = {
        "model_chain": [
            {"name": "ollama", "max_retries": 3},
        ],
        "providers": {
            "ollama": {
                "enabled": True,
                "default_model": "llama3.2:1b",
            },
        },
    }
    if with_extensions:
        config["extensions_folder"] = extensions_folder_name
    with open(config_path, "w") as f:
        yaml.safe_dump(config, f, sort_keys=False)
    return True

def ensure_extensions_folder(root_dir: str, extensions_folder_name: str = "extensions") -> str:
    """Create the extensions folder with adapters/ and validators/ subfolders."""
    ext_path = os.path.join(root_dir, extensions_folder_name)
    os.makedirs(os.path.join(ext_path, "adapters"), exist_ok=True)
    os.makedirs(os.path.join(ext_path, "validators"), exist_ok=True)
    return ext_path

def update_config_with_extensions(config_path: str, extensions_folder_name: str = "extensions") -> bool:
    """Add or update the extensions_folder key in config.yaml."""
    if not os.path.exists(config_path):
        return False
    with open(config_path, "r") as f:
        config = yaml.safe_load(f) or {}
    config["extensions_folder"] = extensions_folder_name
    with open(config_path, "w") as f:
        yaml.safe_dump(config, f, sort_keys=False)
    return True

def create_env_file(env_path: str) -> bool:
    """Create a .env file with dummy API keys if it does not exist, and add a comment hinting the user to change them."""
    if os.path.exists(env_path):
        return False  # Already exists
    env_content = (
        "# TODO: Replace the API keys below with your own keys before running the app!\n"
        "OPENAI_API_KEY=sk-your-openai-key-here\n"
        "ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here\n"
        "LAMIA_API_KEY=sk-your-openai-key-here\n"
    )
    with open(env_path, "w") as f:
        f.write(env_content)
    return True

def create_config_from_wizard_result(config_path: str, wizard_result: "WizardResult") -> bool:
    """Create config.yaml from an interactive wizard result.
    
    The model_chain comes from user selections. The providers section is
    always the same hardcoded block so users can easily activate any
    provider later without becoming config experts.
    """
    # Build model_chain YAML lines
    chain_lines = ["model_chain:"]
    for entry in wizard_result.model_chain:
        chain_lines.append(f'  - name: "{entry.name}"')
        chain_lines.append(f"    max_retries: {entry.max_retries}")
    chain_yaml = "\n".join(chain_lines)

    config_content = f"""# Lamia project configuration
# Model chain: models are tried in order; if one fails, the next is used.
# Use "provider:model" syntax or just "provider" to use its default_model.
{chain_yaml}
{_HARDCODED_PROVIDERS_SECTION}
"""
    with open(config_path, "w") as f:
        f.write(config_content)
    return True


def _render_models(models: list[tuple[str, str]]) -> str:
    return "\n".join(f"      - {name:<28} # {description}" for name, description in models)


_HARDCODED_PROVIDERS_SECTION = f"""# Provider configurations
# Advanced parameters (temperature, max_tokens, etc.) use sensible defaults.
# Uncomment and override only if needed.
providers:
  # OpenAI — models ordered by capability
  openai:
    enabled: false
    default_model: {DEFAULT_MODELS["openai"]}
    models:
{_render_models(OPENAI_MODELS)}

  # Anthropic — models ordered by capability
  anthropic:
    enabled: false
    default_model: {DEFAULT_MODELS["anthropic"]}
    models:
{_render_models(ANTHROPIC_MODELS)}

  # Ollama — local models, no API costs
  ollama:
    enabled: true
    default_model: {DEFAULT_MODELS["ollama"]}
    models:
{_render_models(OLLAMA_MODELS)}

""".lstrip()