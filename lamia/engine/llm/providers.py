"""Provider registry for LLM adapters."""

from typing import Dict, Type, Set, Optional
import importlib
import importlib.util
import inspect
import os
from pathlib import Path

from ...adapters.llm.base import BaseLLMAdapter
from ...adapters.llm.openai_adapter import OpenAIAdapter
from ...adapters.llm.anthropic_adapter import AnthropicAdapter
from ...adapters.llm.local.ollama_adapter import OllamaAdapter
from ...adapters.llm.lamia_adapter import LamiaAdapter


class ProviderRegistry:
    """Registry for LLM provider adapters that only loads needed adapters."""
    
    def __init__(self, needed_providers: Optional[Set[str]] = None):
        # Built-in adapters
        self._builtin_adapters = [
            OpenAIAdapter,
            AnthropicAdapter,
            OllamaAdapter,
            LamiaAdapter,
        ]
        
        # Maps for fast access
        self._adapter_map: Dict[str, Type[BaseLLMAdapter]] = {}
        self._remote_providers: Set[str] = set()
        self._lamia_proxy_providers: Set[str] = {"openai", "anthropic"}
        
        # Only load needed adapters
        self._needed_providers = needed_providers or set()
        
        # Build maps
        self._build_maps()
    
    def _build_maps(self):
        """Build maps for needed adapters only."""
        # Add built-in adapters that are needed
        for adapter_cls in self._builtin_adapters:
            name = adapter_cls.name()
            if not self._needed_providers or name in self._needed_providers:
                self._adapter_map[name] = adapter_cls
                
                # Build remote providers set
                if adapter_cls.is_remote():
                    self._remote_providers.add(name)
    
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
                                    
                                    # Only load if needed
                                    if self._needed_providers and adapter_name not in self._needed_providers:
                                        continue
                                    
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
        """Get list of environment variable names for provider."""
        if provider_name not in self._adapter_map:
            return []
        return self._adapter_map[provider_name].env_var_names()
    
    def get_api_key_from_env(self, provider_name: str) -> Optional[str]:
        """Get API key from environment variables."""
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