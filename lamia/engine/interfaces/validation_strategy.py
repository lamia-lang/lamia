from abc import ABC, abstractmethod
from typing import Any, List, Dict, Type
from .manager import Manager
from lamia.validation.base import BaseValidator, ValidationResult
from lamia.validation.validators import CONFLICTING_VALIDATOR_GROUPS
import logging

logger = logging.getLogger(__name__)

class ValidationStrategy(ABC):
    """Abstract base class for domain-specific validation strategies."""

    def __init__(self, validator_registry: Dict[str, Type[BaseValidator]], validator_configs : List[Dict[str, Any]]):
        self.validator_registry = validator_registry
        self.validators = self._setup_validators(validator_configs)

    def _setup_validators(self, validator_configs: List[Dict[str, Any]]) -> List[BaseValidator]:
        """Set up validators from configuration."""
        validators = []
        if not validators:
            return validators
        for validator_config in validator_configs:
            validator_type = validator_config.get("type")
            strict = validator_config.get("strict", True)
            config_copy = validator_config.copy()
            config_copy.pop("type", None)
            config_copy.pop("strict", None)
            if validator_type in self.validator_registry:
                validator_class = self.validator_registry[validator_type]
                validators.append(validator_class(strict=strict, generate_hints=True, **config_copy))
            else:
                raise ValueError(f"Unknown validator type: {validator_type}")
        # Check for duplicate validator names
        names = [v.name for v in validators]
        duplicates = set([name for name in names if names.count(name) > 1])
        if duplicates:
            raise ValueError(f"Duplicate validator name(s) detected: {', '.join(duplicates)}")
        # Conflict detection: only one file type group can be present
        present_groups = []
        for group in CONFLICTING_VALIDATOR_GROUPS:
            if any(type(v) in group for v in validators):
                present_groups.append(group)
        if len(present_groups) > 1:
            # List the file types (by class names) that are conflicting
            group_names = [', '.join(sorted(cls.__name__ for cls in group)) for group in present_groups]
            raise ValueError(
                f"Conflicting file type validators detected: {group_names}. "
                "Only validators from one file type group can be used together."
            )

        return validators

    async def chain_validate(self, response: str) -> ValidationResult:
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
    
    @abstractmethod
    async def validate(self, manager: Manager, content: str, **kwargs) -> Any:
        """Validate content using the provided manager.
        
        Args:
            manager: The domain manager to use for processing
            content: The content to validate
            **kwargs: Domain-specific parameters
            
        Returns:
            Validated response from the domain
        """
        pass 