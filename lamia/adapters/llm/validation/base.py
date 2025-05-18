from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass

@dataclass
class ValidationResult:
    """Result of a validation check."""
    is_valid: bool
    error_message: Optional[str] = None
    validation_data: Optional[Dict[str, Any]] = None

class BaseValidator(ABC):
    """Base class for response validators."""
    
    @abstractmethod
    async def validate(self, response: str, **kwargs) -> ValidationResult:
        """Validate the response against specific criteria.
        
        Args:
            response: The text response from the model
            **kwargs: Additional validation parameters
            
        Returns:
            ValidationResult indicating if the response is valid
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the validator for configuration."""
        pass 