"""
Unit tests for pydantic_utils module.
"""

import json
import pytest
from typing import Optional, List
from collections import OrderedDict
from pydantic import BaseModel

from lamia.validation.utils.pydantic_utils import (
    TokenOptimizedGenerateJsonSchema,
    _get_json_schema,
    get_pydantic_json_schema,
    get_formatted_json_schema_human_readable,
    get_ordered_dict_fields
)


# Test models
class SimpleModel(BaseModel):
    name: str
    age: int


class ComplexModel(BaseModel):
    title: str
    count: int
    is_active: bool
    description: Optional[str] = None


class NestedModel(BaseModel):
    id: int
    user: SimpleModel
    tags: List[str]


class DeepNestedModel(BaseModel):
    level1: NestedModel
    metadata: ComplexModel


class TestTokenOptimizedGenerateJsonSchema:
    """Test the custom JSON schema generator that removes title metadata."""
    
    def test_removes_title_metadata_from_simple_schema(self):
        """Test that title metadata fields are removed from a simple schema."""
        optimized_schema = SimpleModel.model_json_schema(schema_generator=TokenOptimizedGenerateJsonSchema)
        default_schema = SimpleModel.model_json_schema()
        
        # Check that root title is removed
        assert 'title' not in optimized_schema
        assert 'title' in default_schema
        
        # Check that field title metadata is removed
        for field_name, field_schema in optimized_schema['properties'].items():
            assert 'title' not in field_schema
            assert 'title' in default_schema['properties'][field_name]
    
    def test_removes_title_metadata_from_nested_schema(self):
        """Test that title metadata fields are removed from nested schemas."""
        optimized_schema = NestedModel.model_json_schema(schema_generator=TokenOptimizedGenerateJsonSchema)
        default_schema = NestedModel.model_json_schema()
        
        # Check main schema has no title metadata
        assert 'title' not in optimized_schema
        assert 'title' in default_schema
        
        # Check properties have no title metadata
        for field_schema in optimized_schema['properties'].values():
            assert 'title' not in field_schema
        
        # Check $defs section has no title metadata
        if '$defs' in optimized_schema:
            for def_schema in optimized_schema['$defs'].values():
                assert 'title' not in def_schema
                if 'properties' in def_schema:
                    for prop_schema in def_schema['properties'].values():
                        assert 'title' not in prop_schema
    
    def test_preserves_field_named_title(self):
        """Test that actual model fields named 'title' are preserved."""
        optimized_schema = ComplexModel.model_json_schema(schema_generator=TokenOptimizedGenerateJsonSchema)
        
        # The 'title' field should still exist as a property
        assert 'title' in optimized_schema['properties']
        assert optimized_schema['properties']['title']['type'] == 'string'
        assert 'title' in optimized_schema['required']
        
        # But title metadata should be removed
        assert 'title' not in optimized_schema  # Root schema title
        assert 'title' not in optimized_schema['properties']['title']  # Field metadata title
    
    def test_preserves_functional_schema_structure(self):
        """Test that optimized schemas preserve all functional information."""
        optimized_schema = ComplexModel.model_json_schema(schema_generator=TokenOptimizedGenerateJsonSchema)
        default_schema = ComplexModel.model_json_schema()
        
        # Core structure should be the same
        assert optimized_schema['type'] == default_schema['type']
        assert set(optimized_schema['properties'].keys()) == set(default_schema['properties'].keys())
        assert optimized_schema['required'] == default_schema['required']
        
        # Field types should be the same (ignoring title metadata)
        for field_name in optimized_schema['properties']:
            opt_field = optimized_schema['properties'][field_name]
            def_field = default_schema['properties'][field_name]
            
            # Remove title for comparison
            def_field_no_title = {k: v for k, v in def_field.items() if k != 'title'}
            
            assert opt_field == def_field_no_title


