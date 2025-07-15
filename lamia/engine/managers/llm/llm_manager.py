
from typing import List, Optional, Dict, Any, Set
import os
from lamia.adapters.llm.lamia_adapter import LamiaAdapter
from lamia import LLMModel
from lamia.adapters.llm.base import BaseLLMAdapter
from ...config_provider import ConfigProvider
from ...managers import Manager
from .providers import ProviderRegistry
from ...validation_strategies.validation_strategy import ValidationStrategy
from lamia.validation.base import ValidationResult
import logging


logger = logging.getLogger(__name__)

class MissingAPIKeysError(Exception):
    """Raised when one or more required API keys are missing for LLM engines."""
    def __init__(self, missing):
        def get_api_keys_constructor_string(provider_names: List[str]) -> str:
            return "Lamia(..., api_keys={" + \
                ", ".join([f'"{provider_name}": "my-api-key"' for provider_name in provider_names]) + \
                "}"

        self.missing = missing
        missing_providers = [model_provider for model_provider, _ in missing]
        message = (
            "The following engines are missing required API keys:\n" +
            "\n".join([f"- {model_provider}: missing {env_vars}" for model_provider, env_vars in missing]) +
            "\n\nPlease provide the missing API keys in one of the following ways:\n" +
            "- As environment variables (e.g., export OPENAI_API_KEY=...)\n" +
            "- As a parameter to the Lamia() constructor like this: " + get_api_keys_constructor_string([provider for provider,_ in missing]) + "\n" +
            (f"You can also use LAMIA_API_KEY or {get_api_keys_constructor_string(['lamia'])} to proxy remote adapters ({', '.join(LamiaAdapter.get_supported_providers())}).\n" if all(provider in LamiaAdapter.get_supported_providers() for provider in missing_providers) else "") +
            "Alternatively, remove these engines from your default or fallback_models in config."
        )
        super().__init__(message)

