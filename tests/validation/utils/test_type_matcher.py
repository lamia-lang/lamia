import pytest
from enum import Enum
from lamia.validation.utils.type_matcher import TypeMatcher
import typing
from typing import get_origin
from lamia.validation.utils.error_messages import (
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
import re
from pydantic import constr, conint, confloat, conlist

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
    (str, 123, True, None),
    (str, 123.45, True, None),
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
    (dict[str, int], {"a": -1, "b": 1.1, 1:2.2}, False, error_msg_dict_elements_invalid({}, {1.1: error_msg_cannot_strictly_convert(1.1, "int"), 2.2: error_msg_cannot_strictly_convert(2.2, "int")})),
    (typing.Union[int, str], 123, True, None),
    (typing.Union[int, str], "abc", True, None),
    (typing.Union[int, bool], 123.45, False, error_msg_cannot_convert_to_any_of(123.45, (int, bool))),
])
def test_type_matcher_strict(expected_type, value, should_match, expected_error):
    matcher = TypeMatcher(strict=True)
    result = matcher.validate_and_convert(value, expected_type)
    assert result.is_valid == should_match
    
    if should_match:
        if expected_type is typing.Any:
            assert result.value == value
        elif expected_type is str:
            assert result.value == str(value)
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

# Info Loss Tracking Tests
class TestInfoLossTracking:
    """Test info_loss tracking for information-losing type conversions."""
    
    def test_float_to_int_info_loss(self):
        """Test that float to int conversion tracks decimal loss."""
        matcher = TypeMatcher(strict=False)
        result = matcher.validate_and_convert(3.14159, int)
        
        assert result.is_valid is True
        assert result.value == 3
        assert result.info_loss == {
            "conversion": "float -> int",
            "original_value": 3.14159,
            "converted_value": 3,
            "lost_decimal": 3.14159 - 3
        }
    
    def test_float_to_int_no_loss_when_whole_number(self):
        """Test that float to int conversion with no decimal part has no info_loss."""
        matcher = TypeMatcher(strict=False)
        result = matcher.validate_and_convert(5.0, int)
        
        assert result.is_valid is True
        assert result.value == 5
        assert result.info_loss == {}  # No info loss when decimal is 0
    
    def test_string_decimal_to_int_info_loss(self):
        """Test that string with decimal to int conversion tracks loss."""
        matcher = TypeMatcher(strict=False)
        result = matcher.validate_and_convert("42.789", int)
        
        assert result.is_valid is True
        assert result.value == 42
        assert result.info_loss == {
            "conversion": "str -> float -> int",
            "original_value": "42.789",
            "intermediate_float": 42.789,
            "converted_value": 42,
            "lost_decimal": 42.789 - 42
        }
    
    def test_string_whole_number_to_int_no_loss(self):
        """Test that string whole number to int has no info_loss."""
        matcher = TypeMatcher(strict=False)
        result = matcher.validate_and_convert("42.0", int)
        
        assert result.is_valid is True
        assert result.value == 42
        assert result.info_loss == {}  # No info loss when decimal is 0
    
    def test_direct_string_int_to_int_no_loss(self):
        """Test that direct string int to int has no info_loss."""
        matcher = TypeMatcher(strict=False)
        result = matcher.validate_and_convert("42", int)
        
        assert result.is_valid is True
        assert result.value == 42
        assert result.info_loss == {}  # No conversion needed
    
    def test_int_to_str_type_change_info_loss(self):
        """Test that int to string conversion tracks type change."""
        matcher = TypeMatcher(strict=False)
        result = matcher.validate_and_convert(123, str)
        
        assert result.is_valid is True
        assert result.value == "123"
        assert result.info_loss == {
            "conversion": "int -> str",
            "original_value": 123,
            "original_type": "int"
        }
    
    def test_float_to_str_type_change_info_loss(self):
        """Test that float to string conversion tracks type change."""
        matcher = TypeMatcher(strict=False)
        result = matcher.validate_and_convert(3.14, str)
        
        assert result.is_valid is True
        assert result.value == "3.14"
        assert result.info_loss == {
            "conversion": "float -> str",
            "original_value": 3.14,
            "original_type": "float"
        }
    
    def test_no_conversion_no_info_loss(self):
        """Test that no conversion means no info_loss."""
        matcher = TypeMatcher(strict=False)
        result = matcher.validate_and_convert(42, int)
        
        assert result.is_valid is True
        assert result.value == 42
        assert result.info_loss == {}
    
    def test_list_with_info_loss_conversions(self):
        """Test that list conversions collect info_loss from elements."""
        matcher = TypeMatcher(strict=False)
        result = matcher.validate_and_convert([1.5, 2.7, 3], list[int])
        
        assert result.is_valid is True
        assert result.value == [1, 2, 3]
        
        # Check that info_loss is collected from elements that had conversions
        assert "element_0" in result.info_loss
        assert result.info_loss["element_0"]["conversion"] == "float -> int"
        assert result.info_loss["element_0"]["original_value"] == 1.5
        assert abs(result.info_loss["element_0"]["lost_decimal"] - 0.5) < 1e-10
        
        assert "element_1" in result.info_loss
        assert result.info_loss["element_1"]["conversion"] == "float -> int"
        assert result.info_loss["element_1"]["original_value"] == 2.7
        assert abs(result.info_loss["element_1"]["lost_decimal"] - 0.7) < 1e-10
        
        # Element 2 had no conversion, so no info_loss recorded
        assert "element_2" not in result.info_loss
    
    def test_dict_with_info_loss_conversions(self):
        """Test that dict conversions collect info_loss from keys and values."""
        matcher = TypeMatcher(strict=False)
        result = matcher.validate_and_convert({123: 4.5, "hello": 6}, dict[str, int])
        
        assert result.is_valid is True
        assert result.value == {"123": 4, "hello": 6}
        
        # Check key conversion info_loss
        assert "key_123" in result.info_loss
        assert result.info_loss["key_123"]["conversion"] == "int -> str"
        assert result.info_loss["key_123"]["original_value"] == 123
        
        # Check value conversion info_loss  
        assert "value_123" in result.info_loss
        assert result.info_loss["value_123"]["conversion"] == "float -> int"
        assert result.info_loss["value_123"]["original_value"] == 4.5
        assert abs(result.info_loss["value_123"]["lost_decimal"] - 0.5) < 1e-10
        
        # No info_loss for value that didn't need conversion
        assert "value_hello" not in result.info_loss
    
    def test_strict_mode_no_info_loss_on_rejection(self):
        """Test that strict mode doesn't track info_loss when conversion is rejected."""
        matcher = TypeMatcher(strict=True)
        result = matcher.validate_and_convert(3.14, int)
        
        assert result.is_valid is False
        assert result.info_loss == {}  # No info_loss when conversion fails
    
    def test_nested_list_info_loss_collection(self):
        """Test that nested collections properly collect info_loss."""
        matcher = TypeMatcher(strict=False)
        # List of lists with float to int conversions
        result = matcher.validate_and_convert([[1.5, 2], [3.7]], list[list[int]])
        
        assert result.is_valid is True
        assert result.value == [[1, 2], [3]]
        
        # Should collect info_loss from nested conversions
        assert "element_0" in result.info_loss
        assert "element_1" in result.info_loss

    def test_deeply_nested_list_info_loss(self):
        """Test info_loss tracking in deeply nested lists."""
        matcher = TypeMatcher(strict=False)
        # List of lists of lists with conversions
        nested_data = [[[1.5, 2.3], [3]], [[4.7, 5], [6.1]]]
        result = matcher.validate_and_convert(nested_data, list[list[list[int]]])
        
        assert result.is_valid is True
        assert result.value == [[[1, 2], [3]], [[4, 5], [6]]]
        
        # Check that info_loss is properly nested
        assert "element_0" in result.info_loss
        assert "element_1" in result.info_loss
        
        # Check nested structure of info_loss
        elem_0_info = result.info_loss["element_0"]
        assert "element_0" in elem_0_info  # [[1.5, 2.3], [3]]
        assert "element_1" not in elem_0_info  # [3] has no conversions
        
        # Check the deepest level
        elem_0_0_info = elem_0_info["element_0"]
        assert "element_0" in elem_0_0_info  # 1.5 -> 1
        assert "element_1" in elem_0_0_info  # 2.3 -> 2
        assert elem_0_0_info["element_0"]["original_value"] == 1.5
        assert elem_0_0_info["element_1"]["original_value"] == 2.3

    def test_dict_of_lists_info_loss(self):
        """Test info_loss tracking in dict containing lists with conversions."""
        matcher = TypeMatcher(strict=False)
        data = {
            "integers": [1.5, 2.7, 3],
            "floats": [42.3, 85.7, 99.0]
        }
        result = matcher.validate_and_convert(data, dict[str, list[int]])
        
        assert result.is_valid is True
        assert result.value == {"integers": [1, 2, 3], "floats": [42, 85, 99]}
        
        # Check info_loss structure
        assert "value_integers" in result.info_loss
        assert "value_floats" in result.info_loss
        
        # Check integers list info_loss
        integers_info = result.info_loss["value_integers"]
        assert "element_0" in integers_info  # 1.5 -> 1
        assert "element_1" in integers_info  # 2.7 -> 2
        assert "element_2" not in integers_info  # 3 no conversion
        
        # Check floats list info_loss
        floats_info = result.info_loss["value_floats"]
        assert "element_0" in floats_info  # 42.3 -> 42
        assert "element_1" in floats_info  # 85.7 -> 85
        assert "element_2" not in floats_info  # 99.0 -> 99 (no decimal lost)

    def test_list_of_dicts_info_loss(self):
        """Test info_loss tracking in list containing dicts with conversions."""
        matcher = TypeMatcher(strict=False)
        data = [
            {"id": 1.0, "count": 123, "score": 85.7},
            {"id": 2.5, "count": 456, "score": 92.0}
        ]
        result = matcher.validate_and_convert(data, list[dict[str, int]])
        
        assert result.is_valid is True
        assert result.value == [
            {"id": 1, "count": 123, "score": 85},
            {"id": 2, "count": 456, "score": 92}
        ]
        
        # Check nested info_loss structure
        assert "element_0" in result.info_loss
        assert "element_1" in result.info_loss
        
        # First dict info_loss
        dict_0_info = result.info_loss["element_0"]
        assert "value_id" not in dict_0_info     # 1.0 -> 1 (no decimal lost, so no info_loss)
        assert "value_count" not in dict_0_info  # 123 no conversion
        assert "value_score" in dict_0_info      # 85.7 -> 85
        
        # Second dict info_loss
        dict_1_info = result.info_loss["element_1"]
        assert "value_id" in dict_1_info      # 2.5 -> 2
        assert "value_count" not in dict_1_info  # 456 no conversion
        assert "value_score" not in dict_1_info  # 92.0 -> 92 (no decimal lost)

    def test_complex_nested_structure_info_loss(self):
        """Test info_loss tracking in complex nested structures."""
        matcher = TypeMatcher(strict=False)
        # Dict containing lists of dicts with various conversions
        data = {
            "users": [
                {"id": 1.0, "scores": [85.5, 90.2, 88]},
                {"id": 2.7, "scores": [92.1, 87.8]}
            ],
            "metadata": {
                "count": 2.0,
                "average": 88.65
            }
        }
        
        # Convert to: dict[str, list[dict[str, list[int]]]] for users, 
        # but let's use a simpler target type for this test
        result = matcher.validate_and_convert(data, dict[str, dict[str, int]])
        
        # This will fail because the structure doesn't match, but let's test a simpler case
        # Let's test with a flattened version
        flat_data = {
            "user_id": 1.5,
            "score": 85.7,
            "count": 2.0
        }
        result = matcher.validate_and_convert(flat_data, dict[str, int])
        
        assert result.is_valid is True
        assert result.value == {"user_id": 1, "score": 85, "count": 2}
        
        # Check which values have info_loss (only those with actual decimal loss)
        assert "value_user_id" in result.info_loss  # 1.5 -> 1 loses 0.5
        assert "value_score" in result.info_loss    # 85.7 -> 85 loses 0.7
        assert "value_count" not in result.info_loss  # 2.0 -> 2 loses no decimals
        
        # Check specific conversion details
        assert result.info_loss["value_user_id"]["original_value"] == 1.5
        assert result.info_loss["value_user_id"]["lost_decimal"] == 0.5
        assert result.info_loss["value_score"]["original_value"] == 85.7
        assert abs(result.info_loss["value_score"]["lost_decimal"] - 0.7) < 1e-10

    def test_mixed_conversion_types_in_nested_structure(self):
        """Test various conversion types within nested structures."""
        matcher = TypeMatcher(strict=False)
        data = {
            "float_to_int": [1.5, 2.7],
            "int_to_str": [123, 456],
            "mixed_to_str": [789, 3.14, "hello"]
        }
        
        expected_result = dict[str, list[str]]
        result = matcher.validate_and_convert(data, expected_result)
        
        assert result.is_valid is True
        assert result.value == {
            "float_to_int": ["1.5", "2.7"],
            "int_to_str": ["123", "456"], 
            "mixed_to_str": ["789", "3.14", "hello"]
        }
        
        # Check info_loss for different conversion types
        assert "value_float_to_int" in result.info_loss
        assert "value_int_to_str" in result.info_loss
        assert "value_mixed_to_str" in result.info_loss
        
        # Float to string conversions
        float_info = result.info_loss["value_float_to_int"]
        assert "element_0" in float_info
        assert float_info["element_0"]["conversion"] == "float -> str"
        assert float_info["element_0"]["original_value"] == 1.5
        
        # Int to string conversions
        int_info = result.info_loss["value_int_to_str"]
        assert "element_0" in int_info
        assert int_info["element_0"]["conversion"] == "int -> str"
        assert int_info["element_0"]["original_value"] == 123
        
        # Mixed conversions (hello should not appear in info_loss)
        mixed_info = result.info_loss["value_mixed_to_str"]
        assert "element_0" in mixed_info  # 789 -> "789"
        assert "element_1" in mixed_info  # 3.14 -> "3.14"
        assert "element_2" not in mixed_info  # "hello" no conversion

    def test_empty_nested_structures_no_info_loss(self):
        """Test that empty nested structures don't create spurious info_loss entries."""
        matcher = TypeMatcher(strict=False)
        
        # Empty structures
        empty_list_result = matcher.validate_and_convert([], list[int])
        assert empty_list_result.is_valid is True
        assert empty_list_result.value == []
        assert empty_list_result.info_loss == {}
        
        empty_dict_result = matcher.validate_and_convert({}, dict[str, int])
        assert empty_dict_result.is_valid is True
        assert empty_dict_result.value == {}
        assert empty_dict_result.info_loss == {}
        
        # Nested structures with only empty lists (valid conversions)
        nested_empty = {"list1": [], "list2": []}
        nested_result = matcher.validate_and_convert(nested_empty, dict[str, list[int]])
        assert nested_result.is_valid is True
        assert nested_result.value == {"list1": [], "list2": []}
        # No info_loss for empty lists
        assert nested_result.info_loss == {}

