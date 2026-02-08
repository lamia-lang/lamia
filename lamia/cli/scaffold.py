import os
import yaml
from lamia.cli.init_wizard import WizardResult
    

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


# ── Hardcoded providers section (same for every project) ──────────────

_HARDCODED_PROVIDERS_SECTION = """# Provider configurations
# Advanced parameters (temperature, max_tokens, etc.) use sensible defaults.
# Uncomment and override only if needed.
providers:
  # OpenAI — models ordered cheapest to most expensive (standard input $/MTok)
  openai:
    enabled: false
    default_model: gpt-4.1-nano
    models:
      - gpt-5-nano                  # $0.05 in — fastest GPT-5 variant
      - gpt-4.1-nano               # $0.10 in — fastest, most cost-efficient
      - gpt-4o-mini                 # $0.15 in — fast, affordable small model
      - gpt-5-mini                  # $0.25 in — cost-efficient GPT-5
      - gpt-4.1-mini               # $0.40 in — smaller, faster GPT-4.1
      - o4-mini                     # $1.10 in — fast reasoning model
      - o3-mini                     # $1.10 in — small reasoning model
      - gpt-5                       # $1.25 in — intelligent reasoning model
      - gpt-5.1                     # $1.25 in — improved GPT-5
      - gpt-5.2                     # $1.75 in — best for coding and agentic tasks
      - o3                          # $2.00 in — reasoning model for complex tasks
      - gpt-4.1                     # $2.00 in — smartest non-reasoning model
      - gpt-4o                      # $2.50 in — fast, intelligent, flexible
      - gpt-5.2-codex               # $1.75 in — optimized for agentic coding
      - gpt-5.1-codex               # $1.25 in — optimized for agentic coding
      - gpt-5.3-codex               # latest codex model
      - o1                          # $15.00 in — previous full reasoning model
      - gpt-5.2-pro                 # $21.00 in — smartest, most precise
    # temperature: 0.7
    # max_tokens: 1000

  # Anthropic — models ordered cheapest to most expensive (input $/MTok)
  anthropic:
    enabled: false
    default_model: claude-haiku-4-5-20251001
    models:
      - claude-haiku-3-5-20241022   # $0.80 in — previous fast model
      - claude-haiku-4-5-20251001   # $1.00 in — fastest, near-frontier
      - claude-sonnet-4-5-20250929  # $3.00 in — best speed/intelligence balance
      - claude-opus-4-6             # $5.00 in — most intelligent, best for agents
      - claude-opus-4-5             # $5.00 in — previous top-tier opus
      - claude-opus-4-1             # $15.00 in — legacy opus
    # temperature: 0.7
    # max_tokens: 1000

  # Ollama — local models, no API costs
  ollama:
    enabled: true
    default_model: llama3.2:1b
    models:
      - llama3.2:1b
      - llama2
      - mixtral
      - codellama
      - gemma
      - mistral
      - phi

# Validation settings
validation:
  enabled: true
  max_retries: 1
  validators:
    - type: "html"
      strict: false
    - type: "length"
      min_length: 100
    - type: "html_structure"
      model: HtmlStructure""".lstrip()