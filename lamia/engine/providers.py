"""Fast provider registry with pre-built maps for instant access."""

from typing import Dict, Type, Set, Optional
import importlib
import importlib.util
import inspect
import os
from pathlib import Path

from ..adapters.llm.base import BaseLLMAdapter
from ..adapters.llm.openai_adapter import OpenAIAdapter
from ..adapters.llm.anthropic_adapter import AnthropicAdapter
from ..adapters.llm.local.ollama_adapter import OllamaAdapter


class ProviderRegistry:
    """Fast provider registry with pre-built maps."""
    
    def __init__(self):
        # Built-in adapters, we preload them because currently we don't have many of them. Also, we want to allow users call some runs with the models not in the initial config.
        self._builtin_adapters = [
            OpenAIAdapter,
            AnthropicAdapter,
            OllamaAdapter,
        ]
        
        # Pre-built maps for fast access
        self._adapter_map: Dict[str, Type[BaseLLMAdapter]] = {}
        self._remote_providers: Set[str] = set()
        self._lamia_proxy_providers: Set[str] = set()
        
        # Build maps once
        self._build_maps()
    
    def _build_maps(self):
        """Build all maps once for fast access."""
        # Add built-in adapters
        for adapter_cls in self._builtin_adapters:
            name = adapter_cls.name()
            self._adapter_map[name] = adapter_cls
            
            # Build remote providers set
            if adapter_cls.is_remote():
                self._remote_providers.add(name)
        
        # External business logic: which providers support lamia proxy
        self._lamia_proxy_providers = {"openai", "anthropic"}
    
    def add_user_adapters(self, search_paths: list[str]):
        """Add user-defined adapters from search paths."""
        for path in search_paths:
            if not os.path.isdir(path):
                continue
                
            for file_path in Path(path).rglob("*.py"):
                if file_path.name.startswith("_"):
                    continue
                    
                try:
                    spec = importlib.util.spec_from_file_location(
                        f"user_adapter_{file_path.stem}", 
                        file_path
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        
                        for name, obj in inspect.getmembers(module, inspect.isclass):
                            if (issubclass(obj, BaseLLMAdapter) and 
                                obj != BaseLLMAdapter and
                                hasattr(obj, 'name')):
                                try:
                                    adapter_name = obj.name()
                                    
                                    # Check for conflicts
                                    if adapter_name in self._adapter_map:
                                        raise RuntimeError(
                                            f"User adapter '{adapter_name}' conflicts with existing adapter"
                                        )
                                    
                                    self._adapter_map[adapter_name] = obj
                                    
                                    # Add to remote providers if it's remote
                                    if obj.is_remote():
                                        self._remote_providers.add(adapter_name)
                                        
                                except (NotImplementedError, AttributeError):
                                    continue
                                    
                except Exception:
                    continue
    
    def get_adapter_class(self, provider_name: str) -> Type[BaseLLMAdapter]:
        """Get adapter class by name."""
        if provider_name not in self._adapter_map:
            available = list(self._adapter_map.keys())
            raise ValueError(f"Unknown provider: {provider_name}. Available: {available}")
        return self._adapter_map[provider_name]
    
    def get_env_var_names(self, provider_name: str) -> list[str]:
        """Get list of environment variable names for provider, in order of precedence."""
        if provider_name not in self._adapter_map:
            return []
        return self._adapter_map[provider_name].env_var_names()
    
    def get_api_key_from_env(self, provider_name: str) -> Optional[str]:
        """Get API key from environment variables, trying each in order of precedence."""
        env_var_names = self.get_env_var_names(provider_name)
        for env_var in env_var_names:
            if value := os.getenv(env_var):
                return value
        return None
    
    def is_remote(self, provider_name: str) -> bool:
        """Check if provider is remote."""
        return provider_name in self._remote_providers
    
    def supports_lamia_proxy(self, provider_name: str) -> bool:
        """Check if provider supports lamia proxy."""
        return provider_name in self._lamia_proxy_providers
    
    def get_all_providers(self) -> Set[str]:
        """Get all provider names."""
        return set(self._adapter_map.keys())
    
    def get_providers_requiring_api_keys(self) -> Set[str]:
        """Get providers that need API keys."""
        return {name for name, adapter_cls in self._adapter_map.items() 
                if adapter_cls.env_var_names()}


# Global registry instance
_registry = ProviderRegistry()


def get_adapter_class(provider_name: str, user_search_paths: Optional[list[str]] = None) -> Type[BaseLLMAdapter]:
    """Get adapter class by provider name."""
    if user_search_paths:
        # Create temporary registry with user adapters
        temp_registry = ProviderRegistry()
        temp_registry.add_user_adapters(user_search_paths)
        return temp_registry.get_adapter_class(provider_name)
    
    return _registry.get_adapter_class(provider_name)


def get_env_var_names(provider_name: str) -> list[str]:
    """Get list of environment variable names for provider."""
    return _registry.get_env_var_names(provider_name)


def get_api_key_from_env(provider_name: str) -> Optional[str]:
    """Get API key from environment variables with precedence."""
    return _registry.get_api_key_from_env(provider_name)


def is_remote(provider_name: str) -> bool:
    """Check if provider is remote."""
    return _registry.is_remote(provider_name)


def supports_lamia_proxy(provider_name: str) -> bool:
    """Check if provider supports lamia proxy."""
    return _registry.supports_lamia_proxy(provider_name)


def get_all_providers() -> Set[str]:
    """Get all provider names."""
    return _registry.get_all_providers()


def get_providers_requiring_api_keys() -> Set[str]:
    """Get providers that need API keys."""
    return _registry.get_providers_requiring_api_keys()


# Legacy function for backward compatibility
def get_env_var(provider_name: str) -> Optional[str]:
    """Legacy function - returns first env var name or None."""
    env_vars = get_env_var_names(provider_name)
    return env_vars[0] if env_vars else None 