# Error message templates for TypeMatcher

MAX_INVALID_ELEMENTS_IN_REPORT = 3

def error_msg_none_not_allowed(expected_type):
    return f"None is not allowed for {expected_type}"

def error_msg_cannot_convert_to_any_of(value, args):
    return f"Cannot convert {value!r} to any of {args}"

def error_msg_expected_type_got(expected, actual):
    return f"Expected {expected}, got {actual}"

def error_msg_expected_list_got(actual):
    return error_msg_expected_type_got("list", actual)

def error_msg_list_elements_invalid(list, invlaid_elems):
    if len(invlaid_elems) >= MAX_INVALID_ELEMENTS_IN_REPORT:
        n_more = len(invlaid_elems) - MAX_INVALID_ELEMENTS_IN_REPORT
    return f"List elements with failed validation: {[f'{list[invalid_index]} at index {invalid_index} with failed validation: {invlaid_elems[invalid_index]}' for invalid_index in sorted(invlaid_elems.keys())[:MAX_INVALID_ELEMENTS_IN_REPORT]]} {f'{n_more} more failed elements are skipped...' if n_more else ''}"

def error_msg_expected_dict_got(actual):
    return error_msg_expected_type_got("dict", actual)

def error_msg_expected_str_got(actual):
    return error_msg_expected_type_got("str", actual)

def error_msg_cannot_strictly_convert(value, type_name):
    return f"Cannot strictly convert {value!r} to {type_name}"

def error_msg_cannot_convert(value, type_name):
    return f"Cannot convert {value!r} to {type_name}" 