class LLMManager(Manager):
    """Manages LLM adapters and only loads the ones that are actually needed."""
    
    def __init__(self, config_provider: ConfigProvider, validation_strategy: ValidationStrategy):
        self.config_provider = config_provider
        self.validation_strategy = validation_strategy
        # Determine which providers are needed based on config
        needed_providers = self._get_needed_providers()
        
        # Initialize provider registry with only needed providers
        self.provider_registry = ProviderRegistry(needed_providers)

        self._adapter_cache = {}
        
        # Add user adapters from extensions
        ext_folder = self.config_provider.get_extensions_folder()
        ext_adapters_path = os.path.join(os.getcwd(), ext_folder, "adapters")
        self.provider_registry.add_user_adapters([ext_adapters_path])
        
        # Check if all needed providers are supported
        self._check_all_required_providers(needed_providers)

        # Check API keys early
        self._check_all_required_api_keys(needed_providers)
        self._initialized = True
    
    def _get_needed_providers(self) -> Set[str]:
        """Get the set of providers that are actually needed based on config."""
        needed = set()
        
        # Add default model provider
        default_model = self.config_provider.get_primary_model()
        if default_model:
            needed.add(default_model.model.get_provider_name())
        
        # Add fallback models providers
        fallback_models = self.config_provider.get_fallback_models()
        needed.update([model.model.get_provider_name() for model in fallback_models])
        
        return needed
    
    def _resolve_api_key(self, provider_name: str) -> Optional[str]:
        """
        Get and validate API key from config_provider config.
        Returns the API key if found, otherwise raises MissingAPIKeysError.
        Priority: specific provider key > lamia key (for remote providers) > env var fallback (with precedence).
        """

        # Priority: lamia key > lamia env key > provider key > provider env key
        if provider_name in LamiaAdapter.get_supported_providers():
            lamia_api_key = self.config_provider.get_api_key("lamia")
            if lamia_api_key:
                return lamia_api_key, True
        
        lamia_env_api_key = self.provider_registry.get_api_key_from_env("lamia")
        if lamia_env_api_key:
            return lamia_env_api_key, True

        api_key = self.config_provider.get_api_key(provider_name)
        if api_key:
            return api_key, False

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
    
    def _check_all_required_providers(self, needed_providers: Set[str]):
        """
        Check that all required providers are supported.
        If any are missing, raise ValueError.
        """
        unsupported = []
        for provider_name in needed_providers:
            try:
                self.provider_registry.get_adapter_class(provider_name)
            except ValueError as e:
                unsupported.append(provider_name)

        if unsupported:
            raise ValueError(
                f"The following providers are not supported: {', '.join(unsupported)}.\n"
                "Please either:\n"
                "- Remove them from the model chain\n"
                "- Add corresponding adapters to your extensions folder."
            )
        
    def _check_all_required_api_keys(self, needed_providers: Set[str]):
        """
        Check that all required API keys for default and fallback engines are present.
        If any are missing, raise MissingAPIKeysError.
        """
        
        missing = []
        for provider_name in needed_providers:
            try:
                self._resolve_api_key(provider_name)
            except MissingAPIKeysError as e:
                missing.extend(e.missing)
        
        if missing:
            raise MissingAPIKeysError(missing)
    
    async def create_adapter_from_config(self, model: LLMModel) -> BaseLLMAdapter:
        """Create an adapter instance based on the active configuration."""
        # Use the full model name as cache key – guarantees one adapter per model
        cache_key = model.get_provider_name()

        if cache_key in self._adapter_cache:
            return self._adapter_cache[cache_key]

        provider_name = model.get_provider_name()
        api_key, use_lamia_adapter = self._resolve_api_key(provider_name)

        # Get the adapter class
        if use_lamia_adapter:
            adapter_class = LamiaAdapter
        else:
            adapter_class = self.provider_registry.get_adapter_class(provider_name)

        if adapter_class.is_remote():
            adapter = adapter_class(api_key=api_key)
        else:
            adapter = adapter_class()

        await adapter.async_initialize()

        # Cache for reuse
        self._adapter_cache[cache_key] = adapter

        return adapter

    async def execute(
        self,
        prompt: str,
    ) -> ValidationResult:
        """Generate a response using the managed adapter.
        
        Args:
            prompt: The input prompt
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            
        Returns:
            LLMResponse containing the generated text and metadata
        """
        # Use the existing validation logic
        return await self.execute_with_retries(
            prompt=prompt,
        )

    async def execute_with_retries(
        self,
        prompt: str
    ) -> ValidationResult:
        """Execute the prompt with retry and fallback logic.
        
        Args:
            primary_adapter: The primary LLM adapter to use
            prompt: The prompt to send
            **kwargs: Additional parameters for generate()
            
        Returns:
            ValidationResult from a successful attempt
            
        Raises:
            RuntimeError: If all attempts fail
        """
        primary_model = self.config_provider.get_primary_model().model
        primary_adapter = await self.create_adapter_from_config(primary_model)
        # Aggregate initial hints from all validators
        initial_hints = self.validation_strategy.get_initial_hints()
        initial_hint_text = "\n".join(initial_hints)
        if initial_hint_text:
            current_prompt = f"{initial_hint_text}\n\n{prompt}"
        else:
            current_prompt = prompt
        
        try:
            return await self._generate_and_validate(
                adapter=primary_adapter,
                model=primary_model,
                prompt=current_prompt,
                max_attempts=self.config_provider.get_primary_model().retries,
            )
        except Exception as e:
            # Try fallback model if available
            fallback_models = self.config_provider.get_fallback_models()
            for fallback_model in fallback_models:
                logger.info(f"Trying fallback model: {fallback_model.model.name}")
                # Lazily create and cache adapters so we don't re-instantiate them
                if fallback_model in self._adapter_cache:
                    fallback_adapter = self._adapter_cache[fallback_model]
                else:
                    fallback_adapter = await self.create_adapter_from_config(fallback_model.model)
                    self._adapter_cache[fallback_model] = fallback_adapter
                # Reset prompt for new adapter, with initial hints
                if initial_hint_text:
                    current_prompt = f"{initial_hint_text}\n\n{prompt}"
                else:
                    current_prompt = prompt

                try:
                    return await self._generate_and_validate(
                        adapter=fallback_adapter,
                        model=fallback_model.model,
                        prompt=current_prompt,
                        max_attempts=fallback_model.retries,
                    )
                except Exception as e:
                    # Continue to the next fallback model
                    pass
                
        raise RuntimeError(
            f"All attempts failed. Giving up."
        )
    
    async def _generate_and_validate(
        self,
        adapter: BaseLLMAdapter,
        model: LLMModel,
        prompt: str,
        max_attempts: int,
    ) -> ValidationResult:
        errors = []
        attempts = 0
        current_prompt = prompt
        while attempts < max_attempts:
            attempts += 1
            try:
                logger.info(f"[Lamia][Ask][Attempt {attempts}] Prompt sent to model '{model.name}':\n{current_prompt}")
                response = await adapter.generate(current_prompt, model=model)
                logger.info(f"[Lamia][Answer][Attempt {attempts}] Response from model '{model.name}':\n{response.text}")
                
                # Validate the response
                validation_result = await self.validation_strategy.validate(response.text)
                if validation_result.is_valid:
                    return validation_result
                
                logger.warning(
                    f"Attempt {attempts}/{max_attempts} failed validation: "
                    f"{validation_result.error_message}"
                )
                errors.append(validation_result.error_message)

                # Construct retry prompt based on context memory
                # TODO: Maybe we need to send whole chat history, for telling about all errors that the model made?
                if adapter.has_context_memory:
                    # Only send the validation issue and hint
                    retry_message = f"The previous response had an issue: {validation_result.error_message}. Hint: {validation_result.hint}. Please try again."
                    current_prompt = retry_message
                else:
                    # Resend the original prompt plus the validation issue and hint
                    retry_message = f"Previous response failed validation. Issue: {validation_result.error_message}. Hint: {validation_result.hint}. Please try again.\n\nOriginal prompt:\n{prompt}"
                    current_prompt = retry_message
                
            except Exception as e:
                logger.error(f"Attempt {attempts} failed with error: {str(e)}")
                errors.append(str(e))

        raise RuntimeError(
            f"All {attempts} attempts failed with {adapter.name}. Errors: {'; '.join(errors)}"
        ) 
    
    async def close(self):
        """Close and cleanup all managed adapters."""
        for adapter in self._adapter_cache.values():
            await adapter.close()
        self._adapter_cache.clear()
        self._initialized = False


