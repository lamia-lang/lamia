"""Local filesystem adapter implementation."""

import os
import asyncio
from pathlib import Path
from typing import Union
from .base import BaseFSAdapter


class LocalFSAdapter(BaseFSAdapter):
    """Local filesystem adapter using async file operations.
    
    This adapter provides async file operations for local filesystem access
    using asyncio for non-blocking I/O.
    """
    
    def __init__(self, base_path: Union[str, None] = None):
        """Initialize the local filesystem adapter.
        
        Args:
            base_path: Optional base path to restrict operations to a specific directory.
                      If provided, all paths will be relative to this directory.
        """
        self.base_path = Path(base_path) if base_path else None
        
    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to base_path if set.
        
        Args:
            path: The file path to resolve
            
        Returns:
            Resolved Path object
            
        Raises:
            ValueError: If path tries to escape base_path when base_path is set
        """
        target_path = Path(path)
        
        if self.base_path:
            # Ensure path doesn't escape base directory
            if target_path.is_absolute():
                # Convert absolute path to relative
                try:
                    target_path = target_path.relative_to(self.base_path)
                except ValueError:
                    raise ValueError(f"Path {path} is outside base directory {self.base_path}")
            
            # Join with base path
            resolved_path = self.base_path / target_path
            
            # Additional security check - ensure resolved path is still under base_path
            try:
                resolved_path.resolve().relative_to(self.base_path.resolve())
            except ValueError:
                raise ValueError(f"Path {path} escapes base directory {self.base_path}")
                
            return resolved_path
        else:
            return target_path
    
    async def read(self, path: str) -> bytes:
        """Read file contents from local filesystem.
        
        Args:
            path: Path to the file to read
            
        Returns:
            File contents as bytes
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            PermissionError: If access is denied
            IOError: For other IO-related errors
        """
        resolved_path = self._resolve_path(path)
        
        def _read_file():
            with open(resolved_path, 'rb') as f:
                return f.read()
        
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _read_file)
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {path}")
        except PermissionError:
            raise PermissionError(f"Permission denied reading file: {path}")
        except Exception as e:
            raise IOError(f"Error reading file {path}: {e}")
    
    async def write(self, path: str, data: Union[str, bytes]) -> None:
        """Write data to a file in local filesystem.
        
        Args:
            path: Path to write to
            data: Data to write (string or bytes)
            
        Raises:
            PermissionError: If access is denied
            IOError: For other IO-related errors
        """
        resolved_path = self._resolve_path(path)
        
        # Create parent directories if they don't exist
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        
        def _write_file():
            if isinstance(data, str):
                with open(resolved_path, 'w', encoding='utf-8') as f:
                    f.write(data)
            else:
                with open(resolved_path, 'wb') as f:
                    f.write(data)
        
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _write_file)
        except PermissionError:
            raise PermissionError(f"Permission denied writing to file: {path}")
        except Exception as e:
            raise IOError(f"Error writing to file {path}: {e}")
    
    async def exists(self, path: str) -> bool:
        """Check if a path exists in local filesystem.
        
        Args:
            path: Path to check
            
        Returns:
            True if the path exists, False otherwise
        """
        try:
            resolved_path = self._resolve_path(path)
            return resolved_path.exists()
        except ValueError:
            # Path is invalid/escapes base directory
            return False
        except Exception:
            # Other errors (permissions, etc.) - assume doesn't exist
            return False
    
    async def delete(self, path: str) -> None:
        """Delete a file from local filesystem.
        
        Args:
            path: Path to delete
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            PermissionError: If access is denied
            IOError: For other IO-related errors
        """
        resolved_path = self._resolve_path(path)
        
        try:
            if not resolved_path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            
            if resolved_path.is_dir():
                raise IOError(f"Path is a directory, not a file: {path}")
                
            resolved_path.unlink()
            
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {path}")
        except PermissionError:
            raise PermissionError(f"Permission denied deleting file: {path}")
        except Exception as e:
            raise IOError(f"Error deleting file {path}: {e}")
    
    # Additional convenience methods
    
    async def list_files(self, directory: str = ".") -> list:
        """List files in a directory.
        
        Args:
            directory: Directory path to list (default: current directory)
            
        Returns:
            List of file paths in the directory
            
        Raises:
            FileNotFoundError: If directory doesn't exist
            PermissionError: If access is denied
            IOError: For other IO-related errors
        """
        resolved_path = self._resolve_path(directory)
        
        try:
            if not resolved_path.exists():
                raise FileNotFoundError(f"Directory not found: {directory}")
            
            if not resolved_path.is_dir():
                raise IOError(f"Path is not a directory: {directory}")
            
            files = []
            for item in resolved_path.iterdir():
                if item.is_file():
                    # Return path relative to base_path if set
                    if self.base_path:
                        try:
                            rel_path = item.relative_to(self.base_path)
                            files.append(str(rel_path))
                        except ValueError:
                            continue
                    else:
                        files.append(str(item))
            
            return sorted(files)
            
        except PermissionError:
            raise PermissionError(f"Permission denied listing directory: {directory}")
        except Exception as e:
            raise IOError(f"Error listing directory {directory}: {e}")
    
    async def get_size(self, path: str) -> int:
        """Get file size in bytes.
        
        Args:
            path: Path to the file
            
        Returns:
            File size in bytes
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            PermissionError: If access is denied
            IOError: For other IO-related errors
        """
        resolved_path = self._resolve_path(path)
        
        try:
            if not resolved_path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            
            return resolved_path.stat().st_size
            
        except PermissionError:
            raise PermissionError(f"Permission denied accessing file: {path}")
        except Exception as e:
            raise IOError(f"Error getting file size {path}: {e}")