import typing
import re

class TypeMatchResult:
    def __init__(self, is_valid: bool, value: any = None, error: str = None):
        self.is_valid = is_valid
        self.value = value
        self.error = error

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
                return TypeMatchResult(not self.strict, None, None if not self.strict else f"None is not allowed for {expected_type}")

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
                return TypeMatchResult(False, None, f"Cannot convert {value!r} to any of {args}")

            # Handle lists/dicts
            if origin is list:
                if not isinstance(value, list):
                    return TypeMatchResult(False, None, f"Expected list, got {type(value).__name__}")
                if not args:
                    return TypeMatchResult(True, value)
                coerced = []
                for v in value:
                    result = self.validate_and_convert(v, args[0])
                    if not result.is_valid:
                        return TypeMatchResult(False, None, f"List element {v!r} failed: {result.error}")
                    coerced.append(result.value)
                return TypeMatchResult(True, coerced)
            if origin is dict:
                if not isinstance(value, dict):
                    return TypeMatchResult(False, None, f"Expected dict, got {type(value).__name__}")
                return TypeMatchResult(True, value)

            # Primitive types
            if expected_type is str:
                if isinstance(value, str):
                    return TypeMatchResult(True, value)
                if not self.strict:
                    return TypeMatchResult(True, str(value))
                return TypeMatchResult(False, None, f"Expected str, got {type(value).__name__}")
            if expected_type is int:
                return self._convert_int(value)
            if expected_type is float:
                return self._convert_float(value)
            if expected_type is bool:
                return self._convert_bool(value)

            # Fallback
            if isinstance(value, expected_type):
                return TypeMatchResult(True, value)
            return TypeMatchResult(False, None, f"Expected {expected_type}, got {type(value).__name__}")
        except Exception as e:
            return TypeMatchResult(False, None, str(e))

    def _convert_int(self, value):
        if isinstance(value, int):
            return TypeMatchResult(True, value)
        if self.strict:
            if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
                return TypeMatchResult(True, int(value))
            return TypeMatchResult(False, None, f"Cannot strictly convert {value!r} to int")
        # relaxed
        if isinstance(value, float):
            return TypeMatchResult(True, int(value))
        if isinstance(value, str):
            try:
                return TypeMatchResult(True, int(value))
            except ValueError:
                try:
                    float_val = float(value)
                    # Allow truncation in relaxed mode
                    return TypeMatchResult(True, int(float_val))
                except Exception:
                    pass
        return TypeMatchResult(False, None, f"Cannot convert {value!r} to int")

    def _convert_float(self, value):
        if isinstance(value, float):
            return TypeMatchResult(True, value)
        if isinstance(value, int):
            return TypeMatchResult(True, float(value))
        if self.strict:
            if isinstance(value, str) and re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+|\d+)", value.strip()):
                return TypeMatchResult(True, float(value))
            return TypeMatchResult(False, None, f"Cannot strictly convert {value!r} to float")
        # relaxed
        if isinstance(value, str):
            try:
                return TypeMatchResult(True, float(value))
            except Exception:
                pass
        return TypeMatchResult(False, None, f"Cannot convert {value!r} to float")

    def _convert_bool(self, value):
        if isinstance(value, bool):
            return TypeMatchResult(True, value)
        if self.strict:
            if isinstance(value, str) and value.strip().lower() in ("true", "false"):
                return TypeMatchResult(True, value.strip().lower() == "true")
            return TypeMatchResult(False, None, f"Cannot strictly convert {value!r} to bool")
        # relaxed
        if isinstance(value, str):
            v = value.strip().lower()
            if v in ("true", "1"):
                return TypeMatchResult(True, True)
            if v in ("false", "0"):
                return TypeMatchResult(True, False)
        return TypeMatchResult(False, None, f"Cannot convert {value!r} to bool") 