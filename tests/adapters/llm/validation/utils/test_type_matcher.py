import pytest
from lamia.adapters.llm.validation.utlis.type_matcher import TypeMatcher
import typing
from typing import get_origin

@pytest.mark.parametrize("expected_type,value,should_match", [
    (int, 123, True),
    (int, "123", True),
    (int, 123.0, False),
    (int, "123.0", False),
    (float, 123.45, True),
    (float, "123.45", True),
    (float, 123, True),
    (float, "123", True),
    (bool, True, True),
    (bool, False, True),
    (bool, "true", True),
    (bool, "false", True),
    (bool, "1", False),
    (bool, "0", False),
    (str, "hello", True),
    (str, 123, False),
    (str, 123.45, False),
    (typing.Any, "anything", True),
    (typing.Any, 123, True),
    (list, [], True),
    (list, [1, 2, 3], True),
    (list, [1, 2, 3.0, "4"], True),
    (list, {"a": 1}, False),
    (dict, {}, True),
    (dict, {"a": 1}, True),
    (dict, [1, 2, 3], False),
    (typing.Union[int, str], 123, True),
    (typing.Union[int, str], "abc", True),
    (typing.Union[int, str], 123.45, False),
])
def test_type_matcher_strict(expected_type, value, should_match):
    matcher = TypeMatcher(strict=True)
    result = matcher.validate_and_convert(value, expected_type)
    assert result.is_valid == should_match
    
    if should_match:
        if expected_type is typing.Any: # isinstance fails on Any type. A workaround for the tests with Any type
            assert result.value == value
        elif get_origin(expected_type) is typing.Union: # isinstance fails on Union type. A workaround for the tests with Union type
            assert result.value == value
        elif expected_type is bool and isinstance(value, str): # when parsing string Python does not consider values of the strings. It returns True if teh string is not empty. Since Lamia is more text focused, we need to convert "true" to True, "false" to False. Also, case sensitivity is not important.
            print(f"here {value} {type(result.value)}")
            assert result.value == to_bool_non_pythonic(value)
        elif isinstance(value, str): # Some parsers, for example HTML parser, parse numbers as strings that's why we need to convert them to the expected type even in strict mode
            # Also, this logic of TypeMatcher is similar to Python's behaviour where int("123") where it allows to convert a string to an int, but int(123.45) fails and is not allowed
            assert result.value == expected_type(value) # value should be converted to the expected type in strict mode when it is a string
        else:
            assert result.value == value # value should be returned as is in strict mode for values other than strings
    
    assert result.error is None if should_match else not None


def to_bool_non_pythonic(value: str) -> bool:
    return value.strip().lower() == "true"

# Strict not strict type checking tests are sperated because for each setup only one mode should be used.
@pytest.mark.parametrize("expected_type,value,should_match,resulted_value", [
    (int, 123, True, 123),
    (int, "123", True, 123),
    (int, 123.0, True, 123),
    (int, "123.0", True, 123),
    (float, 123.45, True, 123.45),
    (float, "123.45", True, 123.45),
    (float, 123, True, 123),
    (float, "123", True, 123),
    (bool, True, True, True),
    (bool, False, True, False),
    (bool, "true", True, True),
    (bool, "false", True, False),
    (bool, "1", True, True),
    (bool, "0", True, False),
    (str, "hello", True, "hello"),
    (str, 123, True, "123"),
    (str, 123.45, True, "123.45"),
    (typing.Any, "anything", True, "anything"),
    (typing.Any, 123, True, 123),
    (list, [], True, []),
    (list, [1, 2, 3], True, [1, 2, 3]),
    (list, [1, 2, 3.0, "4"], True, [1, 2, 3, "4"]),
    (list, {"a": 1}, False, None),
    (dict, {}, True, {}),
    (dict, {"a": 1}, True, {"a": 1}),
    (dict, [1, 2, 3], False, None),
    (typing.Union[int, str], 123, True, 123),
    (typing.Union[int, str], "abc", True, "abc"),
    (typing.Union[int, str], 123.45, True, 123),
])
def test_type_matcher_not_strict(expected_type, value, should_match, resulted_value):
    matcher = TypeMatcher(strict=False)
    result = matcher.validate_and_convert(value, expected_type)
    assert result.is_valid == should_match
    assert result.value == resulted_value
    assert result.error is None if should_match else not None

@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("expected_type,value,should_match_strict,should_match_not_strict", [
    (int, None, False, False),
    (typing.Any, None, True, True),
    (typing.Optional[int], None, True, True),
    (typing.Optional[typing.Any], None, True, True),
])
def test_type_matcher_null_values(expected_type, value, should_match_strict, should_match_not_strict, strict):
    matcher = TypeMatcher(strict=strict)
    result = matcher.validate_and_convert(value, expected_type)
    if strict:
        assert result.is_valid == should_match_strict
    else:
        assert result.is_valid == should_match_not_strict
    assert result.value is None
    assert result.error is None