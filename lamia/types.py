from typing import TypeVar, Generic, Optional
from datetime import timedelta
from pydantic import BaseModel
from dataclasses import dataclass

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
    pass

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