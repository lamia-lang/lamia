"""
Command parser for Lamia operations.

This module handles parsing of command strings to determine the appropriate
domain type and extract arguments for execution.
"""

import re
from typing import Tuple, Dict, Any, Optional
from urllib.parse import urlparse
from .command_types import CommandType
from lamia.validation.base import BaseValidator

class CommandParser:
    def __init__(self, command: str):
        self.command = command
        self._command_type = None
        self._content = None
        self._return_type = None
        self._kwargs = {}
        
        # Parse the command
        self._parse()

    @property
    def command_type(self) -> CommandType:
        return self._command_type

    @property
    def content(self) -> str:
        return self._content

    @property
    def return_type(self) -> Any:
        return self._return_type

    @property
    def kwargs(self) -> Dict[str, Any]:
        return self._kwargs

    def _parse(self):
        # Determine command type
        self._command_type = self._determine_command_type()
        content, self._return_type = self._split_command_and_return_type()
        
        # Extract content and arguments based on type
        if self._command_type == CommandType.FILESYSTEM:
            try:
                self._content, self._kwargs = self._parse_fs_command(content)
            except ValueError:
                self._command_type = CommandType.LLM
        elif self._command_type == CommandType.WEB:
            try:
                self._content, self._kwargs = self._parse_web_command(content)
            except ValueError:
                self._command_type = CommandType.LLM
        
        if self._command_type == CommandType.LLM:
            self._content, self._kwargs = self._parse_llm_command(content)

    def _determine_command_type(self) -> CommandType:
        """Determine the type of command based on its format."""
        if self.command.startswith("http://") or self.command.startswith("https://"):
            return CommandType.WEB
        elif self.command.startswith("file://") or "/" in self.command:
            return CommandType.FILESYSTEM
        else:
            return CommandType.LLM

    def _split_command_and_return_type(self) -> Tuple[str, Any]:
        command_parts = self.command.split("->")
        if len(command_parts) == 2:
            return command_parts[0], command_parts[1]
        else:
            return self.command, None

    def _parse_fs_command(self, command) -> Tuple[str, Dict[str, Any]]:
        """Parse filesystem command into operation and arguments."""
        return command, {}
    
    def _parse_web_command(self, command) -> Tuple[str, Dict[str, Any]]:
        """Parse web command into URL and arguments."""
        return command, {}
    
    def _parse_llm_command(self, command) -> Tuple[str, Dict[str, Any]]:
        """Parse LLM command into operation and arguments."""
        return command, {}