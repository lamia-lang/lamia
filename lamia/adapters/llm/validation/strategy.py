from typing import List, Optional, Dict, Any, Type
from dataclasses import dataclass
import logging

from ..base import BaseLLMAdapter, LLMResponse
from .base import BaseValidator, ValidationResult

logger = logging.getLogger(__name__)

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
            validator_type = validator_config.pop("type")
            if validator_type in self.validator_registry:
                validator_class = self.validator_registry[validator_type]
                validators.append(validator_class(**validator_config))
            else:
                logger.warning(f"Unknown validator type: {validator_type}")
                
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
                
        return ValidationResult(is_valid=True)

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
        
        while attempts < self.config.max_retries:
            attempts += 1
            try:
                response = await current_adapter.generate(prompt, **kwargs)
                
                # Validate the response
                validation_result = await self.validate_response(response.text)
                if validation_result.is_valid:
                    return response
                
                logger.warning(
                    f"Attempt {attempts}/{self.config.max_retries} failed validation: "
                    f"{validation_result.error_message}"
                )
                errors.append(validation_result.error_message)
                
                # Try fallback model if available
                if (self.config.fallback_models and 
                    attempts < len(self.config.fallback_models) + 1):
                    fallback_model = self.config.fallback_models[attempts - 1]
                    logger.info(f"Trying fallback model: {fallback_model}")
                    current_adapter = create_adapter_fn(fallback_model)
                    
            except Exception as e:
                logger.error(f"Attempt {attempts} failed with error: {str(e)}")
                errors.append(str(e))
                
        raise RuntimeError(
            f"All {attempts} attempts failed. Errors: {'; '.join(errors)}"
        ) 