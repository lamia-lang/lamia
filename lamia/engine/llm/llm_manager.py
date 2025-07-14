
from typing import List, Optional, Dict, Any, Set
import os
from lamia.adapters.llm.lamia_adapter import LamiaAdapter
from lamia import LLMModel
from lamia.adapters.llm.base import BaseLLMAdapter, LLMResponse
from ..config_provider import ConfigProvider
from ..interfaces import Manager
from .providers import ProviderRegistry

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

class LLMManager(Manager):
    """Manages LLM adapters and only loads the ones that are actually needed."""
    
    def __init__(self, config_provider: ConfigProvider):
        self.config_provider = config_provider
        
        # Determine which providers are needed based on config
        needed_providers = self._get_needed_providers()
        
        # Initialize provider registry with only needed providers
        self.provider_registry = ProviderRegistry(needed_providers)
        
        # Add user adapters from extensions
        ext_folder = self.config_provider.get_extensions_folder()
        ext_adapters_path = os.path.join(os.getcwd(), ext_folder, "adapters")
        self.provider_registry.add_user_adapters([ext_adapters_path])
        
        # Adapter lifecycle management
        self._primary_adapter = None
        
        # Check API keys early
        self.check_all_required_api_keys()
        self._initialized = True
    
    def _get_needed_providers(self) -> Set[str]:
        """Get the set of providers that are actually needed based on config."""
        needed = set()
        
        # Add default model provider
        default_model = self.config_provider.get_primary_model()
        if default_model:
            needed.add(default_model)
        
        # Add fallback models providers
        fallback_models = self.config_provider.get_fallback_models()
        needed.update(fallback_models)
        
        return needed
    
    def _resolve_api_key(self, provider_name: str) -> Optional[str]:
        """
        Get and validate API key from config_provider config.
        Returns the API key if found, otherwise raises MissingAPIKeysError.
        Priority: specific provider key > lamia key (for remote providers) > env var fallback (with precedence).
        """

        if LamiaAdapter.supports(provider_name):
            lamia_api_key = self.config_provider.get_api_key("lamia")
            if lamia_api_key:
                return lamia_api_key, True
        
        lamia_env_api_key = self.provider_registry.get_api_key_from_env("lamia")
        if lamia_env_api_key:
            return lamia_env_api_key, True

        api_key = self.config_provider.get_api_key(provider_name)
        if api_key:
            return api_key

        env_api_key = self.provider_registry.get_api_key_from_env(provider_name)
        if env_api_key:
            return env_api_key, False

        # No API key found - only raise error if this provider needs one
        env_var_names = self.provider_registry.get_env_var_names(provider_name)
        if env_var_names:
            env_vars_str = " or ".join(env_var_names)
            raise MissingAPIKeysError([(provider_name, env_vars_str)])
        
        # Provider doesn't need an API key (e.g., local models)
        return None, False
    
    def check_all_required_api_keys(self):
        """
        Check that all required API keys for default and fallback engines are present.
        If any are missing, raise MissingAPIKeysError.
        """
        default_model = self.config_provider.get_primary_model()
        fallback_models = self.config_provider.get_fallback_models()
        required_engines = set([default_model] + fallback_models)
        
        missing = []
        for engine in required_engines:
            try:
                self._resolve_api_key(engine)
            except MissingAPIKeysError as e:
                missing.extend(e.missing)
        
        if missing:
            raise MissingAPIKeysError(missing)
    
    async def create_adapter_from_config(self, model: LLMModel) -> BaseLLMAdapter:
        """Create an adapter instance based on the active configuration."""
        provider_name = model.name
        provider_config = model.get_config()

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

        api_key, use_lamia_adapter = self._resolve_api_key(provider_name)

        # Get the adapter class
        if use_lamia_adapter:
            adapter_class = LamiaAdapter
            model_name = f"{provider_name}-{model_name}"
        else:
            adapter_class = self.provider_registry.get_adapter_class(provider_name)

        # Create adapter instance based on its requirements
        init_kwargs = {}
        
        # Add model name
        init_kwargs['api_key'] = api_key
        init_kwargs['model'] = model_name
        
        # Add provider-specific parameters
        if provider_name == "ollama":
            # Add any other ollama-specific config from provider_config
            for key in ['base_url', 'temperature', 'max_tokens', 'context_size', 'num_ctx', 'num_gpu', 'num_thread', 'repeat_penalty', 'top_k', 'top_p']:
                if key in provider_config:
                    init_kwargs[key] = provider_config[key]
        
        adapter = adapter_class(**init_kwargs)
        await adapter.async_initialize()
        return adapter

    async def get_primary_adapter(self) -> BaseLLMAdapter:
        """Get the primary adapter, creating and initializing it if needed."""
        if self._primary_adapter is None:
            self._primary_adapter = await self.create_adapter_from_config()
            
        return self._primary_adapter

    async def execute(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """Generate a response using the managed adapter.
        
        Args:
            prompt: The input prompt
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            
        Returns:
            LLMResponse containing the generated text and metadata
        """
        adapter = await self.get_primary_adapter()
        return await adapter.generate(
            prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )

    async def close(self):
        """Close and cleanup the managed adapter."""
        if self._primary_adapter:
            await self._primary_adapter.close()
        self._initialized = False