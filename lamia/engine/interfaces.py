from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from enum import Enum

class DomainType(Enum):
    """Supported domain types."""
    LLM = "llm"
    FILESYSTEM = "fs" 
    WEB = "web"

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

class ValidationStrategy(ABC):
    """Abstract base class for domain-specific validation strategies."""
    
    @property
    @abstractmethod
    def domain_type(self) -> DomainType:
        """Return the domain type this strategy validates."""
        pass
    
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