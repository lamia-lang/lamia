from abc import ABC, abstractmethod
from typing import Any, List, Dict, Type
from ..managers.manager import Manager
from lamia.validation.base import BaseValidator, ValidationResult
from lamia.validation.validators import CONFLICTING_VALIDATOR_GROUPS
from lamia.validation.validator_registry import ValidatorRegistry
import logging

logger = logging.getLogger(__name__)

class ValidationStrategy(ABC):
    """Abstract base class for domain-specific validation strategies."""

    def __init__(self, validator_types: List[Type[BaseValidator]]):
        """Initialize with pre-configured validator instances from registry."""
        self._check_validator_conflicts(validator_types)
        self.validators = [validator_type() for validator_type in validator_types]

    def _check_validator_conflicts(self, validator_types: List[Type[BaseValidator]]) -> List[Type[BaseValidator]]:
        """Check for conflicts between validators."""
        if not validator_types:
            return

        # Check for duplicate validator names
        names = [v.name for v in validator_types]
        duplicates = set([name for name in names if names.count(name) > 1])
        if duplicates:
            raise ValueError(f"Duplicate validator name(s) detected: {', '.join(duplicates)}")

        # Conflict detection: only one file type group can be present
        present_groups = []
        for group in CONFLICTING_VALIDATOR_GROUPS:
            if any(validator_type in group for validator_type in validator_types):
                present_groups.append(group)
        if len(present_groups) > 1:
            # List the file types (by class names) that are conflicting
            group_names = [', '.join(sorted(cls.__name__ for cls in group)) for group in present_groups]
            raise ValueError(
                f"Conflicting file type validators detected: {group_names}. "
                "Only validators from one file type group can be used together."
            )

    async def _chain_validate(self, response: str) -> ValidationResult:
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
    
    async def validate(self, content: str, **kwargs) -> ValidationResult:
        """Validate content using the provided manager.
        
        Args:
            manager: The domain manager to use for processing
            content: The content to validate
            **kwargs: Domain-specific parameters
            
        Returns:
            Validated response from the domain
        """
        return await self._chain_validate(content)