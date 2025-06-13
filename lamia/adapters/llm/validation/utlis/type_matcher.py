import typing
import re

class TypeMatcher:
    def __init__(self, strict: bool = False, get_text_func=None):
        self.strict = strict
        self.get_text_func = get_text_func  # function to extract text from AST nodes

    def _is_primitive_type(self, t):
        return t in (str, int, float, bool)

    def _normalize_primitive_type(self, t):
        # Normalize to canonical Python primitive types
        if t == str or t == type(str()):
            return str
        if t == int or t == type(int()):
            return int
        if t == float or t == type(float()):
            return float
        if t == bool or t == type(bool()):
            return bool
        return t

    def _get_primitive_value(self, value, expected_type):
        if self.get_text_func:
            return self.get_text_func(value)
        return value

    def _is_type_match_strictly_typed(self, value, expected_type):
        if expected_type is int:
            if isinstance(value, int):
                return True
            if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
                return True
            return False
        if expected_type is float:
            if isinstance(value, (int, float)):
                return True
            if isinstance(value, str) and re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+|\d+)", value.strip()):
                return True
            return False
        if expected_type is bool:
            if isinstance(value, bool):
                return True
            if isinstance(value, str) and value.strip().lower() in ("true", "false"):
                return True
            return False
        return False

    def _is_type_match(self, value, expected_type):
        value = self._get_primitive_value(value, expected_type)
        origin = typing.get_origin(expected_type)
        args = typing.get_args(expected_type)
        # Handle built-in list/dict as well as typing generics
        if expected_type is list or origin is list:
            return isinstance(value, list) and (not args or all(self._is_type_match(v, args[0]) for v in value))
        if expected_type is dict or origin is dict:
            return isinstance(value, dict)
        if expected_type is typing.Union or origin is typing.Union:
            return any(self._is_type_match(value, arg) for arg in args)
        if origin is None:
            if expected_type is typing.Any or expected_type is object:
                return True
            if expected_type is str:
                return isinstance(value, str)
            if expected_type is int:
                if self.strict:
                    return self._is_type_match_strictly_typed(value, int)
                if isinstance(value, int):
                    return True
                if isinstance(value, str):
                    s = value.strip()
                    if re.fullmatch(r"-?\d+", s):
                        return True
                    try:
                        float(s)
                        return True
                    except Exception:
                        pass
                return False
            if expected_type is float:
                if self.strict:
                    return self._is_type_match_strictly_typed(value, float)
                if isinstance(value, float) or isinstance(value, int):
                    return True
                if isinstance(value, str):
                    try:
                        float(value)
                        return True
                    except (ValueError, TypeError):
                        return False
                return False
            if expected_type is bool:
                if self.strict:
                    return self._is_type_match_strictly_typed(value, bool)
                if isinstance(value, bool):
                    return True
                if isinstance(value, str) and value.strip().lower() in ("true", "false", "1", "0"):
                    return True
                return False
            return isinstance(value, expected_type)
        return False 