from typing import List, Optional, Dict, Any, Sequence, Set, Tuple, Type
from pydantic import BaseModel

from lamia import LLMModel
from lamia.adapters.llm.base import BaseLLMAdapter, has_value_constraints
from lamia.adapters.llm.lamia_cloud_llm_adapter import cloud_is_available, LamiaCloudLLMAdapter
from ...config_provider import ConfigProvider
from ...managers import Manager
from .providers import ProviderRegistry
from lamia.validation.base import ValidationResult, BaseValidator, TrackingContext
from lamia.adapters.retry.factory import RetriableAdapterFactory
from lamia.errors import MissingAPIKeysError, ExternalOperationError
from lamia.interpreter.command_types import CommandType
from lamia.interpreter.commands import LLMCommand
from lamia.validation.validators.file_validators.file_structure.json_structure_validator import JSONStructureValidator
from lamia.validation.validators.object_validator import ObjectValidator
from lamia.hooks import POST_LLM
import json
import logging

logger = logging.getLogger(__name__)


class LLMManager(Manager):
    """Manages LLM adapters and only loads the ones that are actually needed."""
    
    def __init__(self, config_provider: ConfigProvider):
        self.config_provider = config_provider
        self._use_cloud = cloud_is_available()

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
        self._lamia_supported_providers_cache: Optional[Set[str]] = None
        
        # On cloud, all LLM calls route through the cloud adapter — no API keys needed
        if self._use_cloud:
            logger.info("Cloud environment detected — routing LLM calls through cloud adapter")
        else:
            self._check_all_required_api_keys(needed_providers)

    def _get_lamia_supported_providers(self) -> Set[str]:
        if self._lamia_supported_providers_cache is None:
            from lamia.adapters.llm.lamia_adapter import LamiaAdapter
            self._lamia_supported_providers_cache = set(LamiaAdapter.get_supported_providers())
        return self._lamia_supported_providers_cache

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
        return await self._execute_with_retries(
            prompt=command.prompt,
            validator=validator,
            history=command.history,
        )
    
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
        if provider_name in self._get_lamia_supported_providers():
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

        In cloud mode, unknown providers are handled by the cloud adapter
        (VertexLLM routes any non-Google/non-Anthropic provider through
        rawPredict), so only truly unresolvable providers are rejected.
        """
        unsupported = []
        for provider_name in needed_providers:
            try:
                self.provider_registry.get_adapter_class(provider_name)
            except ValueError:
                if not self._use_cloud:
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
        cache_key = model.get_provider_name()

        if cache_key in self._adapter_cache:
            return self._adapter_cache[cache_key]

        provider_name = model.get_provider_name()

        # On cloud, route through the cloud adapter (like Ollama for local)
        if self._use_cloud:
            adapter = LamiaCloudLLMAdapter()
        else:
            api_key, use_lamia_adapter = self._resolve_api_key(provider_name)

            if use_lamia_adapter:
                from lamia.adapters.llm.lamia_adapter import LamiaAdapter
                adapter_class = LamiaAdapter
            else:
                adapter_class = self.provider_registry.get_adapter_class(provider_name)

            if adapter_class.is_remote():
                adapter = adapter_class(api_key=api_key)
            else:
                adapter = adapter_class()

        await adapter.async_initialize()

        if with_retries:
            retry_config = self.config_provider.get_retry_config()
            adapter_with_retries = RetriableAdapterFactory.create_llm_adapter(adapter, retry_config)
            self._adapter_cache[cache_key] = adapter_with_retries
            return adapter_with_retries
        else:
            return adapter
    
    async def _execute_with_retries(
        self,
        prompt: str,
        validator: Optional[BaseValidator] = None,
        history: Sequence[Dict[str, str]] = (),
    ) -> ValidationResult:
        """Execute the prompt with retry and fallback logic.
        
        Args:
            prompt: The prompt to send
            validator: Optional validator to check the response
            history: Earlier conversation turns *prompt* continues
            
        Returns:
            ValidationResult from a successful attempt
            
        Raises:
            ExternalOperationError: If external system failures occur
            RuntimeError: If all models in the chain fail
        """
        model_chain = self.config_provider.get_model_chain()
        if not model_chain:
            raise ValueError(
                "No models configured in model_chain. "
                "Add a model to your config.yaml, e.g.:\n"
                "model_chain:\n"
                "  - name: \"anthropic:claude-sonnet-4\"\n"
                "    max_retries: 3"
            )

        failed_models = []
        failed_attempts: List[Tuple[str, ValidationResult]] = []
        total_attempts = sum(m.retries for m in model_chain)
        first_attempt = 1

        for model_and_retries in model_chain:
            model = model_and_retries.model

            # Lazily create and cache adapters so we don't re-instantiate them
            if model in self._adapter_cache:
                adapter = self._adapter_cache[model]
            else:
                adapter = await self.create_adapter_from_config(model)
                self._adapter_cache[model] = adapter

            # Build prompt per-adapter: suppress schema hint only when the
            # adapter actually implements provider-native structured output.
            if validator is not None:
                response_model = self._extract_response_model(validator)
                if response_model is not None and adapter.supports_structured_output:
                    # Providers accept the JSON structure schema but some
                    # silently ignore value-constraint keywords (minimum,
                    # maxLength, etc.) at decoding time, and Anthropic
                    # rejects them outright.  Append initial_hints, which do
                    # contain constraint hints, to the prompt so the LLM still
                    # aims to satisfy them on the first attempt.
                    if has_value_constraints(response_model):
                        initial_hints = validator.initial_hint
                        current_prompt = f"{initial_hints}\n\n{prompt}"
                    else:
                        current_prompt = prompt
                else:
                    initial_hints = validator.initial_hint
                    current_prompt = f"{initial_hints}\n\n{prompt}"
            else:
                current_prompt = prompt

            # Change from INFO to DEBUG for routine operations
            logger.debug(f"Trying model '{model.name}' with {model_and_retries.retries} max attempts")
            
            failures_before_model = len(failed_attempts)
            # This will either succeed (return ValidationResult), 
            # exhaust retries (return None), or bubble up exceptions naturally
            result = await self._generate_and_validate(
                adapter=adapter,
                model=model_and_retries.model,
                prompt=current_prompt,
                validator=validator,
                max_attempts=model_and_retries.retries,
                history=history,
                failed_attempts=failed_attempts,
                first_attempt=first_attempt,
                total_attempts=total_attempts,
            )
            
            if result is not None:
                if failed_attempts or failed_models:
                    attempt = first_attempt + len(failed_attempts) - failures_before_model
                    logger.info(
                        f"Attempt {attempt}/{total_attempts} recovered with model '{model.name}'"
                    )
                return result
            first_attempt += model_and_retries.retries
            
            # This model exhausted retries, try next one
            logger.info(f"Model {model.name} exhausted all retries, trying next fallback")
            failed_models.append(model.name)
                
        raise ValueError(
            f"All models in the chain exhausted retries: {', '.join(failed_models)}. "
            "Check the log file for validation errors or increase max_retries in config.yaml."
        )

    @staticmethod
    def _extract_response_model(validator: Optional[BaseValidator]) -> Optional[Type[BaseModel]]:
        """Return the Pydantic model for provider-native structured output, if applicable.

        Only JSONStructureValidator and ObjectValidator support provider-native structured
        output, because the schema validation and extracton can be offloaded directly to the model provider —
        eliminating Lamia's own extraction. Also, retry loop cycles are greatly reduced. If a schema keyword is enforced by a provider, chances of model returning not valid response is almost 0.
        Note that Lamia still does the it's own validations because not all json schema constraints are forced by not all model providers and bug might happen in provider responses.

        HTML, XML, YAML, Markdown, CSV, and plain text validators intentionally remain
        on regular text generation with Lamia-side validation. Reasons:
        - LLMs produce better HTML, XML, and other structured formats as plain text
        than when forced to emit them as JSON string values.
        - No JSON escaping nightmare: figuring out how to represent HTML attributes,
        self-closing tags, and non-trivial components inside a JSON string is painful
        and error-prone.
        - No need to convert the result back from JSON to the target format after the fact.
        - Requesting HTML (or XML, YAML, Markdown) as a JSON string field would require
        the model to JSON-escape every quote, newline, and special character inside the
        markup — recreating the exact escaping problem that structured output is meant
        to solve, but worse. The result would then need to be unescaped and decoded back
        into the original format anyway.
        - Plain text responses are compatible with streaming (HTML, TEXT, Markdown, etc.)
        if Lamia adds streaming support in the future. Provider-native structured output
        requires buffering the full response before delivery, making streaming impractical
        for strict schema assembly.

        """
        if isinstance(validator, JSONStructureValidator):
            return validator.model
        if isinstance(validator, ObjectValidator):
            return validator.model
        return None

    async def _generate_and_validate(
        self,
        adapter: BaseLLMAdapter,
        model: LLMModel,
        prompt: str,
        validator: Optional[BaseValidator] = None,
        max_attempts: int = 1,
        history: Sequence[Dict[str, str]] = (),
        failed_attempts: Optional[List[Tuple[str, ValidationResult]]] = None,
        first_attempt: int = 1,
        total_attempts: Optional[int] = None,
    ) -> Optional[ValidationResult]:
        """
        Try to generate and validate a response with retries for this model.

        Args:
            prompt: The prompt rendered for this model.
            failed_attempts: ``(response, validation_result)`` of earlier failed attempts, shared across the model chain and appended to on each validation failure. Each call renders them for this model as user/assistant turns after *history* and *prompt*.
            first_attempt: Chain-wide number of this model's first attempt, used in log messages.
            total_attempts: Chain-wide attempt budget, used in log messages. Defaults to *max_attempts*.

        Returns:
            ValidationResult if successful, None if all retries exhausted
            
        Raises:
            Other exceptions: Programming errors bubble up immediately
        """
        if failed_attempts is None:
            failed_attempts = []
        if total_attempts is None:
            total_attempts = max_attempts
        attempts = 0
        while attempts < max_attempts:
            attempts += 1
            attempt_label = f"{first_attempt + attempts - 1}/{total_attempts}"

            turns = [{"role": "user", "content": prompt}]
            for response_text, failed_result in failed_attempts:
                turns.append({"role": "assistant", "content": response_text})
                turns.append({"role": "user", "content": self._build_retry_prompt(failed_result)})
            
            logger.info(f"[Lamia][Ask][Attempt {attempt_label}] Prompt sent to model '{model.name}'")
            logger.debug(f"Current prompt: {turns[-1]['content']}")
            response_model = self._extract_response_model(validator)
            try:
                if history or failed_attempts:
                    response = await adapter.generate_messages(
                        [*history, *turns],
                        model=model,
                        response_model=response_model,
                    )
                else:
                    response = await adapter.generate(
                        prompt,
                        model=model,
                        response_model=response_model,
                    )
            except ExternalOperationError as e:
                logger.info(
                    f"Attempt {attempt_label} failed with model '{model.name}': API call failed: {e}. "
                    "Trying next model in chain."
                )
                return None
            logger.info(f"[Lamia][Answer][Attempt {attempt_label}] Received response from model '{model.name}'")
            logger.debug(f"Response: {response.text}")
            
            # Apply post_llm hooks before validation (context already set by facade)
            response_text = self.hook_runner.apply_transform(POST_LLM, response.text)

            # Validate the response
            if validator is not None:
                # Create execution context for tracking
                tracking_context = TrackingContext(
                    data_provider_name=model.name,
                    command_type=CommandType.LLM,
                    metadata={"usage": response.usage, "model": response.model}
                )
                
                validation_result = await validator.validate(
                    response_text,
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
                    validated_text=response_text,
                    execution_context=execution_context
                )
            
            logger.info(
                f"Attempt {attempt_label} failed validation with model '{model.name}': "
                f"{validation_result.error_message}"
            )
            logger.debug(f"[Lamia][FailedResponse][Attempt {attempt_label}] {response.text[:500]}")

            failed_attempts.append((response.text, validation_result))

        # All retries exhausted for this model
        return None

    async def close(self):
        """Close and cleanup all managed adapters."""
        for adapter in self._adapter_cache.values():
            await adapter.close()
        self._adapter_cache.clear()

    @staticmethod
    def _build_retry_prompt(validation_result: ValidationResult) -> str:
        """Return the user message asking the model to fix a failed response."""
        return f"Previous response failed validation. Issue: {validation_result.error_message}. Hint: {validation_result.hint}. Please try again."


