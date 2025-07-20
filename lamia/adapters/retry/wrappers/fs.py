"""Retry wrapper for filesystem adapters."""

from typing import Optional

from ...filesystem.base import BaseFSAdapter
from ..handler import RetryHandler
from ..config import ExternalSystemRetryConfig

class RetryWrappedFSAdapter(BaseFSAdapter):
    """Adds retry capabilities to filesystem adapters."""
    
    def __init__(
        self,
        adapter: BaseFSAdapter,
        retry_config: Optional[ExternalSystemRetryConfig] = None,
        collect_stats: bool = True
    ):
        """Initialize the retry wrapper.
        
        Args:
            adapter: The filesystem adapter to wrap
            retry_config: Optional retry configuration
            collect_stats: Whether to collect retry statistics
        """
        self._adapter = adapter
        self._retry_handler = RetryHandler(retry_config, collect_stats)
    
    async def read(self, path: str) -> bytes:
        """Read file with retry handling.
        
        Args:
            path: Path to the file to read
            
        Returns:
            File contents as bytes
        """
        return await self._retry_handler.execute(
            lambda: self._adapter.read(path)
        )
    
    async def write(self, path: str, data: bytes) -> None:
        """Write file with retry handling.
        
        Args:
            path: Path to write to
            data: Data to write
        """
        await self._retry_handler.execute(
            lambda: self._adapter.write(path, data)
        )
    
    def get_stats(self):
        """Get retry statistics if enabled."""
        return self._retry_handler.get_stats() 