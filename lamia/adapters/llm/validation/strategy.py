from typing import List, Optional, Dict, Any, Type
from dataclasses import dataclass
import logging
import sys

from ..base import BaseLLMAdapter, LLMResponse
from .base import BaseValidator, ValidationResult

logger = logging.getLogger(__name__)

def grey_text(text: str) -> str:
    # Only colorize if output is a TTY (terminal)
    if sys.stdout.isatty():
        return f"\033[90m{text}\033[0m"
    return text

@dataclass
class RetryConfig:
    """Configuration for retry strategy."""
    max_retries: int = 1
    fallback_models: List[str] = None  # List of model names to try if primary fails
    validators: List[Dict[str, Any]] = None  # List of validator configs

class ValidationStrategy:
    """Handles response validation and retry logic."""
    
    def __init__(
        self,
        config: RetryConfig,
        validator_registry: Dict[str, Type[BaseValidator]]
    ):
        """Initialize the validation strategy.
        
        Args:
            config: Retry configuration
            validator_registry: Registry of available validators
        """
        self.config = config
        self.validator_registry = validator_registry
        self.validators = self._setup_validators()
        
    def _setup_validators(self) -> List[BaseValidator]:
        """Set up validators from configuration."""
        validators = []
        if not self.config.validators:
            return validators
            
        for validator_config in self.config.validators:
            validator_type = validator_config.get("type")
            strict = validator_config.get("strict", True)
            config_copy = validator_config.copy()
            config_copy.pop("type", None)
            config_copy.pop("strict", None)
            if validator_type in self.validator_registry:
                validator_class = self.validator_registry[validator_type]
                validators.append(validator_class(strict=strict, **config_copy))
            else:
                raise ValueError(f"Unknown validator type: {validator_type}")
        
        # Check for duplicate validator names
        names = [v.name for v in validators]
        duplicates = set([name for name in names if names.count(name) > 1])
        if duplicates:
            raise ValueError(f"Duplicate validator name(s) detected: {', '.join(duplicates)}")
        return validators

    async def validate_response(self, response: str) -> ValidationResult:
        """Validate a response against all configured validators.
        
        Args:
            response: The model's response to validate
            
        Returns:
            ValidationResult with combined validation results
        """
        for validator in self.validators:
            result = await validator.validate(response)
            if not result.is_valid:
                logger.info(f"Validation failed for {validator.name}: {result.error_message}")
                return result
            # If a validator provides validated_text, propagate it for next validator
            if result.validated_text is not None:
                response = result.validated_text
        return ValidationResult(is_valid=True, validated_text=response)

    async def execute_with_retries(
        self,
        primary_adapter: BaseLLMAdapter,
        prompt: str,
        create_adapter_fn,
        **kwargs
    ) -> LLMResponse:
        """Execute the prompt with retry and fallback logic.
        
        Args:
            primary_adapter: The primary LLM adapter to use
            prompt: The prompt to send
            create_adapter_fn: Function to create new adapters for fallbacks
            **kwargs: Additional parameters for generate()
            
        Returns:
            LLMResponse from a successful attempt
            
        Raises:
            RuntimeError: If all attempts fail
        """
        attempts = 0
        errors = []
        current_adapter = primary_adapter
        # Aggregate initial hints from all validators
        initial_hints = [v.initial_hint for v in self.validators if hasattr(v, 'initial_hint')]
        initial_hint_text = "\n".join(initial_hints)
        if initial_hint_text:
            current_prompt = f"{initial_hint_text}\n\n{prompt}"
        else:
            current_prompt = prompt
        
        while attempts < self.config.max_retries:
            attempts += 1
            try:
                logger.info(f"[Lamia][Ask][Attempt {attempts}] Prompt sent to model '{getattr(current_adapter, 'model', 'unknown')}':\n{grey_text(current_prompt)}")
                response = await current_adapter.generate(current_prompt, **kwargs)
                logger.info(f"[Lamia][Answer][Attempt {attempts}] Response from model '{getattr(current_adapter, 'model', 'unknown')}':\n{response.text}")
                
                # Validate the response
                validation_result = await self.validate_response(response.text)
                if validation_result.is_valid:
                    # If validated_text is present, return a new LLMResponse with it
                    if validation_result.validated_text is not None:
                        return type(response)(**{**response.__dict__, 'text': validation_result.validated_text})
                    return response
                
                logger.warning(
                    f"Attempt {attempts}/{self.config.max_retries} failed validation: "
                    f"{validation_result.error_message}"
                )
                errors.append(validation_result.error_message)

                # Construct retry prompt based on context memory
                if current_adapter.has_context_memory:
                    # Only send the validation issue and hint
                    retry_message = f"The previous response had an issue: {validation_result.error_message}. Hint: {validation_result.hint}. Please try again."
                    current_prompt = retry_message
                else:
                    # Resend the original prompt plus the validation issue and hint
                    retry_message = f"Previous response failed validation. Issue: {validation_result.error_message}. Hint: {validation_result.hint}. Please try again.\n\nOriginal prompt:\n{prompt}"
                    current_prompt = retry_message
                
                # Try fallback model if available
                if (self.config.fallback_models and 
                    attempts < len(self.config.fallback_models) + 1):
                    fallback_model = self.config.fallback_models[attempts - 1]
                    logger.info(f"Trying fallback model: {fallback_model}")
                    current_adapter = create_adapter_fn(fallback_model)
                    # Reset prompt for new adapter, with initial hints
                    if initial_hint_text:
                        current_prompt = f"{initial_hint_text}\n\n{prompt}"
                    else:
                        current_prompt = prompt
                
            except Exception as e:
                logger.error(f"Attempt {attempts} failed with error: {str(e)}")
                errors.append(str(e))
                
        raise RuntimeError(
            f"All {attempts} attempts failed. Errors: {'; '.join(errors)}"
        ) 