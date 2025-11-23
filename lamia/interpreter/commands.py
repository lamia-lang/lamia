"""Command objects for structured communication between parser, engine, and managers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, Union, List
from enum import Enum
from .command_types import CommandType


class WebActionType(Enum):
    """Types of web actions."""
    NAVIGATE = "navigate"
    HTTP_REQUEST = "http_request"
    CLICK = "click"
    TYPE = "type"
    WAIT = "wait"
    GET_TEXT = "get_text"
    GET_PAGE_SOURCE = "get_page_source"
    SCREENSHOT = "screenshot"
    HOVER = "hover"
    SCROLL = "scroll"
    SELECT = "select"
    SUBMIT = "submit"
    IS_VISIBLE = "is_visible"
    IS_ENABLED = "is_enabled"


class FileActionType(Enum):
    """Types of file actions."""
    READ = "read"
    WRITE = "write"
    APPEND = "append"
    DELETE = "delete"
    COPY = "copy"
    MOVE = "move"
    EXISTS = "exists"
    SIZE = "size"
    MKDIR = "mkdir"
    LIST_DIR = "list_dir"

class Command(ABC):
    """Base class for all command objects."""
    command_type: CommandType

    def __init__(self, command_type: CommandType):
        self.command_type = command_type


@dataclass
class LLMCommand(Command):
    """Command for LLM operations."""
    prompt: str
    
    def __post_init__(self):
        super().__init__(CommandType.LLM)


@dataclass
class WebCommand(Command):
    """Command for web operations (browser, HTTP, etc.)."""
    action: WebActionType
    url: Optional[str] = None
    method: Optional[str] = None  # GET, POST, PUT, DELETE, etc.
    headers: Optional[Dict[str, str]] = None
    data: Optional[Union[Dict[str, Any], str]] = None
    timeout: Optional[float] = None
    selector: Optional[str] = None  # For browser actions
    fallback_selectors: Optional[List[str]] = None
    value: Optional[str] = None  # For input actions
    
    def __post_init__(self):
        super().__init__(CommandType.WEB)
    
    def get_primary_content(self) -> str:
        if self.url:
            return self.url
        elif self.selector:
            return f"{self.action.value}({self.selector})"
        else:
            return f"{self.action.value}"


@dataclass  
class FileCommand(Command):
    """Command for file system operations."""
    action: FileActionType
    path: str
    content: Optional[str] = None
    destination: Optional[str] = None  # For copy/move operations
    encoding: str = "utf-8"
    create_dirs: bool = True
    pattern: Optional[str] = None  # For list operations
    
    def __post_init__(self):
        super().__init__(CommandType.FILESYSTEM)
