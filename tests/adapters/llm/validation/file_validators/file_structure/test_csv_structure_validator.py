import pytest
from pydantic import BaseModel
from lamia.adapters.llm.validation.validators.file_validators import CSVStructureValidator

# The tests that are common to all file structure validators should go to multi_file_format folder
# Tests exclusive to CSV format should go here

class SimpleModel(BaseModel):
    title: str
    value: int

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
async def test_file_structure_validator_should_select_first_when_many_fields_with_same_name(strict, file_content, validator_class):
    class DupHeaderModel(BaseModel):
      dup_header: str

    csv = "dup_header;dup_header;\ncell1;\ncell2;cell3;cell4"

    validator = CSVStructureValidator(model=DupHeaderModel, strict=False)
    result = await validator.validate(csv)
    assert result.is_valid is False
    assert result.error_message == "Duplicate header 'dup_header'"
    assert result.hint == "Duplicate header 'dup_header'. Duplicate headers are not supported please return the results in 'dup_header' column."

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

