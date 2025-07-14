from typing import List, Optional, Dict, Any, Type
from dataclasses import dataclass
import logging
import sys

from .base import BaseLLMAdapter, LLMResponse
from ...validation.base import BaseValidator, ValidationResult
from ...engine.interfaces import ValidationStrategy, Manager
from lamia._internal_types.model_retry import ModelWithRetries

logger = logging.getLogger(__name__)

def grey_text(text: str) -> str:
    # Only colorize if output is a TTY (terminal)
    if sys.stdout.isatty():
        return f"\033[90m{text}\033[0m"
    return text

@dataclass
class RetryConfig:
    """Configuration for retry strategy."""
    model_chain: List[ModelWithRetries] = None
    validators: List[Dict[str, Any]] = None  # List of validator configs

class LLMValidationStrategy(ValidationStrategy):
    """Handles response validation and retry logic."""
    
    def __init__(
        self,
        validator_registry: Dict[str, Type[BaseValidator]]
    ):
        """Initialize the validation strategy.
        
        Args:
            config: Retry configuration
            validator_registry: Registry of available validators
        """
        super().__init__(validator_registry, validators)

        # Cache for lazily-created fallback adapters
        self._adapter_cache: Dict[str, BaseLLMAdapter] = {}
        self._initialized = True
    
    async def validate(self, manager: Manager, content: str, **kwargs) -> Any:
        """Validate LLM content using this strategy.
        
        Args:
            manager: The LLM manager to use
            content: The prompt to validate
            **kwargs: LLM generation parameters
            
        Returns:
            Validated LLMResponse
        """
        
        # Use the existing validation logic
        return await self.execute_with_retries(
            manager=manager,
            prompt=content,
            **kwargs
        )

    async def execute_with_retries(
        self,
        manager: Manager,
        prompt: str,
        **kwargs
    ) -> LLMResponse:
        """Execute the prompt with retry and fallback logic.
        
        Args:
            primary_adapter: The primary LLM adapter to use
            prompt: The prompt to send
            **kwargs: Additional parameters for generate()
            
        Returns:
            LLMResponse from a successful attempt
            
        Raises:
            RuntimeError: If all attempts fail
        """
        primary_adapter = await manager.get_primary_adapter()
        # Aggregate initial hints from all validators
        initial_hints = [v.initial_hint for v in self.validators if hasattr(v, 'initial_hint')]
        initial_hint_text = "\n".join(initial_hints)
        if initial_hint_text:
            current_prompt = f"{initial_hint_text}\n\n{prompt}"
        else:
            current_prompt = prompt
        
        try:
            return await self._generate_and_validate(
                adapter=primary_adapter,
                prompt=current_prompt,
                max_attempts=self.config.max_retries,
                **kwargs,
            )
        except Exception as e:
            # Try fallback model if available
            if self.config.fallback_models:
                for fallback_model in self.config.fallback_models:
                    logger.info(f"Trying fallback model: {fallback_model}")
                    # Lazily create and cache adapters so we don't re-instantiate them
                    if fallback_model in self._adapter_cache:
                        fallback_adapter = self._adapter_cache[fallback_model]
                    else:
                        fallback_adapter = await manager.create_adapter_from_config(fallback_model)
                        self._adapter_cache[fallback_model] = fallback_adapter
                    # Reset prompt for new adapter, with initial hints
                    if initial_hint_text:
                        current_prompt = f"{initial_hint_text}\n\n{prompt}"
                    else:
                        current_prompt = prompt

                    try:
                        return await self._generate_and_validate(
                            adapter=fallback_adapter,
                            prompt=current_prompt,
                            max_attempts=1, # Fallback models are used only once
                            **kwargs,
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
        prompt: str,
        max_attempts: int,
        **kwargs,
    ) -> LLMResponse:
        errors = []
        attempts = 0
        current_prompt = prompt
        while attempts < self.config.max_retries:
            attempts += 1
            try:
                logger.info(f"[Lamia][Ask][Attempt {attempts}] Prompt sent to model '{getattr(adapter, 'model', 'unknown')}':\n{grey_text(current_prompt)}")
                response = await adapter.generate(current_prompt, **kwargs)
                logger.info(f"[Lamia][Answer][Attempt {attempts}] Response from model '{getattr(adapter, 'model', 'unknown')}':\n{response.text}")
                
                # Validate the response
                validation_result = await self.chain_validate(response.text)
                if validation_result.is_valid:
                    # If validated_text is present, return a new LLMResponse with it
                    if validation_result.validated_text is not None:
                        return type(response)(**{**response.__dict__, 'text': validation_result.validated_text})
                    return response
                
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