from typing import TypeVar, Generic
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)
S = TypeVar('S', bound=bool)

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