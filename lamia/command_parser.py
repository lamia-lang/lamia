"""
Command parser for Lamia operations.

This module handles parsing of command strings to determine the appropriate
domain type and extract arguments for execution.
"""

import re
from typing import Tuple, Dict, Any, Optional
from urllib.parse import urlparse
from lamia.command_types import CommandType


class CommandParser:
    """
    Parser for Lamia commands that determines domain type and extracts arguments.
    
    Parses a command string once and provides access to both the command type
    and parsed arguments through getter methods.
    """
    
    def __init__(self, command: str):
        """
        Initialize the parser with a command string.
        
        Args:
            command: The command string to parse
        """
        self.command = command.strip()
        self._command_type = None
        self._content = None
        self._kwargs = None
        self._parse()
    
    def _parse(self):
        """Parse the command to determine type and extract arguments."""
        # Determine command type
        self._command_type = self._determine_command_type()
        
        # Extract content and arguments based on type
        if self._command_type == CommandType.FILESYSTEM:
            try:
                self._content, self._kwargs = self._parse_fs_command()
            except ValueError:
                # If parsing fails, treat as LLM command
                self._command_type = CommandType.LLM
                self._content = self.command
                self._kwargs = {}
        elif self._command_type == CommandType.WEB:
            try:
                self._content, self._kwargs = self._parse_web_command()
            except ValueError:
                # If parsing fails, treat as LLM command
                self._command_type = CommandType.LLM
                self._content = self.command
                self._kwargs = {}
        else:
            # LLM commands - return the command as-is
            self._content = self.command
            self._kwargs = {}
    
    def _determine_command_type(self) -> CommandType:
        """Determine the domain type for the command."""
        # Filesystem commands
        if self._is_fs_command():
            return CommandType.FILESYSTEM
        
        # Web commands
        if self._is_web_command():
            return CommandType.WEB
        
        # Default to LLM for natural language queries
        return CommandType.LLM
    
    def _is_fs_command(self) -> bool:
        """Check if command is a filesystem operation."""
        fs_patterns = [
            r'^(read|write|list|copy|move|delete|mkdir|rmdir)\s+[/\\]',  # Must be followed by a path starting with / or \
            r'^(file|dir|directory)\s+[/\\]',  # Must be followed by a path starting with / or \
            r'^(ls|cat|cp|mv|rm|mkdir|rmdir)\s+[/\\]',  # Must be followed by a path starting with / or \
        ]
        
        return any(re.match(pattern, self.command, re.IGNORECASE) for pattern in fs_patterns)
    
    def _is_web_command(self) -> bool:
        """Check if command is a web operation."""
        # Check for URLs
        if self._looks_like_url(self.command):
            return True
        
        # Check for web-specific commands
        web_patterns = [
            r'^(get|post|fetch|download|screenshot|scrape)\s+',
            r'^(http|https)://',
            r'^www\.',
        ]
        
        return any(re.match(pattern, self.command, re.IGNORECASE) for pattern in web_patterns)
    
    def _looks_like_url(self, text: str) -> bool:
        """Check if text looks like a URL."""
        try:
            result = urlparse(text)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    def _parse_fs_command(self) -> Tuple[str, Dict[str, Any]]:
        """Parse filesystem command into operation and arguments."""
        parts = self.command.split()
        
        if len(parts) < 2:
            raise ValueError(f"Invalid filesystem command: {self.command}")
        
        operation = parts[0].lower()
        path = parts[1]
        
        kwargs = {}
        
        # Extract additional arguments
        for i in range(2, len(parts)):
            if parts[i].startswith('--'):
                # Handle flags like --recursive, --force, etc.
                flag = parts[i][2:]
                if i + 1 < len(parts) and not parts[i + 1].startswith('--'):
                    kwargs[flag] = parts[i + 1]
                else:
                    kwargs[flag] = True
        
        return path, {'operation': operation, **kwargs}
    
    def _parse_web_command(self) -> Tuple[str, Dict[str, Any]]:
        """Parse web command into URL and arguments."""
        parts = self.command.split()
        
        if self._looks_like_url(parts[0]):
            url = parts[0]
            operation = 'get'  # Default operation
        else:
            operation = parts[0].lower()
            if len(parts) < 2:
                raise ValueError(f"Invalid web command: {self.command}")
            url = parts[1]
        
        kwargs = {'operation': operation}
        
        # Extract additional arguments
        for i in range(2, len(parts)):
            if parts[i].startswith('--'):
                flag = parts[i][2:]
                if i + 1 < len(parts) and not parts[i + 1].startswith('--'):
                    kwargs[flag] = parts[i + 1]
                else:
                    kwargs[flag] = True
        
        return url, kwargs
    
    @property
    def command_type(self) -> CommandType:
        """Get the determined command type."""
        return self._command_type
    
    @property
    def content(self) -> str:
        """Get the parsed content (path, URL, or text)."""
        return self._content
    
    @property
    def kwargs(self) -> Dict[str, Any]:
        """Get the parsed keyword arguments."""
        return self._kwargs
    
    def get_args(self) -> Tuple[str, Dict[str, Any]]:
        """Get both content and kwargs as a tuple."""
        return self._content, self._kwargs


# Backward compatibility functions
def get_lamia_command_type(command: str) -> CommandType:
    """
    Determine the domain type for a given command.
    
    Args:
        command: The command string to analyze
        
    Returns:
        CommandType: Domain type (CommandType.LLM, CommandType.FILESYSTEM, CommandType.WEB, etc.)
        
    Raises:
        ValueError: If command type cannot be determined
    """
    parser = CommandParser(command)
    return parser.command_type


def get_command_args(command: str) -> Tuple[str, Dict[str, Any]]:
    """
    Extract the content and arguments from a command.
    
    Args:
        command: The command string to parse
        
    Returns:
        Tuple[str, Dict[str, Any]]: (content, kwargs)
        
    Raises:
        ValueError: If command cannot be parsed
    """
    parser = CommandParser(command)
    return parser.get_args() 