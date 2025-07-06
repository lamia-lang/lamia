import asyncio
from typing import List
import os
import subprocess
import requests
import time
import sys
from typing import Optional, Dict, Any
import importlib.util

from dotenv import load_dotenv

from lamia.adapters.llm.openai_adapter import OpenAIAdapter
from lamia.adapters.llm.anthropic_adapter import AnthropicAdapter
from lamia.adapters.llm.local import OllamaAdapter
from lamia.adapters.llm.base import BaseLLMAdapter, LLMResponse
from .config_manager import ConfigManager

class MissingAPIKeysError(Exception):
    """Raised when one or more required API keys are missing for LLM engines."""
    def __init__(self, missing):
        self.missing = missing
        message = (
            "\n❌ The following engines are missing required API keys:\n" +
            "\n".join([f"- {engine}: missing {env_var}" for engine, env_var in missing]) +
            "\n\nPlease provide the missing API keys in one of the following ways:\n"
            "- As environment variables (e.g., export OPENAI_API_KEY=...)\n"
            "- In your config file under api_keys (e.g., api_keys: {openai: ...})\n"
            "- As a parameter to the Lamia() constructor (e.g., Lamia(..., api_keys={...}))\n"
            "You can also use LAMIA_API_KEY to proxy remote adapters (openai, anthropic).\n"
            "Alternatively, remove these engines from your default or fallback_models in config."
        )
        super().__init__(message)

def check_api_key(model_type: str, config_manager: ConfigManager) -> Optional[str]:
    """
    Get and validate API key from config_manager config.
    Returns the API key if found, otherwise raises MissingAPIKeysError.
    Priority: specific provider key > lamia key (for remote providers) > env var fallback.
    """
    env_vars = {
        'openai': 'OPENAI_API_KEY',
        'anthropic': 'ANTHROPIC_API_KEY',
        'lamia': 'LAMIA_API_KEY'
    }
    
    # First priority: specific provider API key
    api_key = config_manager.get_api_key(model_type)
    if api_key:
        return api_key
    
    # Second priority: lamia API key (for remote providers only)
    if model_type in ('openai', 'anthropic'):
        lamia_api_key = config_manager.get_api_key('lamia')
        if lamia_api_key:
            return lamia_api_key
    
    # Third priority: environment variable fallback for backward compatibility
    env_var = env_vars.get(model_type)
    if env_var:
        env_api_key = os.getenv(env_var)
        if env_api_key:
            return env_api_key
    
    # No API key found
    raise MissingAPIKeysError([(model_type, env_vars.get(model_type, 'API_KEY'))])

def check_all_required_api_keys(config_manager: ConfigManager):
    """
    Check that all required API keys for default and fallback engines are present.
    If any are missing, raise MissingAPIKeysError.
    Reuses check_api_key for consistent logic and priority handling.
    """
    config = config_manager.get_config()
    default_model = config.get('default_model')
    fallback_models = config.get('validation', {}).get('fallback_models', [])
    required_engines = set([default_model] + fallback_models)
    
    missing = []
    for engine in required_engines:
        if ConfigManager.is_remote_provider(engine):
            try:
                check_api_key(engine, config_manager)
            except MissingAPIKeysError as e:
                # Extract the missing key info from the exception
                missing.extend(e.missing)
    
    if missing:
        raise MissingAPIKeysError(missing)

def is_ollama_running() -> bool:
    """Check if Ollama service is running by trying to connect to its API."""
    try:
        response = requests.get("http://localhost:11434/api/version", timeout=2)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def list_available_ollama_models() -> list[str]:
    """
    Get list of available local Ollama models.
    Returns empty list if service is not running or no models found.
    """
    if not is_ollama_running():
        print("⚠️  Ollama service is not running. Start it with 'ollama serve'")
        return []
        
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            return [model['name'] for model in models]
        return []
    except requests.exceptions.RequestException:
        return []

