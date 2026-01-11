"""Base interface for filesystem adapters."""

from abc import ABC, abstractmethod
from typing import Union

class BaseFSAdapter(ABC):
    """Base interface for filesystem adapters.
    
    This defines the core filesystem operations without retry handling.
    Retry handling is provided through wrapper classes.
    """
    
    @abstractmethod
    async def read(self, path: str) -> bytes:
        """Read file contents.
        
        Args:
            path: Path to the file to read
            
        Returns:
            File contents as bytes
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            PermissionError: If access is denied
            IOError: For other IO-related errors
        """
        pass
    
    @abstractmethod
    async def write(self, path: str, data: Union[str, bytes]) -> None:
        """Write data to a file.
        
        Args:
            path: Path to write to
            data: Data to write (string or bytes)
            
        Raises:
            PermissionError: If access is denied
            IOError: For other IO-related errors
        """
        pass
    
    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if a path exists.
        
        Args:
            path: Path to check
            
        Returns:
            True if the path exists, False otherwise
        """
        pass
    
    @abstractmethod
    async def delete(self, path: str) -> None:
        """Delete a file.
        
        Args:
            path: Path to delete
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            PermissionError: If access is denied
            IOError: For other IO-related errors
        """
        pass 