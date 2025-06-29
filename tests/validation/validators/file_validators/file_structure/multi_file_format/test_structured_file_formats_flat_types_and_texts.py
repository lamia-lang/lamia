# NOTE: Type checking logic is now tested in unit tests for TypeMatcher. These tests remain as integration tests for file structure validators.
import pytest
from pydantic import BaseModel
from lamia.validation.validators.file_validators import *
from typing import Any, Optional

FILE_CONTENT_VALIDATOR_PAIR_WITH_PRIMITIVES_TYPES = [
    (
        '<html><title>Test</title><myboolen>true</myboolen><myint>123</myint><myfloat>123.45</myfloat></html>',
        HTMLStructureValidator,
    ),
    (
        '<root><title>Test</title><myboolen>true</myboolen><myint>123</myint><myfloat>123.45</myfloat></root>',
        XMLStructureValidator,
    ),
    (
        '{"title": "Test", "myboolen": true, "myint": 123, "myfloat": 123.45}',
        JSONStructureValidator,
    ),
    (
        'title: Test\nmyboolen: true\nmyint: 123\nmyfloat: 123.45\n',
        YAMLStructureValidator,
    ),
    (
        'title,myboolen,myint,myfloat\nTest,true,123,123.45',
        CSVStructureValidator,
    ),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("file_content, validator_class", FILE_CONTENT_VALIDATOR_PAIR_WITH_PRIMITIVES_TYPES)
async def test_file_structure_validator_primitives_should_be_valid_strings(strict, file_content, validator_class):
    class ModelWithPrimitiveTypesAsStrings(BaseModel):
        title: str
        myboolen: str
        myint: str
        myfloat: str

    validator = validator_class(model=ModelWithPrimitiveTypesAsStrings, strict=strict)  
    result = await validator.validate(file_content)
    assert result.result_type.title == "Test"
    assert result.result_type.myboolen.lower() == "true"
    assert result.result_type.myint == "123"
    assert result.result_type.myfloat == "123.45"

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("file_content, validator_class", FILE_CONTENT_VALIDATOR_PAIR_WITH_PRIMITIVES_TYPES)
async def test_file_structure_validator_primitives_same_type_casting_should_be_valid(strict, file_content, validator_class):
    class ModelWithPrimitiveTypes(BaseModel):
        title: str
        myboolen: bool
        myint: int
        myfloat: float

    validator = validator_class(model=ModelWithPrimitiveTypes, strict=strict)
    result = await validator.validate(file_content)
    print(result)
    assert result.is_valid is True, f"result should be valid: {result}"
    # Check that result_type is a filled Pydantic model and fields match
    assert isinstance(result.result_type, ModelWithPrimitiveTypes), f"result_type should be ModelWithPrimitiveTypes, got {type(result.result_type)}"
    assert result.result_type.title == "Test"
    assert result.result_type.myboolen is True or result.result_type.myboolen == True  # Accept bool True
    assert result.result_type.myint == 123
    assert abs(result.result_type.myfloat - 123.45) < 1e-6 

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("file_content, validator_class", FILE_CONTENT_VALIDATOR_PAIR_WITH_PRIMITIVES_TYPES)
async def test_file_structure_validator_possible_cross_numeric_type_validation_should_be_valid(strict, file_content, validator_class):
    class ModelWithPrimitiveTypes(BaseModel):
        title: str
        myboolen: bool
        myint: float
        myfloat: int

    validator = validator_class(model=ModelWithPrimitiveTypes, strict=strict)
    result = await validator.validate(file_content)
    assert result.is_valid is True, f"result should be valid: {result}"
    assert result.result_type.title == "Test"
    assert result.result_type.myboolen is True or result.result_type.myboolen == True  # Accept bool True
    assert abs(result.result_type.myint - 123.00) < 1e-6 
    assert result.result_type.myfloat == 123

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("file_content, validator_class", [
    ("", HTMLStructureValidator),
    ("", XMLStructureValidator),
    ("", JSONStructureValidator),
    ("", YAMLStructureValidator),
    ("", CSVStructureValidator),
])
async def test_file_structure_validator_empty_text(strict, file_content, validator_class):
    class Model(BaseModel):
      val1: Any
      val2: Any

    validator = validator_class(model=Model, strict=strict)
    result = await validator.validate(file_content)
    assert result.is_valid is False

# If users want fixed order of fields even for the stric mode, they can use OrderedDict type.
# see *_validator_ordered_fields_* tests for more details
@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("file_content, validator_class", FILE_CONTENT_VALIDATOR_PAIR_WITH_PRIMITIVES_TYPES)
async def test_file_structure_validator_type_order_mismatch(strict, file_content, validator_class):
    class OneToOneMatchingModelWithWrongOrder(BaseModel):
        myfloat: float
        myint: int
        myboolen: bool
        title: str

    validator = validator_class(model=OneToOneMatchingModelWithWrongOrder, strict=strict)
    result = await validator.validate(file_content)
    assert result.is_valid is True

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("file_content, validator_class", FILE_CONTENT_VALIDATOR_PAIR_WITH_PRIMITIVES_TYPES)
async def test_file_structure_validator_additional_fields(strict, file_content, validator_class):
    class ModelWithAdditionalFields(BaseModel):
        title: str
        myboolen: bool
        myint: int
        myfloat: float
        extra: str

    validator = validator_class(model=ModelWithAdditionalFields, strict=strict)
    result = await validator.validate(file_content)
    assert result.is_valid is False, f"extra str field should be invalid: {result}"

    class ModelWithAdditionalFields(BaseModel):
        title: str
        myboolen: bool
        myint: int
        myfloat: float
        extra_any_is_for_non_null_types_only: Any # Check test_type_matcher for contract tests about Any

    validator = validator_class(model=ModelWithAdditionalFields, strict=strict)
    result = await validator.validate(file_content)
    assert result.is_valid is False, f"extra Any field should be invalid: {result}"

    class ModelWithAdditionalFields(BaseModel):
        title: str
        myboolen: bool
        myint: int
        myfloat: float
        optional_extra: Optional[Any]
        optional_extra: Optional[str]

    validator = validator_class(model=ModelWithAdditionalFields, strict=strict)
    result = await validator.validate(file_content)
    assert result.is_valid is True

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("file_content, validator_class", FILE_CONTENT_VALIDATOR_PAIR_WITH_PRIMITIVES_TYPES)
async def test_file_structure_validator_missing_fields(strict, file_content, validator_class):
    class ModelWithMissingFields(BaseModel):
        title: str
        myboolen: bool
        myint: int

    validator = validator_class(model=ModelWithMissingFields, strict=strict)
    result = await validator.validate(file_content)
    assert result.is_valid is True


@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("file_content, validator_class", FILE_CONTENT_VALIDATOR_PAIR_WITH_PRIMITIVES_TYPES)
async def test_file_structure_validator_ordered_fields_correct_order(strict, file_content, validator_class):
    from collections import OrderedDict

    validator = validator_class(model=OrderedDict([
            ("title", str),
            ("myboolen", bool),
            ("myint", int),
            ("myfloat", float),
        ]), strict=strict)
    result = await validator.validate(file_content)
    # Should fail if fields are in different order than declared
    assert result.is_valid is True
    assert isinstance(result.result_type, OrderedDict)
    assert result.result_type["title"] == "Test"
    assert result.result_type["myboolen"] is True or result.result_type["myboolen"] == True  # Accept bool True
    assert result.result_type["myint"] == 123
    assert abs(result.result_type["myfloat"] - 123.45) < 1e-6 

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("file_content, validator_class", FILE_CONTENT_VALIDATOR_PAIR_WITH_PRIMITIVES_TYPES)
async def test_file_structure_validator_ordered_fields_incorrect_order(strict, file_content, validator_class):
    from collections import OrderedDict

    # incorrect order
    validator = validator_class(model=OrderedDict([
            ("myint", int),
            ("title", str),
            ("myfloat", float),
            ("myboolen", bool)
        ]), strict=strict)
    result = await validator.validate(file_content)
    # Should fail if fields are in different order than declared
    assert result.is_valid is False
    assert "field order" in result.error_message.lower()
