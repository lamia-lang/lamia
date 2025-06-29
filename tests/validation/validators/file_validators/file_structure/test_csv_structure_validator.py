import pytest
from pydantic import BaseModel
from lamia.validation.validators.file_validators.file_structure.csv_structure_validator import CSVStructureValidator
from lamia.validation.base import ValidationResult

# The tests that are common to all file structure validators should go to multi_file_format folder
# Tests exclusive to CSV format should go here

class SimpleModel(BaseModel):
    title: str
    value: int

class CSVModel(BaseModel):
    mystr: str
    myint: int
    myfloat: float
    mybool: bool

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_csv_structure_validator_type_validity_colons(strict):
    validator = CSVStructureValidator(model=SimpleModel, strict=strict)
    valid_csv = 'title,value\nTest,123\nFoo,456\n'
    invalid_csv = 'title,value\nTest,abc\nFoo,456\n'
    result = await validator.validate(valid_csv)
    assert result.is_valid is True, f"Expected valid CSV to pass in {'strict' if strict else 'permissive'} mode, got: {result}"
    result = await validator.validate(invalid_csv)
    assert result.is_valid is False, f"Expected invalid CSV to fail in {'strict' if strict else 'permissive'} mode, got: {result}"

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_csv_structure_validator_type_validity_semicolons(strict):
    validator = CSVStructureValidator(model=SimpleModel, strict=strict)
    valid_csv = 'title;value\nTest;123\nFoo;456\n'
    invalid_csv = 'title;value\nTest;abc\nFoo;456\n'
    result = await validator.validate(valid_csv)
    assert result.is_valid is True, f"Expected valid semicolon-separated CSV to pass in {'strict' if strict else 'permissive'} mode, got: {result}"
    result = await validator.validate(invalid_csv)
    assert result.is_valid is False, f"Expected invalid semicolon-separated CSV to fail in {'strict' if strict else 'permissive'} mode, got: {result}"

# Dup headers are currently not supported by CSVStructureValidator
@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_csv_structure_validator_many_fields_with_same_name(strict):
    class DupHeaderModel(BaseModel):
      dup_header: str

    csv = "dup_header;dup_header;\ncell1;cell2;\ncell3;cell4;"

    validator = CSVStructureValidator(model=DupHeaderModel, strict=False)
    result = await validator.validate(csv)
    assert result.is_valid is False
    assert result.error_message == "Invalid file: Duplicate header found 'dup_header'"
    #assert result.hint == "Duplicate header 'dup_header'. Duplicate headers are not supported please return the results in 'dup_header' column."

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_csv_structure_validator_no_header(strict):
    validator = CSVStructureValidator(model=SimpleModel, strict=strict)
    invalid_csv = 'Test,abc\nFoo,456\n'
    result = await validator.validate(invalid_csv)
    assert result.is_valid is False, f"Expected CSV with no header to fail in {'strict' if strict else 'permissive'} mode, got: {result}"

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_csv_structure_validator_missing_cell(strict):
    validator = CSVStructureValidator(model=SimpleModel, strict=strict)
    invalid_csv = 'title,value\nTest,abc\nFoo,\n'
    result = await validator.validate(invalid_csv)
    assert result.is_valid is False, f"Expected CSV with missing cell to fail in {'strict' if strict else 'permissive'} mode, got: {result}"

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_csv_structure_validator_missing_comma(strict):
    validator = CSVStructureValidator(model=SimpleModel, strict=strict)
    invalid_csv = 'title,value\nTest,abc\nFoo\n'
    result = await validator.validate(invalid_csv)
    assert result.is_valid is False, f"Expected CSV with missing comma to fail in {'strict' if strict else 'permissive'} mode, got: {result}"

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_csv_structure_validator_whitespaces(strict):
    validator = CSVStructureValidator(model=SimpleModel, strict=strict)
    csv_with_extra_whitespace = '  title  ,  value  \n  Test  ,  123  \n  Foo  ,  456  \n'
    result = await validator.validate(csv_with_extra_whitespace)
    assert result.is_valid is not strict, f"Expected CSV with extra whitespace to {'fail' if strict else 'pass'} in {'strict' if strict else 'permissive'} mode, got: {result}"

def test_csv_structure_validator_flat_model():
    """Test that CSVStructureValidator works with primitive types only"""
    validator = CSVStructureValidator(model=CSVModel)
    assert validator.model == CSVModel

def test_csv_structure_validator_rejects_non_primitive_model():
    class NonPrimitiveWrongCVSModel(BaseModel):
        name: str
        nested: dict  # This should cause validation to fail
        items: list   # This should also cause validation to fail
        another_model: SimpleModel

    """Test that CSVStructureValidator fails early with non-primitive types"""
    with pytest.raises(ValueError) as exc_info:
        CSVStructureValidator(model=NonPrimitiveWrongCVSModel)
    
    error_message = str(exc_info.value)
    assert "CSV validation only supports primitive types" in error_message
    assert "'nested': dict" in error_message
    assert "'items': list" in error_message
    assert "'another_model': SimpleModel" in error_message

