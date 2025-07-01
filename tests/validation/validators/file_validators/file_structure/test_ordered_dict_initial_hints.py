import pytest
from collections import OrderedDict
from pydantic import BaseModel

from lamia.validation.validators.file_validators.file_structure.csv_structure_validator import CSVStructureValidator
from lamia.validation.utils.pydantic_utils import get_ordered_dict_fields


class CSVModelWithOrderedFields(BaseModel):
    name: str
    age: int
    
    # These fields must maintain order in CSV
    __ordered_fields__ = OrderedDict([
        ("col1", int),
        ("col2", str),
    ])

class CSVModelRegular(BaseModel):
    name: str
    age: int
    salary: float

def test_csv_validator_with_ordered_fields_initial_hint():
    """Test that CSV validator generates proper initial hints for OrderedDict fields"""
    validator = CSVStructureValidator(model=CSVModelWithOrderedFields, strict=True, generate_hints=True)
    hint = validator.initial_hint
    
    # Should contain OrderedDict warning
    assert "IMPORTANT: Fields [col1, col2] require order preservation!" in hint
    assert "CSV columns for these fields must appear in exactly the order shown above" in hint


def test_csv_validator_without_ordered_fields_initial_hint():
    """Test that CSV validator without OrderedDict fields doesn't show order warnings"""
    validator = CSVStructureValidator(model=CSVModelRegular, strict=True, generate_hints=True)
    hint = validator.initial_hint
    
    # Should NOT contain OrderedDict warnings
    assert "order preservation" not in hint
    assert "Fields [" not in hint

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
    
    for csv_content in valid_cases:
        result = validator.extract_payload(csv_content)
        assert result is not None, f"Should accept: {csv_content.split()[0]}"
    
    # Invalid cases - ordered fields in wrong relative order  
    invalid_cases = [
        "name,col2,age,col1\nJohn,test,25,1",  # Ordered fields reversed
        "col2,col1,name,age\ntest,1,John,25",  # Ordered fields completely reversed
        "name,age,col2,col1\nJohn,25,test,1",  # Ordered fields at end but reversed
    ]
    
    for csv_content in invalid_cases:
        result = validator.extract_payload(csv_content)
        assert result is None, f"Should reject: {csv_content.split()[0]}"


@pytest.mark.parametrize("strict", [True, False])
def test_csv_ordered_fields_both_modes(strict):
    """Test that OrderedDict warnings appear in both strict and permissive modes"""
    validator = CSVStructureValidator(model=CSVModelWithOrderedFields, strict=strict, generate_hints=True)
    hint = validator.initial_hint
    
    # OrderedDict warnings should appear regardless of strict/permissive mode
    assert "IMPORTANT: Fields [col1, col2] require order preservation!" in hint


def test_csv_ordered_fields_no_hints_when_disabled():
    """Test that OrderedDict warnings don't appear when generate_hints=False"""
    validator = CSVStructureValidator(model=CSVModelWithOrderedFields, strict=True, generate_hints=False)
    hint = validator.initial_hint
    
    # Should be a simple generic hint when hints are disabled
    assert "order preservation" not in hint
    assert hint == "Please return only the CSV table, starting with the header row and ending with the last row, with no explanation or extra text and without extra whitespaces in the header and content rows. Please use commas as separators. If any of the cells of a string type contains a comma, please surround the cell with double quotes." 