@pytest.mark.parametrize("expected_type,value,is_valid,expected_error", [
    # String constraints (valid and invalid)
    (constr(min_length=3), "abcd", True, None),
    (constr(min_length=3), "ab", False, "at least 3 characters"),
    (constr(max_length=5), "abc", True, None),
    (constr(max_length=5), "abcdef", False, "at most 5 characters"),
    (constr(pattern=r"^abc"), "abcde", True, None),
    (constr(pattern=r"^abc"), "def", False, "String should match pattern '^abc'"),
    # Integer constraints (valid and invalid)
    (conint(gt=0), 1, True, None),
    (conint(gt=0), -1, False, "greater than 0"),
    (conint(ge=10), 10, True, None),
    (conint(ge=10), 5, False, "greater than or equal to 10"),
    (conint(lt=100), 99, True, None),
    (conint(lt=100), 150, False, "less than 100"),
    (conint(le=50), 50, True, None),
    (conint(le=50), 51, False, "less than or equal to 50"),
    # Float constraints (valid and invalid)
    (confloat(gt=0.0), 0.1, True, None),
    (confloat(gt=0.0), -0.1, False, "greater than 0"),
    # List constraints (valid and invalid)
    (conlist(int, min_length=2), [1, 2], True, None),
    (conlist(int, min_length=2), [1], False, "at least 2 items"),
    (conlist(int, max_length=2), [1, 2], True, None),
    (conlist(int, max_length=2), [1, 2, 3], False, "at most 2 items"),
])
@pytest.mark.parametrize("strict", [True, False])
def test_type_matcher_field_constraints(expected_type, value, is_valid, expected_error, strict):
    matcher = TypeMatcher(strict=strict)
    result = matcher.validate_and_convert(value, expected_type)

    assert result.is_valid == is_valid
    if not is_valid:
        assert expected_error in result.error
    else:
        assert result.error is None

