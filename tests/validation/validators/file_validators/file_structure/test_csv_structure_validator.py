import pytest
from enum import Enum
from pydantic import BaseModel, Field
from lamia.validation.validators.file_validators.file_structure.csv_structure_validator import CSVStructureValidator
from lamia.validation.base import ValidationResult
from collections import OrderedDict

# The tests that are common to all file structure validators should go to multi_file_format folder
# Tests exclusive to CSV format should go here

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

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
    assert result.error_message == "Duplicate header found: dup_header"
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

class CSVModelWithOrderedFields(BaseModel):
    name: str
    age: int
    
    # These fields must maintain order in CSV
    __ordered_fields__ = OrderedDict([
        ("col1", int),
        ("col2", str),
    ])

class TestCSVStructureAppend:

    def test_strips_model_header_when_file_has_content(self) -> None:
        validator = CSVStructureValidator(model=SimpleModel)
        existing = "title,value\nTest,123\n"
        new = "title,value\nFoo,456\n"
        result = validator.prepare_content_for_write(existing, new)
        assert result == "title,value\nTest,123\nFoo,456\n"

    def test_keeps_header_on_empty_file(self) -> None:
        validator = CSVStructureValidator(model=SimpleModel)
        result = validator.prepare_content_for_write("", "title,value\nTest,123\n")
        assert result == "title,value\nTest,123\n"

    def test_header_only_new_content_returns_existing(self) -> None:
        validator = CSVStructureValidator(model=SimpleModel)
        result = validator.prepare_content_for_write("title,value\nTest,123\n", "title,value")
        assert result == "title,value\nTest,123\n"

    def test_no_model_strips_duplicate_header(self) -> None:
        validator = CSVStructureValidator(model=None)
        existing = "a,b\n1,2\n"
        new = "a,b\n3,4\n"
        result = validator.prepare_content_for_write(existing, new)
        assert result == "a,b\n1,2\n3,4\n"

    def test_non_matching_header_plain_concatenation(self) -> None:
        validator = CSVStructureValidator(model=SimpleModel)
        existing = "title,value\nTest,123\n"
        new = "other,cols\nFoo,456\n"
        result = validator.prepare_content_for_write(existing, new)
        assert result == "title,value\nTest,123\nother,cols\nFoo,456\n"

    def test_no_model_inserts_row_separator_when_existing_has_no_trailing_newline(self) -> None:
        validator = CSVStructureValidator(model=None)
        existing = "a,b\n1,2\n3,4"
        new = "a,b\n5,6\n7,8\n"
        result = validator.prepare_content_for_write(existing, new)
        assert result == "a,b\n1,2\n3,4\n5,6\n7,8\n"


def test_csv_order_validation_in_extract_payload():
    """Test that CSV validator properly validates field order during extraction"""
    validator = CSVStructureValidator(model=CSVModelWithOrderedFields, strict=True, generate_hints=True)
    
    # Valid cases - ordered fields maintain relative order
    valid_cases = [
        "name,col1,age,col2\nJohn,1,25,test",  # Ordered fields in correct order
        "col1,col2,name,age\n1,test,John,25",  # Ordered fields first
        "name,age,col1,col2\nJohn,25,1,test",  # Ordered fields at end
        "col1,name,col2,age\n1,John,test,25",  # Ordered fields separated but in order
    ]
    
    # Invalid cases - ordered fields in wrong relative order  
    invalid_cases = [
        "name,col2,age,col1\nJohn,test,25,1",  # Ordered fields reversed
        "col2,col1,name,age\ntest,1,John,25",  # Ordered fields completely reversed
        "name,age,col2,col1\nJohn,25,test,1",  # Ordered fields at end but reversed
    ]


@pytest.mark.asyncio
async def test_csv_validates_single_bad_row_reports_exact_row():
    validator = CSVStructureValidator(model=SimpleModel, strict=True, generate_hints=True)
    result = await validator.validate("title,value\nAlpha,1\nBeta,2\nGamma,not_a_number")
    assert not result.is_valid
    assert result.error_message == "Row 3, field 'value': Cannot strictly convert 'not_a_number' to int"
    

