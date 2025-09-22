from typing import TypeVar, Generic, Optional, Union, List
from datetime import timedelta
from pydantic import BaseModel
from dataclasses import dataclass
from enum import Enum
from typing import Any

T = TypeVar('T', bound=BaseModel)
S = TypeVar('S', bound=bool)

@dataclass
class ExternalOperationRetryConfig:
    """Configuration for external system retry behavior."""
    max_attempts: int
    base_delay: float
    max_delay: float
    exponential_base: float
    max_total_duration: Optional[timedelta]

class BaseType(Generic[T, S]):
    """Base marker class for all validation types."""
    
    def __class_getitem__(cls, params):
        # Allow single parameter usage like HTML[MyModel]
        if not isinstance(params, tuple):
            params = (params, False)  # Default S to False (non-strict validation)
        return super().__class_getitem__(params)

class HTML(BaseType[T, S]):
    """Marker class for HTML validation types."""
    pass

class YAML(BaseType[T, S]):
    """Marker class for YAML validation types."""
    pass

class JSON(BaseType[T, S]):
    """Marker class for JSON validation types."""
    pass

class XML(BaseType[T, S]):
    """Marker class for XML validation types."""
    pass

class CSV(BaseType[T, S]):
    """Marker class for CSV validation types."""
    pass

class Markdown(BaseType[T, S]):
    """Marker class for Markdown validation types."""
    pass


class BrowserActionType(str, Enum):
    """Types of browser actions that can be performed."""
    CLICK = "click"
    TYPE = "type"
    WAIT = "wait"
    NAVIGATE = "navigate"
    SCROLL = "scroll"
    HOVER = "hover"
    SELECT = "select"
    SUBMIT = "submit"
    SCREENSHOT = "screenshot"
    GET_TEXT = "get_text"
    GET_ATTRIBUTE = "get_attribute"
    IS_VISIBLE = "is_visible"
    IS_ENABLED = "is_enabled"


class HttpActionType(str, Enum):
    """Types of HTTP actions that can be performed."""
    GET = "get"
    POST = "post"
    PUT = "put"
    PATCH = "patch"
    DELETE = "delete"
    HEAD = "head"
    OPTIONS = "options"


class SelectorType(str, Enum):
    """Types of selectors for web elements."""
    CSS = "css"
    XPATH = "xpath"
    ID = "id"
    NAME = "name"
    CLASS_NAME = "class_name"
    TAG_NAME = "tag_name"
    LINK_TEXT = "link_text"
    PARTIAL_LINK_TEXT = "partial_link_text"
    AI_DESCRIPTION = "ai_description"  # For AI-powered element selection


class BrowserActionParams(BaseModel):
    """Parameters for browser actions."""
    selector: Optional[str] = None
    selector_type: SelectorType = SelectorType.CSS
    fallback_selectors: Optional[List[str]] = None
    value: Optional[str] = None  # For typing, selecting options, URLs, file paths
    timeout: Optional[float] = None
    wait_condition: Optional[str] = None
    description: Optional[str] = None  # For AI-powered actions
    
    class Config:
        use_enum_values = True


class HttpActionParams(BaseModel):
    """Parameters for HTTP actions."""
    url: str
    headers: Optional[dict] = None
    data: Optional[Any] = None  # Can be dict (JSON) or str (form-encoded)
    params: Optional[dict] = None  # Query parameters
    
    class Config:
        use_enum_values = True


class BrowserAction(BaseModel):
    """Browser automation command for Selenium, Playwright, and AI tools."""
    action: BrowserActionType
    params: BrowserActionParams
    
    class Config:
        use_enum_values = True


class HttpAction(BaseModel):
    """HTTP request command for REST APIs and web services."""
    action: HttpActionType
    params: HttpActionParams
    
    class Config:
        use_enum_values = True