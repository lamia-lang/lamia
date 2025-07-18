from typing import Type, get_args, get_origin, TypeVar, Generic
from pydantic import BaseModel
from lamia.validation.base import BaseValidator
from lamia.types import BaseType, HTML, YAML, JSON
from lamia.validation.validators.file_validators.html_validator import HTMLValidator
from lamia.validation.validators.file_validators.file_structure.html_structure_validator import HTMLStructureValidator
from lamia.validation.validators.file_validators.yaml_validator import YAMLValidator
from lamia.validation.validators.file_validators.file_structure.yaml_structure_validator import YAMLStructureValidator
from lamia.validation.validators.file_validators.json_validator import JSONValidator
from lamia.validation.validators.file_validators.file_structure.json_structure_validator import JSONStructureValidator

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
  