class TestPrivateGetJsonSchema:
    """Test the private _get_json_schema function."""
    
    def test_returns_same_as_pydantic_default_when_not_optimized(self):
        """Test that function returns same result as pydantic default when optimization is False."""
        our_result = _get_json_schema(SimpleModel, optimize_for_tokens=False)
        pydantic_result = SimpleModel.model_json_schema()
        
        assert our_result == pydantic_result
    
    def test_returns_optimized_schema_when_optimized(self):
        """Test that function returns optimized schema when optimization is True."""
        optimized_result = _get_json_schema(SimpleModel, optimize_for_tokens=True)
        default_result = SimpleModel.model_json_schema()
        
        # Results should be different
        assert optimized_result != default_result
        
        # Optimized should have no title metadata
        assert 'title' not in optimized_result
        assert 'title' not in optimized_result['properties']['name']


class TestGetPydanticJsonSchema:
    """Test the public get_pydantic_json_schema function."""
    
    def test_returns_same_as_pydantic_default_when_not_optimized(self):
        """Test that function returns same JSON as pydantic default when optimization is False."""
        our_result = get_pydantic_json_schema(SimpleModel, optimize_for_tokens=False)
        pydantic_result = json.dumps(SimpleModel.model_json_schema(), separators=(',', ':'))
        
        assert our_result == pydantic_result
    
    def test_returns_minified_json_string(self):
        """Test that function returns a minified JSON string."""
        result = get_pydantic_json_schema(SimpleModel, optimize_for_tokens=True)
        
        assert isinstance(result, str)
        # Should be valid JSON
        parsed = json.loads(result)
        assert isinstance(parsed, dict)
        
        # Should be minified (no extra spaces, no newlines)
        assert '\n' not in result
        assert result.count(' ') == 0 or ':' in result  # Only spaces should be in values, not structure
    
    def test_optimization_reduces_output_size(self):
        """Test that token optimization reduces the output size."""
        normal_result = get_pydantic_json_schema(NestedModel, optimize_for_tokens=False)
        optimized_result = get_pydantic_json_schema(NestedModel, optimize_for_tokens=True)
        
        # Optimized should be shorter due to removed title metadata
        assert len(optimized_result) < len(normal_result)
        
        # Both should be valid JSON
        assert json.loads(normal_result)
        assert json.loads(optimized_result)


class TestGetFormattedJsonSchemaHumanReadable:
    """Test the formatted JSON schema function."""
    
    def test_returns_same_as_pydantic_default_when_not_optimized(self):
        """Test that function returns same formatted JSON as pydantic default when optimization is False."""
        our_result = get_formatted_json_schema_human_readable(SimpleModel, optimize_for_tokens=False)
        pydantic_result = json.dumps(SimpleModel.model_json_schema(), indent=2)
        
        assert our_result == pydantic_result
    
    def test_returns_formatted_json_string(self):
        """Test that function returns a properly formatted JSON string."""
        result = get_formatted_json_schema_human_readable(SimpleModel, optimize_for_tokens=True)
        
        assert isinstance(result, str)
        # Should be valid JSON
        parsed = json.loads(result)
        assert isinstance(parsed, dict)
        
        # Should be formatted (has indentation)
        assert '\n' in result
        assert '  ' in result
    
    def test_optimization_works_with_formatting(self):
        """Test that optimization flag works correctly with formatted output."""
        normal_result = get_formatted_json_schema_human_readable(ComplexModel, optimize_for_tokens=False)
        optimized_result = get_formatted_json_schema_human_readable(ComplexModel, optimize_for_tokens=True)
        
        # Both should be formatted
        assert '\n' in normal_result
        assert '\n' in optimized_result
        
        # Parse and check for title metadata differences
        normal_parsed = json.loads(normal_result)
        optimized_parsed = json.loads(optimized_result)
        
        # Normal should have title metadata, optimized should not
        assert 'title' in normal_parsed
        assert 'title' not in optimized_parsed
        
        # But both should have the 'title' field property
        assert 'title' in normal_parsed['properties']
        assert 'title' in optimized_parsed['properties']


