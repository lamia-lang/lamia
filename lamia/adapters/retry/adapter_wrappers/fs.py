"""Retry wrapper for filesystem adapters."""

from typing import Optional

from ...filesystem.base import BaseFSAdapter
from ..retry_handler import RetryHandler
from lamia.types import ExternalOperationRetryConfig

class RetryingFSAdapter(BaseFSAdapter):
    """Adds retry capabilities to filesystem adapters.
    
    Automatically configures retry settings optimized for filesystem
    operations with appropriate error classification (no rate limiting).
    """
    
    def __init__(
        self,
        adapter: BaseFSAdapter,
        retry_config: Optional[ExternalOperationRetryConfig] = None,
        collect_stats: bool = True
    ):
        """Initialize the retry wrapper.
        
        Args:
            adapter: The filesystem adapter to wrap
            retry_config: Optional retry configuration (uses FS defaults if None)
            collect_stats: Whether to collect retry statistics
        """
        self._adapter = adapter
        self._retry_handler = RetryHandler(
            adapter=adapter,  # Pass adapter for intelligent defaults
            config=retry_config,
            collect_stats=collect_stats
        )
    
    async def read(self, path: str) -> bytes:
        """Read file with retry handling.
        
        Uses filesystem-optimized retry logic:
        - 2 max attempts (most FS errors are permanent)
        - 0.5-5 second delays
        - No rate limit handling
        
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