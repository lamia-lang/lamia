# NOTE: Type checking logic is now tested in unit tests for TypeMatcher. These tests remain as integration tests for file structure validators.
import pytest
from pydantic import BaseModel
from lamia.adapters.llm.validation.validators.file_validators import *
from typing import Any, List, Dict, Type, Tuple

# Test Models
class ItemModel(BaseModel):
    id: int
    name: str

class NestedListsModel(BaseModel):
    simple_list: List[int]
    nested_list: List[List[int]]
    deep_nested_list: List[List[List[int]]]
    list_of_objects: List[ItemModel]
    mixed_nesting: Dict[str, List[List[int]]]

# Valid test data for different formats
YAML_VALID_CONTENT = """
simple_list: [1, 2, 3]
nested_list:
  - [1, 2, 3]
  - [4, 5, 6]
deep_nested_list:
  - [[1, 2], [3, 4]]
  - [[5, 6], [7, 8]]
list_of_objects:
  - id: 1
    name: "Item 1"
  - id: 2
    name: "Item 2"
mixed_nesting:
  key1: [[1, 2], [3, 4]]
  key2: [[5, 6], [7, 8]]
"""

JSON_VALID_CONTENT = """
{
    "simple_list": [1, 2, 3],
    "nested_list": [[1, 2, 3], [4, 5, 6]],
    "deep_nested_list": [[[1, 2], [3, 4]], [[5, 6], [7, 8]]],
    "list_of_objects": [
        {"id": 1, "name": "Item 1"},
        {"id": 2, "name": "Item 2"}
    ],
    "mixed_nesting": {
        "key1": [[1, 2], [3, 4]],
        "key2": [[5, 6], [7, 8]]
    }
}
"""

# Invalid test data for different formats
YAML_INVALID_CONTENT = """
simple_list: not_a_list
nested_list:
  - [1, "invalid"]
  - [4, 5, 6]
deep_nested_list:
  - [[1, 2], [3, 4]]
  - not_a_list
list_of_objects:
  - id: not_an_int
    name: "Item 1"
  - id: 2
    name: "Item 2"
mixed_nesting:
  key1: not_a_list
  key2: [[5, 6], [7, 8]]
"""

JSON_INVALID_CONTENT = """
{
    "simple_list": "not_a_list",
    "nested_list": [[1, "invalid"], [4, 5, 6]],
    "deep_nested_list": [[[1, 2], [3, 4]], "invalid"],
    "list_of_objects": [
        {"id": "not_an_int", "name": "Item 1"},
        {"id": 2, "name": "Item 2"}
    ],
    "mixed_nesting": {
        "key1": "not_a_list",
        "key2": [[5, 6], [7, 8]]
    }
}
"""

# TODO: Think about supporting non-native user defined lists in XML files, ul-s, ol-s with li-s in HTML files, etc.
FILE_CONTENT_VALIDATOR_PAIR_WITH_NESTED_TYPES = [
    (YAML_VALID_CONTENT, YAMLStructureValidator),
    (JSON_VALID_CONTENT, JSONStructureValidator),
]

FILE_CONTENT_VALIDATOR_PAIR_WITH_INVALID_NESTED_TYPES = [
    (YAML_INVALID_CONTENT, YAMLStructureValidator),
    (JSON_INVALID_CONTENT, JSONStructureValidator),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("file_content, validator_class", FILE_CONTENT_VALIDATOR_PAIR_WITH_NESTED_TYPES)
async def test_nested_collections(strict: bool, file_content: str, validator_class):
    """Test nested collections validation for different file formats."""
    validator = validator_class(model=NestedListsModel, strict=strict)
    
    # Test valid content
    result = await validator.validate(file_content)
    assert result.is_valid is True, f"Valid content should be accepted for {validator_class.__name__}"
    
    # Verify the parsed structure
    parsed_data = result.result_type
    assert isinstance(parsed_data.simple_list, list), "simple_list should be a list"
    assert isinstance(parsed_data.nested_list[0], list), "nested_list should be a 2D list"
    assert isinstance(parsed_data.deep_nested_list[0][0], list), "deep_nested_list should be a 3D list"
    assert isinstance(parsed_data.list_of_objects[0], ItemModel), "list_of_objects should contain ItemModel instances"
    assert isinstance(parsed_data.mixed_nesting["key1"], list), "mixed_nesting should contain lists"
    
    # Verify values
    assert parsed_data.simple_list == [1, 2, 3], "simple_list values should match"
    assert parsed_data.nested_list[0] == [1, 2, 3], "nested_list values should match"
    assert parsed_data.deep_nested_list[0][0] == [1, 2], "deep_nested_list values should match"
    assert parsed_data.list_of_objects[0].id == 1, "list_of_objects values should match"
    assert parsed_data.mixed_nesting["key1"][0] == [1, 2], "mixed_nesting values should match"

@pytest.mark.asyncio
@pytest.mark.parametrize("file_content, validator_class", FILE_CONTENT_VALIDATOR_PAIR_WITH_INVALID_NESTED_TYPES)
async def test_invalid_nested_collections(file_content: str, validator_class):
    """Test invalid nested collections for different file formats."""
    validator = validator_class(model=NestedListsModel, strict=True)
    result = await validator.validate(file_content)
    assert result.is_valid is False, f"Invalid content should be rejected for {validator_class.__name__}"
    