import pytest
from lamia.adapters.llm.validation.utlis.type_matcher import TypeMatcher
import typing
from typing import get_origin
from lamia.adapters.llm.validation.utlis.error_messages import (
    error_msg_none_not_allowed,
    error_msg_cannot_convert_to_any_of,
    error_msg_expected_list_got,
    error_msg_list_element_failed,
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
    (typing.Any, "anything", True, None),
    (typing.Any, 123, True, None),
    (list, [], True, None),
    (list, [1, 2, 3], True, None),
    (list, [1, 2, 3.0, "4"], True, None),
    (list, {"a": 1}, False, error_msg_expected_list_got("dict")),
    (dict, {}, True, None),
    (dict, {"a": 1}, True, None),
    (dict, [1, 2, 3], False, error_msg_expected_dict_got("list")),
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
    (typing.Any, "anything", True, "anything", None),
    (typing.Any, 123, True, 123, None),
    (list, [], True, [], None),
    (list, [1, 2, 3], True, [1, 2, 3], None),
    (list, [1, 2, 3.0, "4"], True, [1, 2, 3, "4"], None),
    (list, {"a": 1}, False, None, error_msg_expected_list_got("dict")),
    (dict, {}, True, {}, None),
    (dict, {"a": 1}, True, {"a": 1}, None),
    (dict, [1, 2, 3], False, None, error_msg_expected_dict_got("list")),
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