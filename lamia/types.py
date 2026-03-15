"""Public API types for Lamia users."""

from typing import TypeVar, Generic, Optional
from datetime import timedelta
from pydantic import BaseModel
from dataclasses import dataclass
from enum import Enum

T = TypeVar('T', bound=BaseModel)
S = TypeVar('S', bound=bool)


class InputType(str, Enum):
    """HTML input element types for form automation.
    
    Use with web.get_input_type() to determine how to interact with form fields.
    
    Example:
        field = web.get_element("div.form-field")
        input_type = field.get_input_type()
        
        if input_type == InputType.TEXT:
            field.type_text("input", "answer")
        elif input_type == InputType.FILE:
            field.upload_file("input", "~/file.pdf")
    """
    # Text-based inputs (use type_text)
    TEXT = "text"
    EMAIL = "email"
    TEL = "tel"
    NUMBER = "number"
    PASSWORD = "password"
    TEXTAREA = "textarea"
    URL = "url"
    SEARCH = "search"
    
    # Date/Time inputs (use type_text with formatted string)
    DATE = "date"
    TIME = "time"
    DATETIME_LOCAL = "datetime-local"
    MONTH = "month"
    WEEK = "week"
    
    # Special inputs
    FILE = "file"          # Use upload_file()
    CHECKBOX = "checkbox"  # Use click() + is_checked()
    RADIO = "radio"        # Use click()
    COLOR = "color"        # Use type_text() with hex color
    RANGE = "range"        # Use type_text() with number
    
    # Selection
    SELECT = "select"      # Use select_option()
    
    # Buttons
    BUTTON = "button"      # Use click()
    SUBMIT = "submit"      # Use click()
    RESET = "reset"        # Use click()
    
    # Special
    HIDDEN = "hidden"      # Usually not interacted with
    UNKNOWN = "unknown"    # Unrecognized type


@dataclass
class ExternalOperationRetryConfig:
    """Configuration for external system retry behavior.
    
    Users can configure this in their config.yaml to control
    retry behavior for external operations (LLM, browser, etc.).
    """
    max_attempts: int
    base_delay: float
    max_delay: float
    exponential_base: float
    max_total_duration: Optional[timedelta]


class BaseType(Generic[T, S]):
    """Base marker class for all validation types.
    
    Used internally to support parametric types like HTML[Model].
    Users typically use the concrete types (HTML, JSON, etc.) directly.
    """
    
    def __class_getitem__(cls, params):
        # Allow single parameter usage like HTML[MyModel]
        if not isinstance(params, tuple):
            params = (params, False)  # Default S to False (non-strict validation)
        return super().__class_getitem__(params)


class HTML(BaseType[T, S]):
    """Marker class for HTML validation types.
    
    Use in function return annotations to validate HTML content:
    
    Example:
        def get_page() -> HTML:
            return "https://example.com"
        
        def get_structured_page() -> HTML[MyModel]:
            return "https://example.com"
    """
    pass


class YAML(BaseType[T, S]):
    """Marker class for YAML validation types.
    
    Use in function return annotations to validate YAML content.
    """
    pass


class JSON(BaseType[T, S]):
    """Marker class for JSON validation types.
    
    Use in function return annotations to validate JSON content.
    """
    pass


class XML(BaseType[T, S]):
    """Marker class for XML validation types.
    
    Use in function return annotations to validate XML content.
    """
    pass


class CSV(BaseType[T, S]):
    """Marker class for CSV validation types.
    
    Use in function return annotations to validate CSV content.
    """
    pass


class Markdown(BaseType[T, S]):
    """Marker class for Markdown validation types.
    
    Use in function return annotations to validate Markdown content.
    """
    pass


class TEXT(BaseType[T, S]):
    """Raw text with no validation.

    The Pythonic alias ``str`` can be used interchangeably::

        result = "summarize this" -> str
        result = "summarize this" -> TEXT

    ``TXT`` is an additional alias that reads well with ``File()``::

        "summarize this" -> File(TXT, "summary.txt")
    """
    pass


TXT = TEXT
