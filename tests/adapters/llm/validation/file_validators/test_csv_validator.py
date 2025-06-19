import pytest
from pydantic import BaseModel
from lamia.adapters.llm.validation.validators.file_validators import CSVStructureValidator

class SimpleModel(BaseModel):
    title: str
    value: int

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_csv_structure_validator_type_validity(strict):
    validator = CSVStructureValidator(model=SimpleModel, strict=strict)
    valid_csv = 'title,value\nTest,123\nFoo,456\n'
    invalid_csv = 'title,value\nTest,abc\nFoo,456\n'
    result = await validator.validate(valid_csv)
    assert result.is_valid is True, f"Expected valid CSV to pass in {'strict' if strict else 'permissive'} mode, got: {result}"
    result = await validator.validate(invalid_csv)
    assert result.is_valid is False, f"Expected invalid CSV to fail in {'strict' if strict else 'permissive'} mode, got: {result}"

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_csv_structure_validator_type_validity_semicolon_separator(strict):
    validator = CSVStructureValidator(model=SimpleModel, strict=strict)
    valid_csv = 'title;value\nTest;123\nFoo;456\n'
    invalid_csv = 'title;value\nTest;abc\nFoo;456\n'
    result = await validator.validate(valid_csv)
    assert result.is_valid is True, f"Expected valid semicolon-separated CSV to pass in {'strict' if strict else 'permissive'} mode, got: {result}"
    result = await validator.validate(invalid_csv)
    assert result.is_valid is False, f"Expected invalid semicolon-separated CSV to fail in {'strict' if strict else 'permissive'} mode, got: {result}"

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

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_csv_structure_validator_missing_fields(strict):
    validator = CSVStructureValidator(model=SimpleModel, strict=strict)
    invalid_csv = 'title\nTest\nFoo\n'
    result = await validator.validate(invalid_csv)
    assert result.is_valid is False, f"Expected CSV with missing fields to fail in {'strict' if strict else 'permissive'} mode, got: {result}"