class TestIntegration:
    """Integration tests for the pydantic utils module."""
    
    def test_token_savings_with_complex_models(self):
        """Test that we achieve meaningful token savings with complex models."""
        normal_schema = get_pydantic_json_schema(DeepNestedModel, optimize_for_tokens=False)
        optimized_schema = get_pydantic_json_schema(DeepNestedModel, optimize_for_tokens=True)
        
        savings = len(normal_schema) - len(optimized_schema)
        savings_percentage = (savings / len(normal_schema)) * 100
        
        # Should have meaningful savings due to removed title metadata
        assert savings > 0
        assert savings_percentage > 5  # At least 5% savings expected from title removal
    
    def test_optimized_schemas_are_functionally_equivalent(self):
        """Test that optimized schemas retain all functional information."""
        normal_schema = json.loads(get_pydantic_json_schema(ComplexModel, optimize_for_tokens=False))
        optimized_schema = json.loads(get_pydantic_json_schema(ComplexModel, optimize_for_tokens=True))
        
        # Core structure should be identical
        assert normal_schema['type'] == optimized_schema['type']
        assert set(normal_schema['properties'].keys()) == set(optimized_schema['properties'].keys())
        assert normal_schema['required'] == optimized_schema['required']
        
        # Field types should be identical (ignoring title metadata)
        for field_name in normal_schema['properties']:
            normal_field = normal_schema['properties'][field_name]
            optimized_field = optimized_schema['properties'][field_name]
            
            # Remove title metadata for comparison
            normal_field_no_title = {k: v for k, v in normal_field.items() if k != 'title'}
            
            assert optimized_field == normal_field_no_title

# Test models for OrderedDict functionality
class ModelWithOrderedFields(BaseModel):
    name: str
    age: int
    
    __ordered_fields__ = OrderedDict([
        ("col1", int),
        ("col2", str),
    ])


class ModelWithoutOrderedFields(BaseModel):
    name: str
    age: int
    salary: float

class BadModelWithOrderedDictType(BaseModel):
    name: str
    config: OrderedDict[str, int]  # This should fail


class TestGetOrderedDictFields:
    """Test the get_ordered_dict_fields function."""
    
    def test_detects_ordered_fields_correctly(self):
        """Test that function correctly identifies __ordered_fields__ attributes."""
        ordered_fields = get_ordered_dict_fields(ModelWithOrderedFields)
        assert ordered_fields == ["col1", "col2"]
    
    def test_returns_empty_for_regular_models(self):
        """Test that function returns empty list for models without OrderedDict."""
        ordered_fields = get_ordered_dict_fields(ModelWithoutOrderedFields)
        assert ordered_fields == []
    
    def test_fails_fast_on_ordereddict_as_entire_model(self):
        """Test that function raises error when OrderedDict is used as entire model."""
        ordered_model = OrderedDict([
            ("name", str),
            ("age", int),
        ])
        
        with pytest.raises(ValueError, match="OrderedDict as entire model is no longer supported"):
            get_ordered_dict_fields(ordered_model)
    
    def test_fails_fast_on_ordereddict_field_type(self):
        """Test that function raises error when OrderedDict is used as field type annotation."""
        with pytest.raises(ValueError, match="uses OrderedDict as type annotation"):
            get_ordered_dict_fields(BadModelWithOrderedDictType)
    
    def test_maintains_field_order(self):
        """Test that function preserves the order of fields from OrderedDict."""
        # Test with a model that has specific order
        class OrderedModel(BaseModel):
            regular_field: str
            
            __ordered_fields__ = OrderedDict([
                ("third", int),
                ("first", str), 
                ("second", bool),
            ])
        
        ordered_fields = get_ordered_dict_fields(OrderedModel)
        assert ordered_fields == ["third", "first", "second"]  # Order should be preserved
    
    def test_handles_model_with_no_model_fields(self):
        """Test that function handles edge case of model with only ordered fields."""
        class OnlyOrderedModel(BaseModel):
            __ordered_fields__ = OrderedDict([
                ("field1", str),
                ("field2", int),
            ])
        
        ordered_fields = get_ordered_dict_fields(OnlyOrderedModel)
        assert ordered_fields == ["field1", "field2"]
    
    def test_handles_model_with_no_ordered_fields_attribute(self):
        """Test that function handles models without __ordered_fields__ attribute."""
        class SimpleModel(BaseModel):
            name: str
            age: int
        
        ordered_fields = get_ordered_dict_fields(SimpleModel)
        assert ordered_fields == []