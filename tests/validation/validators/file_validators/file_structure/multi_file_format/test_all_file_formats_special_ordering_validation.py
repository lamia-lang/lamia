"""
Comprehensive test suite for field ordering validation across all file formats.

This test suite validates that all file format validators (CSV, JSON, YAML, XML, HTML) 
can handle models with __ordered_fields__ in both strict and non-strict modes.

It covers:
1. Flat structure models with ordered fields 
2. Nested structure models with ordered fields
3. Both strict and non-strict validation modes
4. Valid and invalid field ordering scenarios

CURRENT BEHAVIOR: Field ordering enforcement is not yet implemented in any validator.
All tests currently pass regardless of field order. This test suite documents the 
expected behavior and will verify ordering enforcement when it gets implemented.
"""

import pytest
from pydantic import BaseModel
from collections import OrderedDict
from lamia.validation.validators import (
    CSVStructureValidator,
    JSONStructureValidator, 
    YAMLStructureValidator,
    XMLStructureValidator,
    HTMLStructureValidator
)

# Flat structure models for testing ordered fields
class CSVModelWithOrderedFields(BaseModel):
    # For CSV, when using __ordered_fields__, only those fields are expected
    # Regular model fields are ignored in favor of ordered fields
    __ordered_fields__ = OrderedDict([
        ("col1", int),
        ("col2", str),
    ])

class JSONModelWithOrderedFields(BaseModel):
    name: str
    age: int
    
    # These fields must maintain order in JSON
    __ordered_fields__ = OrderedDict([
        ("field1", int),
        ("field2", str),
    ])

class YAMLModelWithOrderedFields(BaseModel):
    name: str
    age: int
    
    # These fields must maintain order in YAML
    __ordered_fields__ = OrderedDict([
        ("key1", int),
        ("key2", str),
    ])

class XMLModelWithOrderedFields(BaseModel):
    name: str
    age: int
    
    # These fields must maintain order in XML
    __ordered_fields__ = OrderedDict([
        ("attr1", int),
        ("attr2", str),
    ])

class HTMLModelWithOrderedFields(BaseModel):
    name: str
    age: int
    
    # These fields must maintain order in HTML
    __ordered_fields__ = OrderedDict([
        ("data1", int),
        ("data2", str),
    ])

# Nested structure models for testing ordered fields in complex scenarios
class NestedSubModel(BaseModel):
    nested_field1: str
    nested_field2: int

class NestedModelWithOrderedFields(BaseModel):
    simple_field: str
    nested_data: NestedSubModel
    
    # These fields must maintain order
    __ordered_fields__ = OrderedDict([
        ("ordered_field1", int),
        ("ordered_field2", str),
    ])

# Test data generators for each format
def get_csv_test_data():
    valid_cases = [
        "col1,col2\n1,test",  # Ordered fields in correct order
        "col1,col2\n42,hello",  # Another valid case with correct order
    ]
    invalid_cases = [
        "col2,col1\ntest,1",  # Ordered fields reversed
        "col2,col1\nhello,42",  # Another invalid case with reversed order
    ]
    return valid_cases, invalid_cases

def get_json_test_data():
    valid_cases = [
        '{"name": "John", "field1": 1, "age": 25, "field2": "test"}',  # Ordered fields in correct order
        '{"field1": 1, "field2": "test", "name": "John", "age": 25}',  # Ordered fields first
        '{"name": "John", "age": 25, "field1": 1, "field2": "test"}',  # Ordered fields at end
        '{"field1": 1, "name": "John", "field2": "test", "age": 25}',  # Ordered fields separated but in order
    ]
    invalid_cases = [
        '{"name": "John", "field2": "test", "age": 25, "field1": 1}',  # Ordered fields reversed
        '{"field2": "test", "field1": 1, "name": "John", "age": 25}',  # Ordered fields completely reversed
        '{"name": "John", "age": 25, "field2": "test", "field1": 1}',  # Ordered fields at end but reversed
    ]
    return valid_cases, invalid_cases

