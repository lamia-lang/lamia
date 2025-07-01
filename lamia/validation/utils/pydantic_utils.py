"""
Utility functions for generating JSON schemas with optional token optimization.
"""
import json
from typing import Dict, Any
from collections import OrderedDict
from pydantic import BaseModel, create_model
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaValue
from pydantic_core import core_schema


def get_ordered_dict_fields(model) -> list[str]:
    """Find fields that need order preservation in BaseModel classes.
    
    ONLY supports the __ordered_fields__ pattern:
        class MyModel(BaseModel):
            regular_field: str
            __ordered_fields__ = OrderedDict([("ordered_field", int)])
    
    Returns:
        List of field names that need order preservation.
    """
    # Fail fast for OrderedDict as entire model (legacy pattern no longer supported)
    if isinstance(model, OrderedDict):
        raise ValueError("OrderedDict as entire model is no longer supported. "
                        "Use BaseModel with '__ordered_fields__' class attribute instead.")
    
    # Fail fast for OrderedDict field type annotations (NOT SUPPORTED)
    if hasattr(model, 'model_fields'):
        for field_name, field_info in model.model_fields.items():
            field_type = field_info.annotation
            
            # Fail fast for OrderedDict as field type annotation
            if hasattr(field_type, '__origin__') and field_type.__origin__ is OrderedDict:
                raise ValueError(f"Field '{field_name}' uses OrderedDict as type annotation. "
                               "Use '__ordered_fields__' class attribute instead.")
            elif str(field_type).startswith('collections.OrderedDict') or str(field_type).startswith('typing.OrderedDict'):
                raise ValueError(f"Field '{field_name}' uses OrderedDict as type annotation. "
                               "Use '__ordered_fields__' class attribute instead.")
    
    # Only supported pattern: Look for __ordered_fields__ class attribute
    ordered_fields = []
    if hasattr(model, '__ordered_fields__') and isinstance(model.__ordered_fields__, OrderedDict):
        ordered_fields.extend(model.__ordered_fields__.keys())
    
    return ordered_fields


class TokenOptimizedGenerateJsonSchema(GenerateJsonSchema):
    """Custom JSON schema generator that removes redundant fields to save tokens."""
    
    def generate(self, schema, mode='validation') -> JsonSchemaValue:
        json_schema = super().generate(schema, mode=mode)
        self._optimize_schema(json_schema)
        return json_schema
    
    def _optimize_schema(self, schema_dict: Dict[str, Any]) -> None:
        """Recursively remove title metadata fields and other redundant information."""
        if isinstance(schema_dict, dict):
            # Only remove title if this looks like a field definition with type/ref info
            # Don't remove title from properties objects that represent actual model fields
            has_type_info = any(key in schema_dict for key in ['type', '$ref', 'anyOf', 'allOf', 'oneOf'])
            has_properties = 'properties' in schema_dict
            
            # Remove title metadata from field definitions, but not from properties lists
            if has_type_info and not has_properties:
                schema_dict.pop('title', None)
            # Also remove title from the root schema if it has properties (schema-level title)
            elif has_properties:
                schema_dict.pop('title', None)
            
            # Recursively process all nested objects
            for key, value in list(schema_dict.items()):
                if isinstance(value, dict):
                    self._optimize_schema(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            self._optimize_schema(item)


def _get_json_schema(model: BaseModel, optimize_for_tokens: bool = False) -> dict:
    if optimize_for_tokens:
        schema_generator = TokenOptimizedGenerateJsonSchema
    else:
        schema_generator = GenerateJsonSchema
    
    json_schema = model.model_json_schema(schema_generator=schema_generator)
    return json_schema

def get_pydantic_json_schema(model: BaseModel, optimize_for_tokens: bool = False) -> str:
    json_schema = _get_json_schema(model, optimize_for_tokens)
    return json.dumps(json_schema, separators=(',', ':'))


def get_formatted_json_schema_human_readable(model: BaseModel, optimize_for_tokens: bool = False) -> str:
    json_schema = _get_json_schema(model, optimize_for_tokens)
    return json.dumps(json_schema, indent=2) 