@pytest.mark.asyncio
async def test_csv_validates_every_row_bad_reports_all():
    validator = CSVStructureValidator(model=SimpleModel, strict=True, generate_hints=True)
    result = await validator.validate("title,value\nA,x\nB,y\nC,z")
    assert not result.is_valid
    assert "Row 1" in result.error_message
    assert "Row 2" in result.error_message
    assert "Row 3" in result.error_message


@pytest.mark.asyncio
async def test_csv_validates_required_fields_in_later_rows():
    validator = CSVStructureValidator(model=SimpleModel, strict=True, generate_hints=True)
    result = await validator.validate("title,value\nAlpha,1\n,2\nDelta,4")
    assert not result.is_valid
    assert result.error_message == "Row 2, field 'title' cannot be empty (required field)"


@pytest.mark.asyncio
async def test_csv_all_rows_valid_passes():
    validator = CSVStructureValidator(model=SimpleModel, strict=True, generate_hints=True)
    result = await validator.validate("title,value\nAlpha,1\nBeta,2\nGamma,3")
    assert result.is_valid
    assert result.typed_result.title == "Alpha"
    assert result.typed_result.value == 1


def test_csv_structure_validator_accepts_str_enum():
    class TicketModel(BaseModel):
        title: str
        priority: Priority
        assignee: str

    validator = CSVStructureValidator(model=TicketModel)
    assert validator.model == TicketModel


def test_csv_structure_validator_accepts_int_enum():
    class Severity(int, Enum):
        LOW = 1
        MEDIUM = 2
        HIGH = 3

    class AlertModel(BaseModel):
        message: str
        severity: Severity

    validator = CSVStructureValidator(model=AlertModel)
    assert validator.model == AlertModel


@pytest.mark.asyncio
async def test_csv_enum_validation_rejects_invalid_value():
    class TicketModel(BaseModel):
        title: str
        priority: Priority

    validator = CSVStructureValidator(model=TicketModel, strict=True, generate_hints=True)
    result = await validator.validate("title,priority\nBug fix,urgent")
    assert not result.is_valid
    assert "Invalid enum value" in result.error_message


@pytest.mark.asyncio
async def test_csv_enum_validation_accepts_valid_value():
    class TicketModel(BaseModel):
        title: str
        priority: Priority

    validator = CSVStructureValidator(model=TicketModel, strict=True, generate_hints=True)
    hint = validator.initial_hint
    assert "title: str" in hint
    assert "priority: one of ['low', 'medium', 'high']" in hint
    assert "Priority" not in hint


@pytest.mark.asyncio
async def test_csv_enum_validation_rejects_invalid_value():
    class TicketModel(BaseModel):
        title: str
        priority: Priority

    validator = CSVStructureValidator(model=TicketModel, strict=True, generate_hints=True)
    result = await validator.validate("title,priority\nBug fix,urgent")
    assert not result.is_valid
    assert result.error_message == "Row 1, field 'priority': Invalid enum value 'urgent' for Priority. Valid values are: ['low', 'medium', 'high']"


@pytest.mark.asyncio
async def test_csv_enum_validation_accepts_valid_value():
    class TicketModel(BaseModel):
        title: str
        priority: Priority

    validator = CSVStructureValidator(model=TicketModel, strict=True, generate_hints=True)
    result = await validator.validate("title,priority\nBug fix,high")
    assert result.is_valid
    assert result.typed_result.title == "Bug fix"
    assert result.typed_result.priority == Priority.HIGH


def test_csv_duplicate_header_error_message_not_file_scoped_sync():
    import asyncio

    class DupHeaderModel(BaseModel):
        dup_header: str

    csv = "dup_header;dup_header;\ncell1;cell2;\ncell3;cell4;"
    validator = CSVStructureValidator(model=DupHeaderModel, strict=False)
    result = asyncio.run(validator.validate(csv))
    assert result.is_valid is False
    assert result.error_message == "Duplicate header found: dup_header"
