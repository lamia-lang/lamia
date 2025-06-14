import pytest
from lamia.adapters.llm.validation.utlis.type_matcher import TypeMatcher
import typing

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

# Strict not strict type checking tests are sperated because for each setup only one mode should be used.
@pytest.mark.parametrize("expected_type,value,should_match", [
    (int, 123, True),
    (int, "123", True),
    (int, 123.0, True),
    (int, "123.0", True),
    (float, 123.45, True),
    (float, "123.45", True),
    (float, 123, True),
    (float, "123", True),
    (bool, True, True),
    (bool, False, True),
    (bool, "true", True),
    (bool, "false", True),
    (bool, "1", True),
    (bool, "0", True),
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
    (typing.Union[int, str], 123.45, True),
])
def test_type_matcher_not_strict(expected_type, value, should_match):
    matcher = TypeMatcher(strict=False)
    result = matcher.validate_and_convert(value, expected_type)
    assert result.is_valid == should_match

@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("expected_type,value,should_match_strict,should_match_not_strict", [
    (int, None, False, True),
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