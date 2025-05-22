from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass

@dataclass
class ValidationResult:
    """Result of a validation check.
    
    Attributes:
        is_valid: Whether the response is valid.
        error_message: Error message if invalid.
        hint: Optional hint for fixing the response.
        validated_text: Sanitized/validated part of the response (if available).
    """
    is_valid: bool
    error_message: Optional[str] = None
    hint: Optional[str] = None
    validated_text: Optional[str] = None

class BaseValidator(ABC):
    """Base class for response validators.
    
    Subclasses should implement both validate_strict (forgiving) and validate_restrictive (strict) methods.
    The __call__ method dispatches to the correct method based on the strict flag.
    """
    def __init__(self, strict: bool = True):
        self.strict = strict

    async def validate(self, response: str, **kwargs) -> ValidationResult:
        if self.strict:
            return await self.validate_strict(response, **kwargs)
        else:
            return await self.validate_restrictive(response, **kwargs)

    @abstractmethod
    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        """Strict validation (default mode)."""
        pass

    @abstractmethod
    async def validate_restrictive(self, response: str, **kwargs) -> ValidationResult:
        """Forgiving (non-strict) validation mode."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the validator for configuration."""
        pass

    @property
    @abstractmethod
    def initial_hint(self) -> str:
        """Initial hint for the LLM prompt, to be aggregated if multiple validators are used."""
        pass 