# Test enums for enum validation tests
class Color(str, Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"

class Status(Enum):
    PENDING = 1
    ACTIVE = 2
    COMPLETED = 3

# Enum Type Conversion Tests
class TestEnumTypeConversion:
    """Test enum type conversion support in TypeMatcher."""

    def test_enum_already_correct_type(self):
        """Test that passing an enum instance of correct type is valid."""
        matcher = TypeMatcher(strict=True)
        result = matcher.validate_and_convert(Color.RED, Color)
        
        assert result.is_valid is True
        assert result.value == Color.RED
        assert result.error is None

    def test_string_enum_value_strict(self):
        """Test conversion from string value to string enum in strict mode."""
        matcher = TypeMatcher(strict=True)
        result = matcher.validate_and_convert("red", Color)
        
        assert result.is_valid is True
        assert result.value == Color.RED
        assert result.error is None

    def test_string_enum_value_strict_rejects_name(self):
        """Strict mode should not match enum names, only values."""
        matcher = TypeMatcher(strict=True)
        result = matcher.validate_and_convert("RED", Color)
        
        assert result.is_valid is False
        assert "RED" in result.error

    def test_string_enum_value_not_strict_case_insensitive(self):
        """Non-strict mode should allow case-insensitive value matching."""
        matcher = TypeMatcher(strict=False)
        result = matcher.validate_and_convert("RED", Color)
        
        assert result.is_valid is True
        assert result.value == Color.RED
        assert result.error is None

    def test_int_enum_from_value(self):
        """Test conversion from int value to int enum."""
        matcher = TypeMatcher(strict=True)
        result = matcher.validate_and_convert(2, Status)
        
        assert result.is_valid is True
        assert result.value == Status.ACTIVE
        assert result.error is None

    def test_enum_invalid_value_strict(self):
        """Test that invalid enum value fails in strict mode."""
        matcher = TypeMatcher(strict=True)
        result = matcher.validate_and_convert("purple", Color)
        
        assert result.is_valid is False
        assert "purple" in result.error
        assert "Color" in result.error

    def test_enum_invalid_value_not_strict(self):
        """Test that invalid enum value fails in non-strict mode too."""
        matcher = TypeMatcher(strict=False)
        result = matcher.validate_and_convert("purple", Status)
        
        assert result.is_valid is False
        assert "purple" in result.error
        assert "Status" in result.error

    def test_enum_wrong_type_for_int_enum(self):
        """Test that wrong type value fails for int enum."""
        matcher = TypeMatcher(strict=True)
        result = matcher.validate_and_convert("not_a_number", Status)
        
        assert result.is_valid is False

    def test_enum_wrong_type_for_int_value(self):
        """Test that wrong type value fails for int enum."""
        matcher = TypeMatcher(strict=True)
        result = matcher.validate_and_convert(9000, Status)
        
        assert result.is_valid is False

        matcher = TypeMatcher(strict=False)
        result = matcher.validate_and_convert(9000, Status)

    def test_enum_list_of_enums(self):
        """Test conversion of list of enum values."""
        matcher = TypeMatcher(strict=True)
        result = matcher.validate_and_convert(["red", "green", "blue"], list[Color])
        
        assert result.is_valid is True
        assert result.value == [Color.RED, Color.GREEN, Color.BLUE]

    def test_enum_list_with_invalid_value(self):
        """Test that list with invalid enum value fails."""
        matcher = TypeMatcher(strict=True)
        result = matcher.validate_and_convert(["red", "purple", "blue"], list[Color])
        
        assert result.is_valid is False

    def test_enum_optional(self):
        """Test Optional enum type."""
        matcher = TypeMatcher(strict=True)
        
        # None should be valid for Optional[Color]
        result = matcher.validate_and_convert(None, typing.Optional[Color])
        assert result.is_valid is True
        assert result.value is None
        
        # Valid value should also work
        result = matcher.validate_and_convert("red", typing.Optional[Color])
        assert result.is_valid is True
        assert result.value == Color.RED

    def test_enum_union(self):
        """Test Union with enum type."""
        matcher = TypeMatcher(strict=True)
        
        # Color value should work
        result = matcher.validate_and_convert("red", typing.Union[Color, str])
        assert result.is_valid is True
        # Should convert to Color first since it comes first in Union
        assert result.value == Color.RED

    def test_enum_wrong_enum_type(self):
        """Test that passing wrong enum type fails."""
        matcher = TypeMatcher(strict=True)
        result = matcher.validate_and_convert(Status.ACTIVE, Color)
        
        assert result.is_valid is False

    @pytest.mark.parametrize("value,expected", [
        (1, Status.PENDING),
        (2, Status.ACTIVE),
        (3, Status.COMPLETED),
    ])
    def test_int_enum_various_values(self, value, expected):
        """Test various int enum conversions."""
        matcher = TypeMatcher(strict=True)
        result = matcher.validate_and_convert(value, Status)
        
        assert result.is_valid is True
        assert result.value == expected