def start_ollama_service() -> bool:
    """
    Start the Ollama service if it's not running.
    
    Returns:
        bool: True if service started successfully or was already running
    """
    if is_ollama_running():
        print("✓ Ollama service is running")
        return True

    print("Starting Ollama service...")
    try:
        # Start Ollama in the background
        subprocess.Popen(["ollama", "serve"], 
                       stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
        
        # Wait for service to start (max 30 seconds)
        for i in range(30):
            if is_ollama_running():
                print("✓ Ollama service started successfully")
                return True
            if i % 5 == 0:  # Show progress every 5 seconds
                print(".", end="", flush=True)
            time.sleep(1)
        
        print("\n❌ Timeout waiting for Ollama service to start")
        return False
    except FileNotFoundError:
        print("\n❌ Ollama is not installed. Please install it first: https://ollama.ai/download")
        raise RuntimeError("Ollama is not installed")
    except Exception as e:
        print(f"\n❌ Failed to start Ollama service: {str(e)}")
        return False

def ensure_ollama_model_pulled(model_name: str) -> bool:
    """
    Ensure the specified Ollama model is pulled and available.
    
    Args:
        model_name: Name of the Ollama model to check/pull
        
    Returns:
        bool: True if model is available
    """
    try:
        # Check if model exists
        response = requests.get(f"http://localhost:11434/api/show", 
                              json={"name": model_name})
        
        if response.status_code == 200:
            return True
            
        # If model doesn't exist, pull it
        pull_response = requests.post(f"http://localhost:11434/api/pull", 
                                    json={"name": model_name})
        
        return pull_response.status_code == 200
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to check/pull Ollama model: {str(e)}")

def _discover_adapters_in_path(path: str) -> dict:
    """Discover all adapter classes in a given filesystem path."""
    import inspect
    from lamia.adapters.llm.base import BaseLLMAdapter
    adapter_class_map = {}
    if not os.path.isdir(path):
        return adapter_class_map
    sys.path.insert(0, path)
    for file in os.listdir(path):
        if file.endswith(".py") and not file.startswith("__"):
            module_name = file[:-3]
            try:
                spec = importlib.util.spec_from_file_location(module_name, os.path.join(path, file))
                if not spec or not spec.loader:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                for _, cls in inspect.getmembers(module, inspect.isclass):
                    if (
                        issubclass(cls, BaseLLMAdapter)
                        and cls is not BaseLLMAdapter
                        and hasattr(cls, '__name__')
                    ):
                        adapter_class_map[cls.__name__] = cls
            except Exception as e:
                print(f"Warning: Could not import adapter from {file}: {e}")
    sys.path.pop(0)
    return adapter_class_map

def create_adapter_from_config(config_manager: ConfigManager, override_model: str = None) -> BaseLLMAdapter:
    """Create an adapter instance based on the active configuration. Local engines are not started here."""
    check_all_required_api_keys(config_manager)
    provider_name = override_model or config_manager.get_default_model()
    provider_config = config_manager.get_model_config(provider_name)

    # Determine the model name
    model_name = provider_config.get('default_model')
    if not model_name:
        available_models = provider_config.get('models', [])
        print(f"\nAvailable {provider_name.capitalize()} models:")
        for m in available_models:
            if isinstance(m, str):
                model_name = m
            elif isinstance(m, dict):
                model_name = m.get('name')

    # Extract has_context_memory from config if present
    has_context_memory = config_manager.get_has_context_memory(provider_name, model_name)

    # Discover extension adapters
    ext_folder = config_manager.get_extensions_folder()
    ext_adapters_path = os.path.join(os.getcwd(), ext_folder, "adapters")
    ext_adapter_class_map = _discover_adapters_in_path(ext_adapters_path)
    # Built-in mapping
    builtin_adapters = {
        "openai": OpenAIAdapter,
        "anthropic": AnthropicAdapter,
        "ollama": OllamaAdapter,
    }
    # Check for name conflicts
    conflict_names = set(builtin_adapters.keys()) & set(ext_adapter_class_map.keys())
    if conflict_names:
        raise RuntimeError(f"User-defined adapter name(s) conflict with built-in adapters: {', '.join(conflict_names)}")
    # Merge
    all_adapters = {**builtin_adapters, **ext_adapter_class_map}
    # Use the adapter by provider_name
    if provider_name in all_adapters:
        AdapterClass = all_adapters[provider_name]
        # Pass config as needed (assume same signature as built-ins)
        if provider_name == "openai":
            return AdapterClass(
                api_key=check_api_key('openai', config_manager),
                model=model_name,
            )
        elif provider_name == "anthropic":
            return AdapterClass(
                api_key=check_api_key('anthropic', config_manager),
                model=model_name,
            )
        elif provider_name == "ollama":
            return AdapterClass(
                model=model_name,
                has_context_memory=has_context_memory
            )
        else:
            # For extension adapters, try to instantiate with api_key and model_name
            # Inspect the adapter __init__ signature and pass only the supported params
            import inspect  # local import to avoid global overhead if not needed
            init_sig = inspect.signature(AdapterClass.__init__)
            init_kwargs = {}
            if 'api_key' in init_sig.parameters:
                init_kwargs['api_key'] = check_api_key(provider_name, config_manager)
            if 'model' in init_sig.parameters:
                init_kwargs['model'] = model_name
            return AdapterClass(**init_kwargs)
    else:
        raise ValueError(f"Unsupported model type: {provider_name}")