import pytest
from pydantic import BaseModel
from lamia.adapters.llm.validation.validators.file_validators import *

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
    assert result.is_valid is True, f"result should be valid: {result}"

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
    assert result.is_valid is True, f"result should be valid: {result}"

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