from abc import ABC, abstractmethod
from typing import Any
from .domain_types import DomainType

class Manager(ABC):
    """Abstract base class for all domain managers."""
    
    @property
    @abstractmethod
    def domain_type(self) -> DomainType:
        """Return the domain type this manager handles."""
        pass
    
    @abstractmethod
    async def execute(self, content: str, **kwargs) -> Any:
        """Execute a request in this domain.
        
        Args:
            content: The content to process
            **kwargs: Domain-specific parameters
            
        Returns:
            Domain-specific response
        """
        pass
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the manager."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close and cleanup manager resources."""
        pass 