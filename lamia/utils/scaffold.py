import os
import yaml

def create_minimal_config(config_path, with_extensions=False, extensions_folder_name="extensions"):
    """Create a minimal config.yaml if it does not exist."""
    if os.path.exists(config_path):
        return False  # Already exists
    config = {}
    if with_extensions:
        config["extensions_folder"] = extensions_folder_name
    with open(config_path, "w") as f:
        yaml.safe_dump(config, f, sort_keys=False)
    return True

def ensure_extensions_folder(root_dir, extensions_folder_name="extensions"):
    """Create the extensions folder with adapters/ and validators/ subfolders."""
    ext_path = os.path.join(root_dir, extensions_folder_name)
    os.makedirs(os.path.join(ext_path, "adapters"), exist_ok=True)
    os.makedirs(os.path.join(ext_path, "validators"), exist_ok=True)
    return ext_path

def update_config_with_extensions(config_path, extensions_folder_name="extensions"):
    """Add or update the extensions_folder key in config.yaml."""
    if not os.path.exists(config_path):
        return False
    with open(config_path, "r") as f:
        config = yaml.safe_load(f) or {}
    config["extensions_folder"] = extensions_folder_name
    with open(config_path, "w") as f:
        yaml.safe_dump(config, f, sort_keys=False)
    return True

def create_env_file(env_path):
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

def create_full_default_config(config_path):
    """Create a full default config.yaml with all settings, overwriting if it exists."""
    config_content = '''# Default model to use (options: openai, openai:gpt-4-32k anthropic, ollama)
default_model: ollama

# Model configurations
models:
  # OpenAI Configuration
  openai:
    enabled: false
    default_model: gpt-3.5-turbo
    models:
      - gpt-4-turbo-preview        # Latest GPT-4, fastest, most capable, cheaper than GPT-4
      - gpt-4-0125-preview         # Similar to turbo but fixed version
      - gpt-4                      # Original GPT-4, high capability
      - gpt-4-32k                  # Original GPT-4 with 32k context
      - gpt-3.5-turbo              # Fast, good value for most tasks
      - gpt-3.5-turbo-16k          # Same as 3.5 but with 16k context
      - gpt-3.5-turbo-0125         # Latest fixed version, most reliable
    temperature: 0.7      # Higher = more creative, Lower = more focused
    max_tokens: 1000     # Maximum length of response
    top_p: 1.0          # Alternative to temperature for sampling
    frequency_penalty: 0.0  # Reduce repetition of token sequences
    presence_penalty: 0.0   # Reduce repetition of topics

  # Anthropic Configuration
  anthropic:
    enabled: false
    default_model: claude-3-opus-20240229
    models:
      - claude-3-opus-20240229     # Most powerful, best for complex tasks
      - claude-3-sonnet-20240229   # Great balance of speed and capability
      - claude-3-haiku-20240307    # Fastest, most cost-effective
      - claude-2.1                 # Previous generation, still capable
      - claude-2.0                 # Older but stable version
    temperature: 0.7     # Higher = more creative, Lower = more focused
    max_tokens: 1000    # Maximum length of response
    top_k: 50          # Limit vocabulary for sampling
    top_p: 1.0         # Alternative to temperature for sampling

  # Ollama Configuration
  ollama:
    enabled: true
    default_model: llama3.2:1b
    models:
      - llama3.2:1b                # Llama 3.2 1B, default model
      - llama2                     # Meta's Llama 2, good all-rounder
      - mixtral                    # Mixture of experts, very capable
      - neural-chat                # Optimized for chat, good performance
      - codellama                  # Optimized for code generation
      - dolphin-phi                # Improved Phi model with chat
      - starling-lm                # High quality small model
      - phi                        # Microsoft's small but capable model
      - gemma                      # Google's efficient model
      - mistral                    # Mistral AI's base model
      - tinyllama                  # Tiny but fast model
    temperature: 0.7       # Higher = more creative, Lower = more focused
    context_size: 4096     # Maximum context size
    num_ctx: 4096         # Context window size
    num_gpu: 1           # Number of GPUs to use
    num_thread: 4        # Number of CPU threads
    repeat_penalty: 1.1  # Penalty for repeated tokens
    top_k: 40           # Top-k sampling
    top_p: 0.9          # Top-p sampling

# Validation settings
validation:
  enabled: true
  max_retries: 1
  #fallback_models: ["anthropic", "openai"]  # Models to try if primary fails
  validators:
    - type: "html"
      strict: false      # HTML validation
    # - type: "json"    # JSON validation
    # - type: "regex"   # Regex validation
    - type: "length"  # Length validation
      min_length: 100
    - type: "html_structure"  # HTML structure validation
      model: HtmlStructure
'''
    with open(config_path, "w") as f:
        f.write(config_content)
    return True 