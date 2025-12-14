"""Internal types used by Lamia engine - not part of public API."""

from typing import Optional, List, Set, Any
from pydantic import BaseModel
from enum import Enum


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
    GET_PAGE_SOURCE = "get_page_source"
    GET_ATTRIBUTE = "get_attribute"
    GET_ELEMENTS = "get_elements"  # Get multiple elements for iteration/scoping
    GET_INPUT_TYPE = "get_input_type"  # Detect input element type (text, file, checkbox, etc.)
    GET_OPTIONS = "get_options"  # Get selectable options from radio/checkbox/select
    IS_VISIBLE = "is_visible"
    IS_ENABLED = "is_enabled"
    IS_CHECKED = "is_checked"  # Check if checkbox/radio is checked
    UPLOAD_FILE = "upload_file"


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
    scope_element_handle: Optional[Any] = None  # Selenium WebElement or Playwright ElementHandle to scope within
    
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


# Actions that use selectors and support fallback chains
SELECTOR_BASED_ACTIONS: Set[BrowserActionType] = {
    BrowserActionType.CLICK,
    BrowserActionType.TYPE,
    BrowserActionType.WAIT,
    BrowserActionType.GET_TEXT,
    BrowserActionType.HOVER,
    BrowserActionType.SELECT,
    BrowserActionType.IS_VISIBLE,
    BrowserActionType.IS_ENABLED,
    BrowserActionType.UPLOAD_FILE,
}

# Map method names to action types
WEB_METHOD_TO_ACTION = {
    'click': BrowserActionType.CLICK,
    'type_text': BrowserActionType.TYPE,
    'wait_for': BrowserActionType.WAIT,
    'get_text': BrowserActionType.GET_TEXT,
    'get_elements': BrowserActionType.GET_ELEMENTS,
    'get_input_type': BrowserActionType.GET_INPUT_TYPE,
    'get_options': BrowserActionType.GET_OPTIONS,
    'is_checked': BrowserActionType.IS_CHECKED,
    'hover': BrowserActionType.HOVER,
    'scroll_to': BrowserActionType.SCROLL,
    'select_option': BrowserActionType.SELECT,
    'submit_form': BrowserActionType.SUBMIT,
    'screenshot': BrowserActionType.SCREENSHOT,
    'is_visible': BrowserActionType.IS_VISIBLE,
    'is_enabled': BrowserActionType.IS_ENABLED,
    'upload_file': BrowserActionType.UPLOAD_FILE
}

