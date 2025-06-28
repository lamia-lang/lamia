# Error message templates for TypeMatcher

from typing import Any, Dict, List

MAX_INVALID_ELEMENTS_IN_REPORT = 3

def error_msg_none_not_allowed(expected_type: str) -> str:
    return f"None is not allowed for {expected_type}"

def error_msg_cannot_convert_to_any_of(value: Any, args: tuple) -> str:
    return f"Cannot convert {value!r} to any of {args}"

def error_msg_expected_type_got(expected: str, actual: str) -> str:
    return f"Expected {expected}, got {actual}"

def error_msg_expected_list_got(actual: str) -> str:
    return error_msg_expected_type_got("list", actual)

def error_msg_list_elements_invalid(list: List[Any], invalid_elems: Dict[int, str]) -> str:
    n_more = len(invalid_elems) - MAX_INVALID_ELEMENTS_IN_REPORT
    return f"List elements with failed validation: {[f'{list[invalid_index]} at index {invalid_index} with failed validation: {invalid_elems[invalid_index]}' for invalid_index in sorted(invalid_elems.keys())[:MAX_INVALID_ELEMENTS_IN_REPORT]]} {f'{n_more} more failed elements are skipped...' if n_more > 0 else ''}"

def error_msg_dict_elements_invalid(invalid_keys: Dict[Any, str], invalid_values: Dict[Any, str]) -> str:
    n_more = len(invalid_keys) + len(invalid_values) - MAX_INVALID_ELEMENTS_IN_REPORT
    error_arr = [f'dict key {invalid_key} with failed validation: {invalid_keys[invalid_key]}' for invalid_key in sorted(invalid_keys.keys())] \
              + [f'dict value {invalid_value} with failed validation: {invalid_values[invalid_value]}' for invalid_value in sorted(invalid_values.keys())]
    return f"Dict elements with failed validation: {error_arr[:MAX_INVALID_ELEMENTS_IN_REPORT]} {f'{n_more} more failed elements are skipped...' if n_more > 0 else ''}"

def error_msg_expected_dict_got(actual: str) -> str:
    return error_msg_expected_type_got("dict", actual)

def error_msg_expected_str_got(actual: str) -> str:
    return error_msg_expected_type_got("str", actual)

def error_msg_cannot_strictly_convert(value: Any, type_name: str) -> str:
    return f"Cannot strictly convert {value!r} to {type_name}"

def error_msg_cannot_convert(value: Any, type_name: str) -> str:
    return f"Cannot convert {value!r} to {type_name}" 