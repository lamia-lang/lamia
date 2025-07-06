import asyncio
from typing import List
import os
import subprocess
import requests
import time
import sys
from typing import Optional, Dict, Any
import importlib.util
from lamia.adapters.llm.lamia_adapter import LamiaAdapter

from dotenv import load_dotenv

from lamia.adapters.llm.base import BaseLLMAdapter, LLMResponse
from .config_manager import ConfigManager
from .providers import get_adapter_class, get_env_var_names, get_api_key_from_env, supports_lamia_proxy

class MissingAPIKeysError(Exception):
    """Raised when one or more required API keys are missing for LLM engines."""
    def __init__(self, missing):
        self.missing = missing
        message = (
            "\n❌ The following engines are missing required API keys:\n" +
            "\n".join([f"- {engine}: missing {env_vars}" for engine, env_vars in missing]) +
            "\n\nPlease provide the missing API keys in one of the following ways:\n"
            "- As environment variables (e.g., export OPENAI_API_KEY=...)\n"
            "- In your config file under api_keys (e.g., api_keys: {openai: ...})\n"
            "- As a parameter to the Lamia() constructor (e.g., Lamia(..., api_keys={...}))\n"
            "You can also use LAMIA_API_KEY to proxy remote adapters (openai, anthropic).\n"
            "Alternatively, remove these engines from your default or fallback_models in config."
        )
        super().__init__(message)

def check_api_key(provider_name: str, config_manager: ConfigManager) -> Optional[str]:
    """
    Get and validate API key from config_manager config.
    Returns the API key if found, otherwise raises MissingAPIKeysError.
    Priority: specific provider key > lamia key (for remote providers) > env var fallback (with precedence).
    """
    # First priority: specific provider API key
    api_key = config_manager.get_api_key(provider_name)
    if api_key:
        return api_key

    
    # Third priority: environment variable fallback (with precedence)
    env_api_key = get_api_key_from_env(provider_name)
    if env_api_key:
        return env_api_key
    
    # No API key found - try to get lamia API key (for providers that support proxy)
    if supports_lamia_proxy(provider_name):
        lamia_api_key = config_manager.get_api_key('lamia')
        if lamia_api_key:
            return lamia_api_key

    # No API key found - only raise error if this provider needs one
    env_var_names = get_env_var_names(provider_name)
    if env_var_names:
        env_vars_str = " or ".join(env_var_names)
        raise MissingAPIKeysError([(provider_name, env_vars_str)])
    
    # Provider doesn't need an API key (e.g., local models)
    return None

def check_all_required_api_keys(config_manager: ConfigManager):
    """
    Check that all required API keys for default and fallback engines are present.
    If any are missing, raise MissingAPIKeysError.
    """
    config = config_manager.get_config()
    default_model = config.get('default_model')
    fallback_models = config.get('validation', {}).get('fallback_models', [])
    required_engines = set([default_model] + fallback_models)
    
    missing = []
    for engine in required_engines:
        try:
            check_api_key(engine, config_manager)
        except MissingAPIKeysError as e:
            missing.extend(e.missing)
    
    if missing:
        raise MissingAPIKeysError(missing)

def create_adapter_from_config(config_manager: ConfigManager, override_model: str = None) -> BaseLLMAdapter:
    """Create an adapter instance based on the active configuration."""
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

    # Check if we should use Lamia adapter as fallback
    use_lamia_adapter = False
    api_key = None
    
    # Check API key availability and determine adapter to use
    own_api_key = config_manager.get_api_key(provider_name) or get_api_key_from_env(provider_name)
    lamia_api_key = config_manager.get_api_key('lamia') or get_api_key_from_env(provider_name)
    
    if own_api_key:
        # Use original adapter with specific API key
        api_key = own_api_key
        use_lamia_adapter = False
    elif supports_lamia_proxy(provider_name) and lamia_api_key and not env_api_key:
        # Use Lamia adapter when:
        # 1. Provider supports lamia proxy
        # 2. Lamia API key is available
        # 3. No env var API key for the specific provider
        use_lamia_adapter = True
        api_key = lamia_api_key
    else:
        raise MissingAPIKeysError([(provider_name, "API key")])

    # Get the adapter class
    ext_folder = config_manager.get_extensions_folder()
    ext_adapters_path = os.path.join(os.getcwd(), ext_folder, "adapters")
    
    if use_lamia_adapter:
        adapter_class = LamiaAdapter(api_key=api_key)
        # For Lamia adapter, we need to prefix the model name based on provider
        if provider_name == 'openai':
            model_name = f"gpt-{model_name}" if not model_name.startswith('gpt-') else model_name
        elif provider_name == 'anthropic':
            model_name = f"anthropic-{model_name}" if not model_name.startswith('anthropic-') else model_name
    else:
        adapter_class = get_adapter_class(provider_name, [ext_adapters_path])

    # Extract has_context_memory from config if present
    has_context_memory = config_manager.get_has_context_memory(provider_name, model_name)

    # Create adapter instance based on its requirements
    init_kwargs = {}
    
    # Add API key if needed
    env_var_names = get_env_var_names('lamia' if use_lamia_adapter else provider_name)
    if env_var_names:  # Provider needs an API key
        init_kwargs['api_key'] = api_key
    
    # Add model name
    init_kwargs['model'] = model_name
    
    # Add provider-specific parameters
    if provider_name == "ollama" and not use_lamia_adapter:
        init_kwargs['has_context_memory'] = has_context_memory
        # Add any other ollama-specific config from provider_config
        for key in ['base_url', 'temperature', 'max_tokens', 'context_size', 'num_ctx', 'num_gpu', 'num_thread', 'repeat_penalty', 'top_k', 'top_p']:
            if key in provider_config:
                init_kwargs[key] = provider_config[key]
    elif use_lamia_adapter:
        # Add Lamia-specific parameters
        lamia_config = config_manager.get_config().get('lamia', {})
        init_kwargs['api_url'] = lamia_config.get('api_url', 'http://localhost:8080')
    
    return adapter_class(**init_kwargs)

# Legacy function for backward compatibility
def _discover_adapters_in_path(path: str) -> dict:
    """Legacy function - use providers module instead."""
    from .providers import get_all_providers, get_adapter_class
    result = {}
    for provider_name in get_all_providers([path] if os.path.isdir(path) else None):
        try:
            adapter_cls = get_adapter_class(provider_name, [path] if os.path.isdir(path) else None)
            result[adapter_cls.__name__] = adapter_cls
        except ValueError:
            continue
    return result