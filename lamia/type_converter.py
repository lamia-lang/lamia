from typing import Type, get_args, get_origin
from lamia.validation.base import BaseValidator
from lamia.types import BaseType, HTML, YAML, JSON
from lamia.validation.validators.file_validators.html_validator import HTMLValidator
from lamia.validation.validators.file_validators.yaml_validator import YAMLValidator
from lamia.validation.validators.file_validators.json_validator import JSONValidator
from lamia.validation.validators.file_validators.file_structure.html_structure_validator import HTMLStructureValidator
from lamia.validation.validators.file_validators.file_structure.yaml_structure_validator import YAMLStructureValidator
from lamia.validation.validators.file_validators.file_structure.json_structure_validator import JSONStructureValidator

def create_validator(validation_type: Type[BaseType]) -> BaseValidator:
    """
    Create validator based on type annotation.
    
    Args:
        validation_type: The validation type (e.g., HTML, HTML[MyModel], YAML[MyModel, False])
        
    Returns:
        BaseValidator: The appropriate validator instance
    """
    origin = get_origin(validation_type)
    args = get_args(validation_type)
    
    # Determine the base type (HTML, YAML, JSON, etc.)
    if origin is None:
        base_type = validation_type
        model = None
        strict = True
    else:
        base_type = origin
        if len(args) == 1:
            model = args[0]
            strict = True
        elif len(args) == 2:
            model, strict = args
        else:
            raise ValueError(f"Invalid type: {validation_type}")
    
    # Create the appropriate validator based on base type
    if base_type is HTML:
        return _create_html_validator(model, strict)
    elif base_type is YAML:
        return _create_yaml_validator(model, strict)
    elif base_type is JSON:
        return _create_json_validator(model, strict)
    else:
        raise ValueError(f"Unsupported validation type: {base_type}")
    
def _create_html_validator(model, strict: bool) -> BaseValidator:
    if model is not None:
        return HTMLStructureValidator(model=model, strict=strict)
    else:
        return HTMLValidator()

def _create_yaml_validator(model, strict: bool) -> BaseValidator:
    if model is not None:
        return YAMLStructureValidator(model=model, strict=strict)
    else:
        return YAMLValidator()

def _create_json_validator(model, strict: bool) -> BaseValidator:
    if model is not None:
        return JSONStructureValidator(model=model, strict=strict)
    else:
        return JSONValidator()