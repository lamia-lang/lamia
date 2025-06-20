from pydantic import create_model, ValidationError
from ..base import BaseValidator, ValidationResult
import json as _json
import re

class ObjectValidator(BaseValidator):
    """Validates if the response matches an object type (dict/record) using a Pydantic model schema."""
    @classmethod
    def name(cls) -> str:
        return "object"
    def __init__(self, schema: dict, strict: bool = True):
        super().__init__(strict=strict)
        self.schema = schema
        self.model = self._create_pydantic_model(schema)

    @property
    def initial_hint(self) -> str:
        return "Please ensure the response is a valid JSON object matching the required schema, with no explanation or extra text."

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
            return ValidationResult(
                is_valid=False,
                error_message=f"Response is not valid JSON: {e}",
                hint=self.initial_hint
            )
        try:
            self.model.model_validate(data)
            return ValidationResult(is_valid=True)
        except ValidationError as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Response does not match schema: {e}",
                hint=self.initial_hint
            )

    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        match = re.search(r'({[\s\S]*})', response)
        if not match:
            return ValidationResult(
                is_valid=False,
                error_message="No valid JSON object found.",
                hint=self.initial_hint
            )
        json_block = match.group(0)
        try:
            data = _json.loads(json_block)
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Extracted JSON is not valid: {e}",
                hint=self.initial_hint
            )
        try:
            self.model.model_validate(data)
            return ValidationResult(is_valid=True, validated_text=json_block)
        except ValidationError as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Extracted JSON does not match schema: {e}",
                hint=self.initial_hint
            ) 