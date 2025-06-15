import pytest
from lamia.adapters.llm.validation.utlis.type_matcher import TypeMatcher
import typing
from typing import get_origin
from lamia.adapters.llm.validation.utlis.error_messages import (
    error_msg_none_not_allowed,
    error_msg_cannot_convert_to_any_of,
    error_msg_expected_list_got,
    error_msg_list_elements_invalid,
    error_msg_dict_elements_invalid,
    error_msg_expected_dict_got,
    error_msg_expected_str_got,
    error_msg_cannot_strictly_convert,
    error_msg_cannot_convert,
)

@pytest.mark.parametrize("expected_type,value,should_match,expected_error", [
    (int, 123, True, None),
    (int, "123", True, None),
    (int, 123.0, False, error_msg_cannot_strictly_convert(123.0, "int")),
    (int, "123.0", False, error_msg_cannot_strictly_convert("123.0", "int")),
    (float, 123.45, True, None),
    (float, "123.45", True, None),
    (float, 123, True, None),
    (float, "123", True, None),
    (bool, True, True, None),
    (bool, False, True, None),
    (bool, "true", True, None),
    (bool, "false", True, None),
    (bool, "1", False, error_msg_cannot_strictly_convert("1", "bool")),
    (bool, "0", False, error_msg_cannot_strictly_convert("0", "bool")),
    (str, "hello", True, None),
    (str, 123, False, error_msg_expected_str_got("int")),
    (str, 123.45, False, error_msg_expected_str_got("float")),
    (int, "abc", False, error_msg_cannot_strictly_convert("abc", "int")),
    (float, "abc", False, error_msg_cannot_strictly_convert("abc", "float")),
    (bool, "abc", False, error_msg_cannot_strictly_convert("abc", "bool")),
    (typing.Any, "anything", True, None),
    (typing.Any, 123, True, None),
    (list, [], True, None),
    (list, [1, 2, 3], True, None),
    (list, [1, 2, 3.0, "4"], True, None),
    (list[float], [1.0, 2.0], True, None),
    (list[int], [-1, 0, 1.1, 2.22, 3.333, 4.4444, 5.55555], False, error_msg_list_elements_invalid([-1, 0, 1.1, 2.22, 3.333, 4.4444, 5.55555], {2: error_msg_cannot_strictly_convert(1.1, "int"), 3: error_msg_cannot_strictly_convert(2.22, "int"), 4: error_msg_cannot_strictly_convert(3.333, "int"), 5: error_msg_cannot_strictly_convert(4.4444, "int"), 6: error_msg_cannot_strictly_convert(5.55555, "int")})),
    (list, {"a": 1}, False, error_msg_expected_list_got("dict")),
    (dict, {}, True, None),
    (dict, {"a": 1}, True, None),
    (dict, [1, 2, 3], False, error_msg_expected_dict_got("list")),
    (dict[str, float], {"a": 1.0, "b": 2.0}, True, None),
    (dict[str, int], {"a": -1, "b": 1.1, 1:2.2}, False, error_msg_dict_elements_invalid({1: error_msg_expected_str_got("int")}, {1.1: error_msg_cannot_strictly_convert(1.1, "int"), 2.2: error_msg_cannot_strictly_convert(2.2, "int")})),
    (typing.Union[int, str], 123, True, None),
    (typing.Union[int, str], "abc", True, None),
    (typing.Union[int, str], 123.45, False, error_msg_cannot_convert_to_any_of(123.45, (int, str))),
])
def test_type_matcher_strict(expected_type, value, should_match, expected_error):
    matcher = TypeMatcher(strict=True)
    result = matcher.validate_and_convert(value, expected_type)
    assert result.is_valid == should_match
    
    if should_match:
        if expected_type is typing.Any:
            assert result.value == value
        elif get_origin(expected_type) is typing.Union:
            assert result.value == value
        elif expected_type is bool and isinstance(value, str):
            assert result.value == to_bool_non_pythonic(value)
        elif isinstance(value, str):
            assert result.value == expected_type(value)
        else:
            assert result.value == value
    
    if should_match:
        assert result.error is None
    else:
        assert result.error == expected_error


