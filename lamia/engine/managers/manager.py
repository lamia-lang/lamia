from abc import ABC, abstractmethod
from typing import Any

class Manager(ABC):
    """Abstract base class for all domain managers."""
    
    @abstractmethod
    async def execute(self, content: str) -> Any:
        """Execute a request in this domain.
        
        Args:
            content: The content to process
            
        Returns:
            Domain-specific response
        """
        pass