"""Public API types for Lamia users."""

from typing import TypeVar, Generic, Optional
from datetime import timedelta
from pydantic import BaseModel
from dataclasses import dataclass

T = TypeVar('T', bound=BaseModel)
S = TypeVar('S', bound=bool)


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
