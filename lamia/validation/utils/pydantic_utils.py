"""
Utility functions for generating JSON schemas with optional token optimization.
"""
import json
from typing import Dict, Any
from pydantic import BaseModel
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaValue
from pydantic_core import core_schema


class TokenOptimizedGenerateJsonSchema(GenerateJsonSchema):
    """Custom JSON schema generator that removes redundant fields to save tokens."""
    
    def generate(self, schema, mode='validation') -> JsonSchemaValue:
        json_schema = super().generate(schema, mode=mode)
        self._optimize_schema(json_schema)
        return json_schema
    
    def _optimize_schema(self, schema_dict: Dict[str, Any]) -> None:
        """Recursively remove title fields and other redundant information."""
        if isinstance(schema_dict, dict):
            # Remove title fields
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