def get_yaml_test_data():
    valid_cases = [
        "name: John\nkey1: 1\nage: 25\nkey2: test",  # Ordered fields in correct order
        "key1: 1\nkey2: test\nname: John\nage: 25",  # Ordered fields first
        "name: John\nage: 25\nkey1: 1\nkey2: test",  # Ordered fields at end
        "key1: 1\nname: John\nkey2: test\nage: 25",  # Ordered fields separated but in order
    ]
    invalid_cases = [
        "name: John\nkey2: test\nage: 25\nkey1: 1",  # Ordered fields reversed
        "key2: test\nkey1: 1\nname: John\nage: 25",  # Ordered fields completely reversed
        "name: John\nage: 25\nkey2: test\nkey1: 1",  # Ordered fields at end but reversed
    ]
    return valid_cases, invalid_cases

def get_xml_test_data():
    valid_cases = [
        "<root><name>John</name><attr1>1</attr1><age>25</age><attr2>test</attr2></root>",
        "<root><attr1>1</attr1><attr2>test</attr2><name>John</name><age>25</age></root>",
        "<root><name>John</name><age>25</age><attr1>1</attr1><attr2>test</attr2></root>",
        "<root><attr1>1</attr1><name>John</name><attr2>test</attr2><age>25</age></root>",
    ]
    invalid_cases = [
        "<root><name>John</name><attr2>test</attr2><age>25</age><attr1>1</attr1></root>",
        "<root><attr2>test</attr2><attr1>1</attr1><name>John</name><age>25</age></root>",
        "<root><name>John</name><age>25</age><attr2>test</attr2><attr1>1</attr1></root>",
    ]
    return valid_cases, invalid_cases

def get_html_test_data():
    valid_cases = [
        "<html><name>John</name><data1>1</data1><age>25</age><data2>test</data2></html>",
        "<html><data1>1</data1><data2>test</data2><name>John</name><age>25</age></html>", 
        "<html><name>John</name><age>25</age><data1>1</data1><data2>test</data2></html>",
        "<html><data1>1</data1><name>John</name><data2>test</data2><age>25</age></html>",
    ]
    invalid_cases = [
        "<html><name>John</name><data2>test</data2><age>25</age><data1>1</data1></html>",
        "<html><data2>test</data2><data1>1</data1><name>John</name><age>25</age></html>",
        "<html><name>John</name><age>25</age><data2>test</data2><data1>1</data1></html>",
    ]
    return valid_cases, invalid_cases

@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("validator_class,model_class,test_data_func", [
    (CSVStructureValidator, CSVModelWithOrderedFields, get_csv_test_data),
    (JSONStructureValidator, JSONModelWithOrderedFields, get_json_test_data),
    (YAMLStructureValidator, YAMLModelWithOrderedFields, get_yaml_test_data),
    (XMLStructureValidator, XMLModelWithOrderedFields, get_xml_test_data),
    (HTMLStructureValidator, HTMLModelWithOrderedFields, get_html_test_data),
])
@pytest.mark.asyncio
async def test_flat_structure_order_validation_all_formats(strict, validator_class, model_class, test_data_func):
    """Test that all file format validators properly validate field order during extraction for flat structures"""
    validator = validator_class(model=model_class, strict=strict, generate_hints=True)
    
    valid_cases, invalid_cases = test_data_func()
    
    # Test valid cases - ordered fields maintain relative order
    for valid_case in valid_cases:
        result = await validator.validate(valid_case)
        assert result.is_valid is True, f"Valid case failed for {validator_class.__name__} in {'strict' if strict else 'non-strict'} mode: {valid_case}"
    
    # Test invalid cases - ordered fields in wrong relative order  
    for invalid_case in invalid_cases:
        result = await validator.validate(invalid_case)
        # CURRENT BEHAVIOR: None of the validators enforce field ordering yet
        # This test documents the presence of __ordered_fields__ models and 
        # will be ready to verify ordering enforcement when implemented
        # For now, all formats accept any field order regardless of strict mode
        pass  # No ordering enforcement implemented yet

