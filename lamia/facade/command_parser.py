"""
Command parser for Lamia operations.

This module handles parsing of command strings to determine the appropriate
domain type and extract arguments for execution.
"""

from typing import Optional, Tuple, Any
from lamia.interpreter.command_types import CommandType
from lamia.interpreter.commands import Command, LLMCommand, WebCommand, FileCommand, WebActionType, FileActionType
from lamia.validation.base import BaseValidator

class CommandParser:
    def __init__(self, command: str):
        self.command = command
        self._parsed_command: Optional[Command] = None
        self._return_type = None
        
        # Parse the command
        self._parse()

    @property
    def parsed_command(self) -> Command:
        if self._parsed_command is None:
            raise RuntimeError("CommandParser._parse() did not set parsed_command")
        return self._parsed_command

    @property
    def return_type(self) -> Optional[str]:
        return self._return_type

    def _parse(self):
        content, self._return_type = self._split_command_and_return_type()
        command_type = self._determine_command_type()
        
        # Create appropriate Command object based on type
        if command_type == CommandType.FILESYSTEM:
            try:
                self._parsed_command = self._parse_file_command(content)
            except ValueError:
                # Fall back to LLM if parsing fails
                self._parsed_command = LLMCommand(content)
        elif command_type == CommandType.WEB:
            try:
                self._parsed_command = self._parse_web_command(content)
            except ValueError:
                # Fall back to LLM if parsing fails
                self._parsed_command = LLMCommand(content)
        else:
            # Default to LLM command
            self._parsed_command = LLMCommand(content)

    def _determine_command_type(self) -> CommandType:
        """Determine the type of command based on its format.

        Only explicit protocol prefixes trigger non-LLM routing:
        - http:// / https:// → WEB (navigate to URL)
        - file://             → FILESYSTEM (read a file)

        Everything else is an LLM prompt.  File writes are always produced
        by the `-> File(...)` transformer, never by this string parser.
        """
        stripped = self.command.strip()
        if stripped.startswith(("http://", "https://")):
            return CommandType.WEB
        if stripped.startswith("file://"):
            return CommandType.FILESYSTEM
        return CommandType.LLM

    def _split_command_and_return_type(self) -> Tuple[str, Any]:
        command_parts = self.command.split("->")
        if len(command_parts) == 2:
            return command_parts[0], command_parts[1]
        else:
            return self.command, None

    def _parse_file_command(self, command: str) -> FileCommand:
        """Parse filesystem command into FileCommand object.

        Plain paths default to READ. File writes are driven by the
        hybrid syntax `-> File(...)` (not by protocol strings).
        """
        return FileCommand(action=FileActionType.READ, path=command)
    
    def _parse_web_command(self, command) -> WebCommand:
        """Parse web command into WebCommand object."""
        # For URLs, default to NAVIGATE action
        return WebCommand(
            action=WebActionType.NAVIGATE,
            url=command,
        )