"""Base adapter class that all Lamia adapters inherit from."""

from abc import ABC
from typing import TypeVar, Generic, Optional, Callable, Awaitable
from .infrastructure import InfrastructureLayer, RetryConfig

T = TypeVar('T')  # Return type for operations
ConfigType = TypeVar('ConfigType')  # Type for adapter-specific configs

class BaseAdapter(ABC, Generic[T, ConfigType]):
    """Base class for all Lamia adapters."""
    
    def __init__(
        self,
        config: Optional[ConfigType] = None,
        retry_config: Optional[RetryConfig] = None
    ):
        self.config = config
        self.infrastructure = InfrastructureLayer[T](
            adapter=self,
            retry_config=retry_config
        )

    async def execute_operation(
        self,
        operation: Callable[[], Awaitable[T]]
    ) -> T:
        """Execute an operation with retry handling."""
        return await self.infrastructure.execute_with_retry(operation) 