from typing import List, Optional, Dict, Any, Type
from dataclasses import dataclass
import logging
import sys

from .base import BaseLLMAdapter, LLMResponse
from ...validation.base import BaseValidator, ValidationResult
from ...engine.interfaces import ValidationStrategy, Manager

class LLMValidationStrategy(ValidationStrategy):
    """Handles response validation logic."""
    
    def __init__(self, validator_registry: Dict[str, Type[BaseValidator]]):
        super().__init__(validator_registry)
        self._initialized = True
    
    async def validate(self, content: str) -> ValidationResult:
        """Validate LLM content using registered validators.
        
        Args:
            content: The content to validate
            
        Returns:
            ValidationResult with validation status and any error messages
        """
        return await self.chain_validate(content)

    def get_initial_hints(self) -> str:
        """Get combined initial hints from all validators."""
        hints = [v.initial_hint for v in self.validators if hasattr(v, 'initial_hint')]
        return "\n".join(hints) 