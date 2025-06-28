from pydantic import create_model, ValidationError, BaseModel
from ..base import BaseValidator, ValidationResult
from ..utils.pydantic_utils import get_pydantic_json_schema
import json as _json
import re
from typing import Union, Type

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
        try:
            self.model.model_validate(data)
            return ValidationResult(is_valid=True)
        except ValidationError as e:
            error_msg = f"Response does not match schema: {e}"
            return ValidationResult(
                is_valid=False,
                error_message=error_msg,
                hint=self.get_retry_hint(error=e)
            )

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
        try:
            self.model.model_validate(data)
            return ValidationResult(is_valid=True, validated_text=json_block)
        except ValidationError as e:
            error_msg = f"Extracted JSON does not match schema: {e}"
            return ValidationResult(
                is_valid=False,
                error_message=error_msg,
                hint=self.get_retry_hint(error=e)
            ) 