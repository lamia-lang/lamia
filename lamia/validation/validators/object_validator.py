from pydantic import create_model, ValidationError, BaseModel
from ..base import BaseValidator, ValidationResult
from ..utils.pydantic_utils import get_pydantic_json_schema
from ..utils.type_matcher import TypeMatcher
import json as _json
import re
from typing import Union, Type, get_origin, get_args, Any, Optional, List
from collections import OrderedDict

def is_optional(field_type: Any) -> bool:
    return get_origin(field_type) is Union and type(None) in get_args(field_type)

def is_pydantic_model(field_type: Any) -> bool:
    try:
        return issubclass(field_type, BaseModel)
    except TypeError:
        return False

def is_list_of_models(field_type: Any) -> bool:
    origin = get_origin(field_type)
    args = get_args(field_type)
    return origin in (list, List) and args and is_pydantic_model(args[0])

class ObjectValidator(BaseValidator):
    """Validates if the response matches an object type (dict/record) using a Pydantic model schema or a Pydantic BaseModel class."""
    @classmethod
    def name(cls) -> str:
        return "object"

    def __init__(self, schema: Union[dict, Type[BaseModel]], strict: bool = True, generate_hints: bool = False):
        super().__init__(strict=strict, generate_hints=generate_hints)
        self.schema = schema
        if isinstance(schema, dict):
            self.model = self._create_pydantic_model(schema)
        elif isinstance(schema, type) and issubclass(schema, BaseModel):
            self.model = schema
        else:
            raise ValueError("schema must be a dict or a Pydantic BaseModel subclass")
        
        # Initialize TypeMatcher for field-by-field validation
        self.type_matcher = TypeMatcher(strict=strict)

    @property
    def initial_hint(self) -> str:
        # TODO: for openai and anthropic we can request the object structure with a structured api params instead of a prompt
        json_schema = get_pydantic_json_schema(self.model)
        return f"Please ensure the response is a valid JSON object matching the required schema, with no explanation or extra text. Schema: {json_schema}"

    def _create_pydantic_model(self, schema: dict):
        type_map = {
            "int": int,
            "float": float,
            "str": str,
            "string": str,
            "bool": bool,
            "list": list,
            "dict": dict,
        }
        fields = {}
        for k, v in schema.items():
            if isinstance(v, str):
                fields[k] = (type_map.get(v, str), ...)
            elif isinstance(v, tuple):
                fields[k] = v
            else:
                fields[k] = (v, ...)
        return create_model("ObjectValidatorModel", **fields)

    def _validate_dict(self, data: dict, model: Type[BaseModel]) -> ValidationResult:
        """Validate a dictionary against a Pydantic model using field-by-field validation."""
        errors = []
        values = {}
        is_valid = True
        info_loss = {}

        # Get model fields
        model_fields = [(field, field_info) for field, field_info in model.model_fields.items()]

        for field, field_info in model_fields:
            expected_type = field_info.annotation
            value = data.get(field)

            # Handle missing fields
            if field not in data:
                if is_optional(expected_type):
                    values[field] = None
                    continue
                errors.append(f"Missing field '{field}'")
                is_valid = False
                continue

            # Handle None values
            if value is None:
                if is_optional(expected_type):
                    values[field] = None
                    continue
                errors.append(f"Field '{field}' cannot be None")
                is_valid = False
                continue

            # Recursive validation for nested models
            if is_pydantic_model(expected_type):
                if not isinstance(value, dict):
                    errors.append(f"Field '{field}': Expected dict for nested model, got {type(value).__name__}")
                    is_valid = False
                    values[field] = None
                    continue
                
                nested_result = self._validate_dict(value, expected_type)
                if not nested_result.is_valid:
                    errors.append(f"Field '{field}': {nested_result.error_message}")
                    is_valid = False
                    values[field] = None
                else:
                    values[field] = nested_result.result_type
                    # Collect nested info loss
                    if nested_result.info_loss:
                        info_loss[field] = nested_result.info_loss
                continue

            # Recursive validation for lists of models
            if is_list_of_models(expected_type):
                if not isinstance(value, list):
                    errors.append(f"Field '{field}': Expected list, got {type(value).__name__}")
                    is_valid = False
                    values[field] = None
                    continue
                
                item_type = get_args(expected_type)[0]
                nested_values = []
                field_info_loss = {}
                
                for idx, item in enumerate(value):
                    if not isinstance(item, dict):
                        errors.append(f"Field '{field}[{idx}]': Expected dict for nested model, got {type(item).__name__}")
                        is_valid = False
                        nested_values.append(None)
                        continue
                    
                    nested_result = self._validate_dict(item, item_type)
                    if not nested_result.is_valid:
                        errors.append(f"Field '{field}[{idx}]': {nested_result.error_message}")
                        is_valid = False
                        nested_values.append(None)
                    else:
                        nested_values.append(nested_result.result_type)
                        # Collect nested info loss
                        if nested_result.info_loss:
                            field_info_loss[f"item_{idx}"] = nested_result.info_loss
                
                values[field] = nested_values
                if field_info_loss:
                    info_loss[field] = field_info_loss
                continue

            # Use type_matcher for leaf fields
            match_result = self.type_matcher.validate_and_convert(value, expected_type)
            if not match_result.is_valid:
                errors.append(f"Field '{field}': {match_result.error}")
                is_valid = False
                values[field] = None
            else:
                values[field] = match_result.value
                # Collect type conversion info loss
                if match_result.info_loss:
                    info_loss[field] = match_result.info_loss

        # Create model instance if validation passed
        model_instance = None
        if is_valid:
            try:
                model_instance = model(**values)
            except Exception as e:
                errors.append(f"Model creation error: {e}")
                is_valid = False

        error_message = '; '.join(errors) if errors else None
        validated_text = _json.dumps(data, indent=2) if data else None

        return ValidationResult(
            is_valid=is_valid,
            result_type=model_instance,
            validated_text=validated_text,
            error_message=error_message,
            info_loss=info_loss if info_loss else None
        )

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        try:
            data = _json.loads(response)
        except Exception as e:
            error_msg = f"Response is not valid JSON: {e}"
            return ValidationResult(
                is_valid=False,
                error_message=error_msg,
                hint=self.get_retry_hint(error=e)
            )
        
        if not isinstance(data, dict):
            error_msg = f"Expected JSON object, got {type(data).__name__}"
            return ValidationResult(
                is_valid=False,
                error_message=error_msg,
                hint=self.get_retry_hint(retry_hint=error_msg)
            )
        
        result = self._validate_dict(data, self.model)
        if not result.is_valid and self.generate_hints:
            result.hint = self.get_retry_hint(retry_hint=result.error_message)
        return result

    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        match = re.search(r'({[\s\S]*})', response)
        if not match:
            error_msg = "No valid JSON object found."
            return ValidationResult(
                is_valid=False,
                error_message=error_msg,
                hint=self.get_retry_hint(retry_hint=error_msg)
            )
        json_block = match.group(0)
        try:
            data = _json.loads(json_block)
        except Exception as e:
            error_msg = f"Extracted JSON is not valid: {e}"
            return ValidationResult(
                is_valid=False,
                error_message=error_msg,
                hint=self.get_retry_hint(error=e)
            )
        
        if not isinstance(data, dict):
            error_msg = f"Expected JSON object, got {type(data).__name__}"
            return ValidationResult(
                is_valid=False,
                error_message=error_msg,
                hint=self.get_retry_hint(retry_hint=error_msg)
            )
        
        result = self._validate_dict(data, self.model)
        if result.is_valid:
            result.validated_text = json_block
        elif self.generate_hints:
            result.hint = self.get_retry_hint(retry_hint=result.error_message)
        return result 