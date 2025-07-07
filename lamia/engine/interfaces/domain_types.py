from enum import Enum

class DomainType(Enum):
    """Supported domain types."""
    LLM = "llm"
    FILESYSTEM = "fs" 
    WEB = "web" 