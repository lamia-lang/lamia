import typing
import re
from pydantic import TypeAdapter, ValidationError, ConfigDict
from .error_messages import (
    error_msg_none_not_allowed,
    error_msg_cannot_convert_to_any_of,
    error_msg_expected_type_got,
    error_msg_expected_list_got,
    error_msg_list_elements_invalid,
    error_msg_dict_elements_invalid,
    error_msg_expected_dict_got,
    error_msg_expected_str_got,
    error_msg_cannot_strictly_convert,
    error_msg_cannot_convert,
)
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

@dataclass
class TypeMatchResult:
    is_valid: bool
    value: any = None
    error: str = None
    info_loss: dict = field(default_factory=dict)

class TypeMatcher:
    def __init__(self, strict: bool = False, get_text_func=None):
        self.strict = strict
        self.get_text_func = get_text_func



    def validate_and_convert(self, value, expected_type) -> TypeMatchResult:
        try:
            # Handle Optionals
            if value is None:
                if typing.get_origin(expected_type) is typing.Union and type(None) in typing.get_args(expected_type):
                    return TypeMatchResult(True, None)
                if expected_type is typing.Any:
                    return TypeMatchResult(True, None)
                return TypeMatchResult(False, None, error_msg_none_not_allowed(expected_type))

            # Handle Any
            if expected_type is typing.Any or expected_type is object:
                return TypeMatchResult(True, value)

            # Handle Unions
            origin = typing.get_origin(expected_type)
            args = typing.get_args(expected_type)
            if origin is typing.Union:
                for arg in args:
                    result = self.validate_and_convert(value, arg)
                    if result.is_valid:
                        return result
                return TypeMatchResult(False, None, error_msg_cannot_convert_to_any_of(value, args))

            # Handle Pydantic constrained (Annotated) types
            # To check if pydantic constraints are not violated
            if origin is typing.Annotated:
                try:
                    adapter = TypeAdapter(expected_type, config=ConfigDict(strict=self.strict)) # Pass lamia strictness flag to pydantic
                    validated_value = adapter.validate_python(value, strict=self.strict) # To make sure it is used
                    # the validated_value is a pydantic model we ignore it to continue typed validation to record info_loss, etc. 
                    logger.debug(f"Pydantic's validated_value (not used by lamia): {validated_value}")
                except ValidationError as e:
                    # Collect all error messages from pydantic validation
                    error_messages = "; ".join(err["msg"] for err in e.errors())
                    return TypeMatchResult(False, None, error_messages)

            # Handle lists/dicts
            if origin is list:
                if not isinstance(value, list):
                    return TypeMatchResult(False, None, error_msg_expected_list_got(type(value).__name__))
                if not args:
                    return TypeMatchResult(True, value)
                coerced = []
                invalid_elems = {}
                combined_info_loss = {}
                for index, v in enumerate(value):
                    result = self.validate_and_convert(v, args[0])
                    if not result.is_valid:
                        invalid_elems[index] = result.error
                    coerced.append(result.value)
                    # Collect info loss from nested conversions
                    if result.info_loss:
                        combined_info_loss[f"element_{index}"] = result.info_loss
                
                if invalid_elems:
                    return TypeMatchResult(False, None, error_msg_list_elements_invalid(value, invalid_elems))
                return TypeMatchResult(True, coerced, info_loss=combined_info_loss)
            if origin is dict:
                if not isinstance(value, dict):
                    return TypeMatchResult(False, None, error_msg_expected_dict_got(type(value).__name__))
                coerced = {}
                invalid_keys = {}
                invalid_values = {}
                combined_info_loss = {}
                for k, v in value.items():
                    k_result = self.validate_and_convert(k, args[0])
                    if not k_result.is_valid:
                        invalid_keys[k] = k_result.error
                    v_result = self.validate_and_convert(v, args[1])
                    if not v_result.is_valid:
                        invalid_values[v] = v_result.error
                    coerced[k_result.value] = v_result.value
                    # Collect info loss from nested conversions
                    if k_result.info_loss:
                        combined_info_loss[f"key_{k}"] = k_result.info_loss
                    if v_result.info_loss:
                        combined_info_loss[f"value_{k}"] = v_result.info_loss
                
                if invalid_keys or invalid_values:
                    return TypeMatchResult(False, None, error_msg_dict_elements_invalid(invalid_keys, invalid_values))
                return TypeMatchResult(True, coerced, info_loss=combined_info_loss)

            # Primitive types
            if expected_type is str:
                if isinstance(value, str):
                    return TypeMatchResult(True, value)
                # Allow primitive-to-string conversion even in strict mode
                # When user explicitly models a field as str, they want strings regardless of source format
                if isinstance(value, (int, float, bool)):
                    info_loss = {
                        "conversion": f"{type(value).__name__} -> str",
                        "original_value": value,
                        "original_type": type(value).__name__
                    }
                    return TypeMatchResult(True, str(value), info_loss=info_loss)
                if not self.strict:
                    # Converting other types to string can lose type information
                    info_loss = {
                        "conversion": f"{type(value).__name__} -> str",
                        "original_value": value,
                        "original_type": type(value).__name__
                    }
                    return TypeMatchResult(True, str(value), info_loss=info_loss)
                return TypeMatchResult(False, None, error_msg_expected_str_got(type(value).__name__))
            if expected_type is int:
                return self._convert_int(value)
            if expected_type is float:
                return self._convert_float(value)
            if expected_type is bool:
                return self._convert_bool(value)

            # Fallback
            if isinstance(value, expected_type):
                return TypeMatchResult(True, value)
            return TypeMatchResult(False, None, error_msg_expected_type_got(expected_type.__name__, type(value).__name__))
        except Exception as e:
            return TypeMatchResult(False, None, str(e))

    def _convert_int(self, value):
        if isinstance(value, int):
            return TypeMatchResult(True, value)
        if self.strict:
            if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
                return TypeMatchResult(True, int(value))
            return TypeMatchResult(False, None, error_msg_cannot_strictly_convert(value, "int"))
        # relaxed
        if isinstance(value, float):
            # Track info loss when converting float to int
            original_float = value
            converted_int = int(value)
            info_loss = {}
            if original_float != converted_int:
                info_loss = {
                    "conversion": "float -> int",
                    "original_value": original_float,
                    "converted_value": converted_int,
                    "lost_decimal": original_float - converted_int
                }
            return TypeMatchResult(True, converted_int, info_loss=info_loss)
        if isinstance(value, str):
            try:
                return TypeMatchResult(True, int(value))
            except ValueError:
                try:
                    float_val = float(value)
                    # Allow truncation in relaxed mode - track info loss
                    converted_int = int(float_val)
                    info_loss = {}
                    if float_val != converted_int:
                        info_loss = {
                            "conversion": "str -> float -> int",
                            "original_value": value,
                            "intermediate_float": float_val,
                            "converted_value": converted_int,
                            "lost_decimal": float_val - converted_int
                        }
                    return TypeMatchResult(True, converted_int, info_loss=info_loss)
                except Exception:
                    pass
        return TypeMatchResult(False, None, error_msg_cannot_convert(value, "int"))

    def _convert_float(self, value):
        if isinstance(value, float):
            return TypeMatchResult(True, value)
        if isinstance(value, int):
            return TypeMatchResult(True, float(value))
        if self.strict:
            if isinstance(value, str) and re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+|\d+)", value.strip()):
                return TypeMatchResult(True, float(value))
            return TypeMatchResult(False, None, error_msg_cannot_strictly_convert(value, "float"))
        # relaxed
        if isinstance(value, str):
            try:
                return TypeMatchResult(True, float(value))
            except Exception:
                pass
        return TypeMatchResult(False, None, error_msg_cannot_convert(value, "float"))

    def _convert_bool(self, value):
        if isinstance(value, bool):
            return TypeMatchResult(True, value)
        if self.strict:
            if isinstance(value, str) and value.strip().lower() in ("true", "false"):
                return TypeMatchResult(True, value.strip().lower() == "true")
            return TypeMatchResult(False, None, error_msg_cannot_strictly_convert(value, "bool"))
        # relaxed
        if isinstance(value, str):
            v = value.strip().lower()
            if v in ("true", "1"):
                return TypeMatchResult(True, True)
            if v in ("false", "0"):
                return TypeMatchResult(True, False)
        return TypeMatchResult(False, None, error_msg_cannot_convert(value, "bool"))