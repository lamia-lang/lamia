"""
Shared command type constants to ensure consistency between parser and engine.
"""

from enum import Enum

class CommandType(Enum):
    LLM = "llm"
    FILESYSTEM = "fs"
    WEB = "web"