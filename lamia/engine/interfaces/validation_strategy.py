from abc import ABC, abstractmethod
from typing import Any
from .manager import Manager

class ValidationStrategy(ABC):
    """Abstract base class for domain-specific validation strategies."""
    
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