from typing import List, Optional, Dict, Any, Set, Tuple

from lamia.adapters.llm.lamia_adapter import LamiaAdapter
from lamia import LLMModel
from lamia.adapters.llm.base import BaseLLMAdapter
from ...config_provider import ConfigProvider
from ...managers import Manager
from .providers import ProviderRegistry
from lamia.validation.base import ValidationResult, BaseValidator, TrackingContext
from lamia.adapters.retry.factory import RetriableAdapterFactory
from lamia.errors import MissingAPIKeysError
from lamia.interpreter.command_types import CommandType
from lamia.interpreter.commands import LLMCommand
from .files_context_manager import get_active_files_context
import logging

logger = logging.getLogger(__name__)


class LLMManager(Manager):
    """Manages LLM adapters and only loads the ones that are actually needed."""
    
    def __init__(self, config_provider: ConfigProvider):
        self.config_provider = config_provider
        # Determine which providers are needed based on config
        needed_providers = self._get_needed_providers() 

        # Initialize provider registry with only needed providers
        self.provider_registry = ProviderRegistry(needed_providers)

        # Load user adapters from extensions folder
        extensions_folder = config_provider.get_extensions_folder()
        adapters_path = f"{extensions_folder}/adapters"
        self.provider_registry.add_user_adapters([adapters_path])

        # Check that all required providers are supported
        self._check_all_required_providers(needed_providers)

        self._adapter_cache = {}
        
        # Check that all required API keys are present
        self._check_all_required_api_keys(needed_providers)

    async def execute(
        self,
        command: LLMCommand,
        validator: Optional[BaseValidator] = None
    ) -> ValidationResult:
        """Generate a response using the managed adapter.
        
        Args:
            command: The LLM command containing the prompt
            validator: Optional validator for the response
            
        Returns:
            ValidationResult containing the generated text and metadata
        """
        # Extract prompt from LLMCommand
        prompt = command.prompt
        
        # Inject file references if in a files context
        prompt = self._inject_file_references(prompt)
        
        # Use the existing validation logic
        return await self._execute_with_retries(
            prompt=prompt,
            validator=validator
        )

    def _inject_file_references(self, prompt: str) -> str:
        """Inject file references from active files context."""
        context = get_active_files_context()
        if context:
            return context.inject_file_references(prompt)
        return prompt
    
    def _get_needed_providers(self) -> Set[str]:
        """Get the set of providers that are actually needed based on config."""
        needed = set()
        
        # Add default model provider
        model_chain = self.config_provider.get_model_chain()
        if model_chain:
            needed.update([model.model.get_provider_name() for model in model_chain])
        
        return needed

    def _resolve_api_key(self, provider_name: str) -> Tuple[Optional[str], bool]:
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

    async def create_adapter_from_config(self, model: LLMModel, with_retries: bool = True) -> BaseLLMAdapter:
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

        if with_retries:
            # Get user-provided retry config or use defaults
            retry_config = self.config_provider.get_retry_config()
            adapter_with_retries = RetriableAdapterFactory.create_llm_adapter(adapter, retry_config)

            # Cache for reuse
            self._adapter_cache[cache_key] = adapter_with_retries

            return adapter_with_retries
        else:
            # Return raw adapter without retry wrapping
            return adapter
    
    async def _execute_with_retries(
        self,
        prompt: str,
        validator: Optional[BaseValidator] = None,
    ) -> ValidationResult:
        """Execute the prompt with retry and fallback logic.
        
        Args:
            prompt: The prompt to send
            validator: Optional validator to check the response
            
        Returns:
            ValidationResult from a successful attempt
            
        Raises:
            ExternalOperationError: If external system failures occur
            RuntimeError: If all models in the chain fail
        """
        if validator is not None:
            initial_hints = validator.initial_hint
            current_prompt = f"{initial_hints}\n\n{prompt}"
        else:
            current_prompt = prompt

        failed_models = []
        
        for model_and_retries in self.config_provider.get_model_chain():
            model = model_and_retries.model

            # Lazily create and cache adapters so we don't re-instantiate them
            if model in self._adapter_cache:
                adapter = self._adapter_cache[model]
            else:
                adapter = await self.create_adapter_from_config(model)
                self._adapter_cache[model] = adapter

            # Change from INFO to DEBUG for routine operations
            logger.debug(f"Trying model '{model.name}' with {model_and_retries.retries} max attempts")
            
            # This will either succeed (return ValidationResult), 
            # exhaust retries (return None), or bubble up exceptions naturally
            result = await self._generate_and_validate(
                adapter=adapter,
                model=model_and_retries.model,
                prompt=current_prompt,
                validator=validator,
                max_attempts=model_and_retries.retries,
            )
            
            if result is not None:
                return result
            
            # This model exhausted retries, try next one
            logger.warning(f"Model {model.name} exhausted all retries, trying next fallback")
            failed_models.append(model.name)
                
        # All models failed
        raise ValueError(f"All models failed: {', '.join(failed_models)}")

    async def _generate_and_validate(
        self,
        adapter: BaseLLMAdapter,
        model: LLMModel,
        prompt: str,
        validator: Optional[BaseValidator] = None,
        max_attempts: int = 1,  
    ) -> Optional[ValidationResult]:
        """
        Try to generate and validate a response with retries for this model.
        
        Returns:
            ValidationResult if successful, None if all retries exhausted
            
        Raises:
            ExternalOperationError: Bubbles up immediately (don't try other models)
            Other exceptions: Programming errors bubble up immediately
        """
        attempts = 0
        current_prompt = prompt
        while attempts < max_attempts:
            attempts += 1
            
            logger.info(f"[Lamia][Ask][Attempt {attempts}] Prompt sent to model '{model.name}'")
            logger.debug(f"Current prompt: {current_prompt}")
            response = await adapter.generate(current_prompt, model=model)
            logger.info(f"[Lamia][Answer][Attempt {attempts}] Received response from model '{model.name}'")
            logger.debug(f"Response: {response.text}")
            
            # Validate the response
            if validator is not None:
                # Create execution context for tracking
                tracking_context = TrackingContext(
                    data_provider_name=model.name,
                    command_type=CommandType.LLM,
                    metadata={"usage": response.usage, "model": response.model}
                )
                
                validation_result = await validator.validate(
                    response.text, 
                    execution_context=tracking_context
                )
                if validation_result.is_valid:
                    return validation_result
            else:
                # Create execution context even when no validator is used
                execution_context = TrackingContext(
                    data_provider_name=model.name,
                    command_type=CommandType.LLM,
                    metadata={"usage": response.usage, "model": response.model}
                )
                
                return ValidationResult(
                    is_valid=True,
                    raw_text=response.text,
                    validated_text=response.text,
                    execution_context=execution_context
                )
            
            logger.warning(
                f"Model '{model.name}' attempt {attempts} validation failed: "
                f"{validation_result.error_message}"
            )
            logger.info(f"[Lamia][FailedResponse][Attempt {attempts}] {response.text[:500]}")

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

        # All retries exhausted for this model
        return None

    async def close(self):
        """Close and cleanup all managed adapters."""
        for adapter in self._adapter_cache.values():
            await adapter.close()
        self._adapter_cache.clear()