def to_bool_non_pythonic(value: str) -> bool:
    return value.strip().lower() == "true"

# Strict not strict type checking tests are sperated because for each setup only one mode should be used.
@pytest.mark.parametrize("expected_type,value,should_match,resulted_value,expected_error", [
    (int, 123, True, 123, None),
    (int, "123", True, 123, None),
    (int, 123.0, True, 123, None),
    (int, "123.0", True, 123, None),
    (float, 123.45, True, 123.45, None),
    (float, "123.45", True, 123.45, None),
    (float, 123, True, 123, None),
    (float, "123", True, 123, None),
    (bool, True, True, True, None),
    (bool, False, True, False, None),
    (bool, "true", True, True, None),
    (bool, "false", True, False, None),
    (bool, "1", True, True, None),
    (bool, "0", True, False, None),
    (str, "hello", True, "hello", None),
    (str, 123, True, "123", None),
    (str, 123.45, True, "123.45", None),
    (int, "abc", False, None, error_msg_cannot_convert("abc", "int")),
    (float, "abc", False, None, error_msg_cannot_convert("abc", "float")),
    (bool, "abc", False, None, error_msg_cannot_convert("abc", "bool")),
    (typing.Any, "anything", True, "anything", None),
    (typing.Any, 123, True, 123, None),
    (list, [], True, [], None),
    (list, [1, 2, 3], True, [1, 2, 3], None),
    (list, [1, 2, 3.0, "4"], True, [1, 2, 3, "4"], None),
    (list[float], [1.0, 2.0], True, [1.0, 2.0], None),
    (list[int], [-1, 0, 1.1, 2.22, 3.333, 4.4444, 5.55555], True, [-1, 0, 1, 2, 3, 4, 5], None),
    (list, {"a": 1}, False, None, error_msg_expected_list_got("dict")),
    (dict, {}, True, {}, None),
    (dict, {"a": 1}, True, {"a": 1}, None),
    (dict, [1, 2, 3], False, None, error_msg_expected_dict_got("list")),
    (dict[str, float], {"a": 1.0, "b": 2.0}, True, {"a": 1.0, "b": 2.0}, None),
    (dict[str, int], {"a": 1.0, "b": 2.0}, True, {"a": 1, "b": 2}, None),
    (dict[str, int], {"a": -1, "b": 1.1, 1:2.2, "bool": True}, True, {"a": -1, "b": 1, "1":2, "bool": 1}, None),
    (typing.Union[int, str], 123, True, 123, None),
    (typing.Union[int, str], "abc", True, "abc", None),
    (typing.Union[int, str], 123.45, True, 123, None),
])
def test_type_matcher_not_strict(expected_type, value, should_match, resulted_value, expected_error):
    matcher = TypeMatcher(strict=False)
    result = matcher.validate_and_convert(value, expected_type)
    assert result.is_valid == should_match
    assert result.value == resulted_value
    if should_match:
        assert result.error is None
    else:
        assert result.error == expected_error

@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("expected_type,value,should_match_strict,should_match_not_strict,expected_error", [
    (int, None, False, False, error_msg_none_not_allowed(int)),
    (typing.Any, None, True, True, None),
    (typing.Optional[int], None, True, True, None),
    (typing.Optional[typing.Any], None, True, True, None),
])
def test_type_matcher_null_values(expected_type, value, should_match_strict, should_match_not_strict, expected_error, strict):
    matcher = TypeMatcher(strict=strict)
    result = matcher.validate_and_convert(value, expected_type)
    if strict:
        assert result.is_valid == should_match_strict
    else:
        assert result.is_valid == should_match_not_strict
    assert result.value is None
    if result.is_valid:
        assert result.error is None
    else:
        assert result.error == expected_error