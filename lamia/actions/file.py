"""File system operations with excellent IntelliSense support."""

from typing import Optional, Union
import json


class FileActions:
    """File system operations with excellent IntelliSense support.
    
    Access via: file.read(), file.write(), file.append(), etc.
    """
    
    def read(self, path: str, encoding: str = "utf-8") -> str:
        """Read file contents.
        
        Args:
            path: File path to read
            encoding: File encoding (default: utf-8)
            
        Returns:
            Command string for lamia.run() to execute
            
        Example:
            content = file.read("/path/to/file.txt")
            data = file.read("config.json")
        """
        cmd_parts = [f"file://read:{path}"]
        if encoding != "utf-8":
            cmd_parts.append(f"encoding:{encoding}")
        return " ".join(cmd_parts)
    
    def write(self, path: str, content: str, encoding: str = "utf-8", create_dirs: bool = True) -> str:
        """Write content to file (creates new or overwrites existing).
        
        Args:
            path: File path to write
            content: Content to write
            encoding: File encoding (default: utf-8)
            create_dirs: Create parent directories if needed (default: True)
            
        Returns:
            Command string for lamia.run() to execute
            
        Example:
            file.write("/path/to/file.txt", "Hello, World!")
            file.write("output.json", json.dumps(data))
        """
        cmd_parts = [f"file://write:{path}"]
        cmd_parts.append(f"content:{json.dumps(content)}")
        if encoding != "utf-8":
            cmd_parts.append(f"encoding:{encoding}")
        if not create_dirs:
            cmd_parts.append("create_dirs:false")
        return " ".join(cmd_parts)
    
    def append(self, path: str, content: str, encoding: str = "utf-8", create_dirs: bool = True) -> str:
        """Append content to file.
        
        Args:
            path: File path to append to
            content: Content to append
            encoding: File encoding (default: utf-8)
            create_dirs: Create parent directories if needed (default: True)
            
        Returns:
            Command string for lamia.run() to execute
            
        Example:
            file.append("/var/log/app.log", "New log entry\\n")
            file.append("notes.txt", "Additional note")
        """
        cmd_parts = [f"file://append:{path}"]
        cmd_parts.append(f"content:{json.dumps(content)}")
        if encoding != "utf-8":
            cmd_parts.append(f"encoding:{encoding}")
        if not create_dirs:
            cmd_parts.append("create_dirs:false")
        return " ".join(cmd_parts)
    
    def delete(self, path: str) -> str:
        """Delete a file.
        
        Args:
            path: File path to delete
            
        Returns:
            Command string for lamia.run() to execute
            
        Example:
            file.delete("/tmp/temp_file.txt")
            file.delete("old_backup.zip")
        """
        return f"file://delete:{path}"
    
    def exists(self, path: str) -> str:
        """Check if file exists.
        
        Args:
            path: File path to check
            
        Returns:
            Command string for lamia.run() to execute
            
        Example:
            exists = file.exists("/path/to/file.txt")
        """
        return f"file://exists:{path}"
    
    def copy(self, source: str, destination: str, create_dirs: bool = True) -> str:
        """Copy file from source to destination.
        
        Args:
            source: Source file path
            destination: Destination file path
            create_dirs: Create parent directories if needed (default: True)
            
        Returns:
            Command string for lamia.run() to execute
            
        Example:
            file.copy("/source/file.txt", "/backup/file.txt")
        """
        cmd_parts = [f"file://copy:{source}:{destination}"]
        if not create_dirs:
            cmd_parts.append("create_dirs:false")
        return " ".join(cmd_parts)
    
    def move(self, source: str, destination: str, create_dirs: bool = True) -> str:
        """Move file from source to destination.
        
        Args:
            source: Source file path
            destination: Destination file path
            create_dirs: Create parent directories if needed (default: True)
            
        Returns:
            Command string for lamia.run() to execute
            
        Example:
            file.move("/temp/file.txt", "/final/file.txt")
        """
        cmd_parts = [f"file://move:{source}:{destination}"]
        if not create_dirs:
            cmd_parts.append("create_dirs:false")
        return " ".join(cmd_parts)
    
    def size(self, path: str) -> str:
        """Get file size in bytes.
        
        Args:
            path: File path to check
            
        Returns:
            Command string for lamia.run() to execute
            
        Example:
            size = file.size("/path/to/file.txt")
        """
        return f"file://size:{path}"
    
    def mkdir(self, path: str, parents: bool = True) -> str:
        """Create directory.
        
        Args:
            path: Directory path to create
            parents: Create parent directories if needed (default: True)
            
        Returns:
            Command string for lamia.run() to execute
            
        Example:
            file.mkdir("/path/to/new/directory")
        """
        cmd_parts = [f"file://mkdir:{path}"]
        if not parents:
            cmd_parts.append("parents:false")
        return " ".join(cmd_parts)
    
    def list_dir(self, path: str = ".", pattern: Optional[str] = None) -> str:
        """List directory contents.
        
        Args:
            path: Directory path to list (default: current directory)
            pattern: Optional glob pattern to filter files
            
        Returns:
            Command string for lamia.run() to execute
            
        Example:
            files = file.list_dir("/path/to/directory")
            py_files = file.list_dir(".", "*.py")
        """
        cmd_parts = [f"file://list:{path}"]
        if pattern:
            cmd_parts.append(f"pattern:{pattern}")
        return " ".join(cmd_parts)


# Create singleton instance for import
file = FileActions()