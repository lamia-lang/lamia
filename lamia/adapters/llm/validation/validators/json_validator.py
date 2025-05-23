import re
import json
from ..base import BaseValidator, ValidationResult

class JSONValidator(BaseValidator):
    """Validates if the response is valid JSON."""
    @classmethod
    def name(cls) -> str:
        return "json"

    @property
    def initial_hint(self) -> str:
        return "Please return only valid JSON, with no explanation or extra text. The response must be a single JSON object or array."

    async def validate(self, response: str, **kwargs) -> ValidationResult:
        try:
            json.loads(response)
            return ValidationResult(is_valid=True)
        except json.JSONDecodeError as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid JSON: {str(e)}",
                hint="Please ensure the response is valid JSON. All keys and string values must be in double quotes, and the structure must be correct."
            )

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        stripped = response.strip()
        try:
            json.loads(stripped)
            return ValidationResult(is_valid=True)
        except json.JSONDecodeError as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid JSON: {str(e)}",
                hint=self.initial_hint
            )

    async def validate_restrictive(self, response: str, **kwargs) -> ValidationResult:
        stripped = response.strip()
        match = re.search(r'({[\s\S]*})|\[([\s\S]*)\]', stripped)
        if not match:
            return ValidationResult(
                is_valid=False,
                error_message="No valid JSON object or array found.",
                hint=self.initial_hint
            )
        json_block = match.group(0)
        try:
            json.loads(json_block)
            return ValidationResult(is_valid=True, validated_text=json_block)
        except json.JSONDecodeError as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid JSON: {str(e)}",
                hint=self.initial_hint
            ) 