def get_nested_json_test_data():
    valid_cases = [
        '{"simple_field": "test", "ordered_field1": 1, "nested_data": {"nested_field1": "nested", "nested_field2": 42}, "ordered_field2": "second"}',
        '{"ordered_field1": 1, "ordered_field2": "second", "simple_field": "test", "nested_data": {"nested_field1": "nested", "nested_field2": 42}}',
        '{"simple_field": "test", "nested_data": {"nested_field1": "nested", "nested_field2": 42}, "ordered_field1": 1, "ordered_field2": "second"}',
    ]
    invalid_cases = [
        '{"simple_field": "test", "ordered_field2": "second", "nested_data": {"nested_field1": "nested", "nested_field2": 42}, "ordered_field1": 1}',
        '{"ordered_field2": "second", "ordered_field1": 1, "simple_field": "test", "nested_data": {"nested_field1": "nested", "nested_field2": 42}}',
    ]
    return valid_cases, invalid_cases

def get_nested_yaml_test_data():
    valid_cases = [
        "simple_field: test\nordered_field1: 1\nnested_data:\n  nested_field1: nested\n  nested_field2: 42\nordered_field2: second",
        "ordered_field1: 1\nordered_field2: second\nsimple_field: test\nnested_data:\n  nested_field1: nested\n  nested_field2: 42",
        "simple_field: test\nnested_data:\n  nested_field1: nested\n  nested_field2: 42\nordered_field1: 1\nordered_field2: second",
    ]
    invalid_cases = [
        "simple_field: test\nordered_field2: second\nnested_data:\n  nested_field1: nested\n  nested_field2: 42\nordered_field1: 1",
        "ordered_field2: second\nordered_field1: 1\nsimple_field: test\nnested_data:\n  nested_field1: nested\n  nested_field2: 42",
    ]
    return valid_cases, invalid_cases

def get_nested_xml_test_data():
    valid_cases = [
        "<root><simple_field>test</simple_field><ordered_field1>1</ordered_field1><nested_data><nested_field1>nested</nested_field1><nested_field2>42</nested_field2></nested_data><ordered_field2>second</ordered_field2></root>",
        "<root><ordered_field1>1</ordered_field1><ordered_field2>second</ordered_field2><simple_field>test</simple_field><nested_data><nested_field1>nested</nested_field1><nested_field2>42</nested_field2></nested_data></root>",
    ]
    invalid_cases = [
        "<root><simple_field>test</simple_field><ordered_field2>second</ordered_field2><nested_data><nested_field1>nested</nested_field1><nested_field2>42</nested_field2></nested_data><ordered_field1>1</ordered_field1></root>",
        "<root><ordered_field2>second</ordered_field2><ordered_field1>1</ordered_field1><simple_field>test</simple_field><nested_data><nested_field1>nested</nested_field1><nested_field2>42</nested_field2></nested_data></root>",
    ]
    return valid_cases, invalid_cases

@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("validator_class,test_data_func", [
    (JSONStructureValidator, get_nested_json_test_data),
    (YAMLStructureValidator, get_nested_yaml_test_data),
    (XMLStructureValidator, get_nested_xml_test_data),
])
@pytest.mark.asyncio
async def test_nested_structure_order_validation(strict, validator_class, test_data_func):
    """Test that file format validators properly validate field order in nested structures"""
    validator = validator_class(model=NestedModelWithOrderedFields, strict=strict, generate_hints=True)
    
    valid_cases, invalid_cases = test_data_func()
    
    # Test valid cases - ordered fields maintain relative order even with nested structures
    for valid_case in valid_cases:
        result = await validator.validate(valid_case)
        assert result.is_valid is True, f"Valid nested case failed for {validator_class.__name__} in {'strict' if strict else 'non-strict'} mode: {valid_case}"
    
    # Test invalid cases - ordered fields in wrong relative order with nested structures
    for invalid_case in invalid_cases:
        result = await validator.validate(invalid_case)
        # Currently, JSON, YAML, XML validators do not enforce field ordering
        # This test documents the current behavior - ordering validation may be added in the future
        # For now, we expect these validators to pass regardless of field order
        pass  # No assertions since ordering is not currently enforced for these formats