"""Provider registry for LLM adapters."""

import logging
from typing import Dict, Type, Set, Optional, FrozenSet
import importlib
import importlib.util
import inspect
import os
from pathlib import Path

from lamia.adapters.llm.base import BaseLLMAdapter
from lamia.adapters.llm.contract_checker import check_and_warn

logger = logging.getLogger(__name__)

_BUILTIN_ADAPTERS = [
    ("lamia.adapters.llm.openai_adapter", "OpenAIAdapter", "openai"),
    ("lamia.adapters.llm.anthropic_adapter", "AnthropicAdapter", "anthropic"),
    ("lamia.adapters.llm.local.ollama_adapter", "OllamaAdapter", "ollama"),
    ("lamia.adapters.llm.lamia_adapter", "LamiaAdapter", "lamia"),
]

_registry_cache: Dict[Optional[FrozenSet[str]], "ProviderRegistry"] = {}


def get_cached_provider_registry(needed_providers: Optional[Set[str]] = None) -> "ProviderRegistry":
    """Return a cached ProviderRegistry keyed by needed providers."""
    cache_key = None if needed_providers is None else frozenset(needed_providers)
    registry = _registry_cache.get(cache_key)
    if registry is None:
        registry = ProviderRegistry(needed_providers)
        _registry_cache[cache_key] = registry
    return registry


class ProviderRegistry:
    """Registry for LLM provider adapters that only loads needed adapters."""
    
    _ALWAYS_LOAD = {"lamia"}

    def __init__(self, needed_providers: Optional[Set[str]] = None):
        self._adapter_map: Dict[str, Type[BaseLLMAdapter]] = {}
        self._adapter_sources: Dict[str, str] = {}
        self._needed_providers = needed_providers
        self._remote_providers: Set[str] = set()
        
        for module_path, class_name, provider_name in _BUILTIN_ADAPTERS:
            if (self._needed_providers is not None
                    and provider_name not in self._needed_providers
                    and provider_name not in self._ALWAYS_LOAD):
                continue
            try:
                module = importlib.import_module(module_path)
                adapter_cls = getattr(module, class_name)
                self._adapter_map[provider_name] = adapter_cls
                self._adapter_sources[provider_name] = module.__file__ or module_path
                if adapter_cls.is_remote():
                    self._remote_providers.add(provider_name)
            except ImportError as e:
                logger.debug("Skipping builtin adapter '%s': %s", provider_name, e)
    
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
                                    
                                    if self._needed_providers is not None and adapter_name not in self._needed_providers:
                                        continue
                                    
                                    if adapter_name in self._adapter_map:
                                        existing_source = self._adapter_sources.get(adapter_name, "unknown")
                                        raise RuntimeError(
                                            f"Duplicate adapter name '{adapter_name}' found.\n"
                                            f"  First loaded from: {existing_source}\n"
                                            f"  Conflict from:     {file_path}\n"
                                            f"Rename one adapter's name() method to a unique provider name, "
                                            f"or remove the duplicate file."
                                        )
                                    
                                    check_and_warn(obj, str(file_path))

                                    self._adapter_map[adapter_name] = obj
                                    self._adapter_sources[adapter_name] = str(file_path)

                                    if obj.is_remote():
                                        self._remote_providers.add(adapter_name)
                                        
                                except (NotImplementedError, AttributeError):
                                    continue
                                    
                except RuntimeError:
                    raise
                except Exception as e:
                    logger.warning("Failed to load user adapter from %s: %s", file_path, e)
                    continue
    
    def get_adapter_class(self, provider_name: str) -> Type[BaseLLMAdapter]:
        """Get adapter class by name."""
        if provider_name not in self._adapter_map:
            raise ValueError(f"Unknown provider: {provider_name}.")
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
    
    def get_all_providers(self) -> Set[str]:
        """Get all provider names."""
        return set(self._adapter_map.keys())
    
    def get_providers_requiring_api_keys(self) -> Set[str]:
        """Get providers that need API keys."""
        return {name for name, adapter_cls in self._adapter_map.items() 
                if adapter_cls.env_var_names()} 