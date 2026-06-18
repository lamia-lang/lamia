"""
Command parser for Lamia operations.

This module handles parsing of command strings to determine the appropriate
domain type and extract arguments for execution.
"""

import json
import re
from typing import Optional, Tuple, Any
from lamia.interpreter.command_types import CommandType
from lamia.interpreter.commands import Command, LLMCommand, WebCommand, FileCommand, WebActionType, FileActionType
from lamia.validation.base import BaseValidator

_FILE_PROTOCOL_RE = re.compile(r'^file://(read|write|append|exists|glob):(.+)')
_FILE_KV_RE = re.compile(r'(encoding|content):(.+)')

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

        Handles the file:// protocol format produced by FileActions:
            file://read:path [encoding:enc]
            file://write:path content:"..." [encoding:enc]
            file://append:path content:"..." [encoding:enc]
            file://exists:path
            file://glob:pattern
        """
        stripped = command.strip()
        m = _FILE_PROTOCOL_RE.match(stripped)
        if not m:
            return FileCommand(action=FileActionType.READ, path=stripped)

        action_str = m.group(1)
        remainder = m.group(2)

        action_map = {
            'read': FileActionType.READ,
            'write': FileActionType.WRITE,
            'append': FileActionType.APPEND,
            'exists': FileActionType.EXISTS,
            'glob': FileActionType.GLOB,
        }
        action = action_map[action_str]

        parts = remainder.split(' ')
        path = parts[0]
        encoding = 'utf-8'
        content: Optional[str] = None

        for part in parts[1:]:
            if part.startswith('encoding:'):
                encoding = part[len('encoding:'):]
            elif part.startswith('content:'):
                raw = remainder[remainder.index('content:') + len('content:'):]
                if raw.startswith('"') or raw.startswith("'"):
                    try:
                        content = json.loads(raw.split(' encoding:')[0])
                    except (json.JSONDecodeError, ValueError):
                        content = raw
                else:
                    content = raw
                break

        return FileCommand(action=action, path=path, content=content, encoding=encoding)
    
    def _parse_web_command(self, command) -> WebCommand:
        """Parse web command into WebCommand object."""
        # For URLs, default to NAVIGATE action
        return WebCommand(
            action=WebActionType.NAVIGATE,
            url=command,
        )