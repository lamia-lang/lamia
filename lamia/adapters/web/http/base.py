from abc import ABC, abstractmethod
from typing import Any
from lamia.types import HttpActionParams


class BaseHttpAdapter(ABC):
    """Abstract base class for HTTP client adapters."""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the HTTP adapter."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the HTTP adapter and cleanup resources."""
        pass
    
    @abstractmethod
    async def get(self, params: HttpActionParams) -> Any:
        """Send GET request."""
        pass
    
    @abstractmethod
    async def post(self, params: HttpActionParams) -> Any:
        """Send POST request."""
        pass
    
    @abstractmethod
    async def put(self, params: HttpActionParams) -> Any:
        """Send PUT request."""
        pass
    
    @abstractmethod
    async def patch(self, params: HttpActionParams) -> Any:
        """Send PATCH request."""
        pass
    
    @abstractmethod
    async def delete(self, params: HttpActionParams) -> Any:
        """Send DELETE request."""
        pass
    
    @abstractmethod
    async def head(self, params: HttpActionParams) -> Any:
        """Send HEAD request."""
        pass
    
    @abstractmethod
    async def options(self, params: HttpActionParams) -> Any:
        """Send OPTIONS request."""
        pass