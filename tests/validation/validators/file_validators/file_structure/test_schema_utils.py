"""
Unit tests for schema_utils module.
"""

import json
import pytest
from typing import Optional, List
from pydantic import BaseModel

from lamia.validation.validators.file_validators.file_structure.schema_utils import (
    TokenOptimizedGenerateJsonSchema,
    _get_json_schema,
    get_json_schema,
    get_formatted_json_schema_human_readable
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
    """Test the custom JSON schema generator that removes titles."""
    
    def test_removes_titles_from_simple_schema(self):
        """Test that title fields are removed from a simple schema."""
        schema = SimpleModel.model_json_schema(schema_generator=TokenOptimizedGenerateJsonSchema)
        
        # Check that titles are removed from properties
        assert 'title' not in schema
        for field_schema in schema['properties'].values():
            assert 'title' not in field_schema
    
    def test_removes_titles_from_nested_schema(self):
        """Test that title fields are removed from nested schemas."""
        schema = NestedModel.model_json_schema(schema_generator=TokenOptimizedGenerateJsonSchema)
        
        # Check main schema has no title
        assert 'title' not in schema
        
        # Check properties have no titles
        for field_schema in schema['properties'].values():
            assert 'title' not in field_schema
        
        # Check $defs section has no titles
        if '$defs' in schema:
            for def_schema in schema['$defs'].values():
                assert 'title' not in def_schema
                if 'properties' in def_schema:
                    for prop_schema in def_schema['properties'].values():
                        assert 'title' not in prop_schema
    
    def test_removes_titles_from_deeply_nested_schema(self):
        """Test that title metadata fields are removed from deeply nested schemas."""
        schema = DeepNestedModel.model_json_schema(schema_generator=TokenOptimizedGenerateJsonSchema)
        
        def check_no_title_metadata(obj, path=""):
            """Recursively check that no title metadata exists, but allow field names called 'title'."""
            if isinstance(obj, dict):
                # Check if this is a field definition (has 'type' or '$ref' or 'anyOf')
                is_field_definition = any(key in obj for key in ['type', '$ref', 'anyOf'])
                
                if is_field_definition and 'title' in obj:
                    assert False, f"Found title metadata in field definition at {path}: {obj}"
                
                # Check if this is the root schema or a nested schema definition
                is_schema_definition = 'type' in obj and obj.get('type') == 'object'
                if is_schema_definition and 'title' in obj and 'properties' in obj:
                    assert False, f"Found title metadata in schema definition at {path}: title={obj['title']}"
                
                # Recursively check all values
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    check_no_title_metadata(value, new_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_no_title_metadata(item, f"{path}[{i}]")
        
        check_no_title_metadata(schema)
    
    def test_preserves_other_fields(self):
        """Test that other schema fields are preserved when titles are removed."""
        schema = ComplexModel.model_json_schema(schema_generator=TokenOptimizedGenerateJsonSchema)
        
        # Essential schema structure should be preserved
        assert schema['type'] == 'object'
        assert 'properties' in schema
        assert 'required' in schema
        
        # Field types should be preserved (note: 'title' is a field name in ComplexModel, not the schema title)
        properties = schema['properties']
        assert 'title' in properties  # This is the model field, not the schema title
        assert properties['title']['type'] == 'string'
        assert properties['count']['type'] == 'integer'
        assert properties['is_active']['type'] == 'boolean'
        
        # Verify that schema title metadata is removed, but field titles are also removed
        assert 'title' not in schema  # Main schema title should be removed
        for field_schema in properties.values():
            assert 'title' not in field_schema  # Individual field titles should be removed


class TestPrivateGetJsonSchema:
    """Test the private _get_json_schema function."""
    
    def test_returns_dict_with_optimization_false(self):
        """Test that function returns dict when optimization is False."""
        result = _get_json_schema(SimpleModel, optimize_for_tokens=False)
        
        assert isinstance(result, dict)
        assert 'properties' in result
        assert result['properties']['name']['title'] == 'Name'  # Title should be present
    
    def test_returns_dict_with_optimization_true(self):
        """Test that function returns dict when optimization is True."""
        result = _get_json_schema(SimpleModel, optimize_for_tokens=True)
        
        assert isinstance(result, dict)
        assert 'properties' in result
        assert 'title' not in result['properties']['name']  # Title should be removed
    
    def test_different_results_based_on_optimization_flag(self):
        """Test that optimization flag produces different results."""
        normal_result = _get_json_schema(SimpleModel, optimize_for_tokens=False)
        optimized_result = _get_json_schema(SimpleModel, optimize_for_tokens=True)
        
        # Results should be different
        assert normal_result != optimized_result
        
        # Normal should have titles, optimized should not
        assert normal_result['properties']['name'].get('title') == 'Name'
        assert 'title' not in optimized_result['properties']['name']


class TestGetJsonSchema:
    """Test the public get_json_schema function."""
    
    def test_returns_minified_json_string(self):
        """Test that function returns a minified JSON string."""
        result = get_json_schema(SimpleModel, optimize_for_tokens=False)
        
        assert isinstance(result, str)
        # Should be valid JSON
        parsed = json.loads(result)
        assert isinstance(parsed, dict)
        
        # Should be minified (no extra spaces)
        assert ' ' not in result or result.count(' ') < 10  # Very few spaces in minified JSON
        assert '\n' not in result  # No newlines in minified JSON
    
    def test_optimization_affects_output_size(self):
        """Test that token optimization reduces the output size."""
        normal_result = get_json_schema(NestedModel, optimize_for_tokens=False)
        optimized_result = get_json_schema(NestedModel, optimize_for_tokens=True)
        
        # Optimized should be shorter
        assert len(optimized_result) < len(normal_result)
        
        # Both should be valid JSON
        normal_parsed = json.loads(normal_result)
        optimized_parsed = json.loads(optimized_result)
        assert isinstance(normal_parsed, dict)
        assert isinstance(optimized_parsed, dict)
    
    def test_produces_valid_schema_structure(self):
        """Test that the output is a valid JSON schema structure."""
        result = get_json_schema(ComplexModel, optimize_for_tokens=True)
        schema = json.loads(result)
        
        # Basic JSON Schema structure
        assert schema['type'] == 'object'
        assert 'properties' in schema
        assert 'required' in schema
        
        # Properties should have type information
        for prop in schema['properties'].values():
            assert 'type' in prop or '$ref' in prop or 'anyOf' in prop


class TestGetFormattedJsonSchemaHumanReadable:
    """Test the formatted JSON schema function."""
    
    def test_returns_formatted_json_string(self):
        """Test that function returns a formatted JSON string."""
        result = get_formatted_json_schema_human_readable(SimpleModel, optimize_for_tokens=False)
        
        assert isinstance(result, str)
        # Should be valid JSON
        parsed = json.loads(result)
        assert isinstance(parsed, dict)
        
        # Should be formatted (has indentation)
        assert '\n' in result  # Should have newlines
        assert '  ' in result  # Should have indentation
    
    def test_optimization_flag_works_in_formatted_output(self):
        """Test that optimization flag works with formatted output."""
        normal_result = get_formatted_json_schema_human_readable(SimpleModel, optimize_for_tokens=False)
        optimized_result = get_formatted_json_schema_human_readable(SimpleModel, optimize_for_tokens=True)
        
        # Both should be formatted
        assert '\n' in normal_result
        assert '\n' in optimized_result
        
        # Parse and check for titles
        normal_parsed = json.loads(normal_result)
        optimized_parsed = json.loads(optimized_result)
        
        assert normal_parsed['properties']['name'].get('title') == 'Name'
        assert 'title' not in optimized_parsed['properties']['name']
    
    def test_formatted_output_is_readable(self):
        """Test that formatted output is human-readable."""
        result = get_formatted_json_schema_human_readable(NestedModel, optimize_for_tokens=False)
        
        # Should have proper JSON formatting
        lines = result.split('\n')
        assert len(lines) > 5  # Should be multi-line
        
        # Should have consistent indentation
        indented_lines = [line for line in lines if line.startswith('  ')]
        assert len(indented_lines) > 0  # Should have indented lines


class TestIntegration:
    """Integration tests for the schema utils module."""
    
    def test_token_savings_calculation(self):
        """Test that we can measure actual token savings."""
        normal_schema = get_json_schema(DeepNestedModel, optimize_for_tokens=False)
        optimized_schema = get_json_schema(DeepNestedModel, optimize_for_tokens=True)
        
        savings = len(normal_schema) - len(optimized_schema)
        savings_percentage = (savings / len(normal_schema)) * 100
        
        # Should have meaningful savings
        assert savings > 0
        assert savings_percentage > 5  # At least 5% savings expected
    
    def test_schemas_are_functionally_equivalent(self):
        """Test that optimized schemas retain functional equivalence."""
        normal_schema = json.loads(get_json_schema(SimpleModel, optimize_for_tokens=False))
        optimized_schema = json.loads(get_json_schema(SimpleModel, optimize_for_tokens=True))
        
        # Core structure should be the same
        assert normal_schema['type'] == optimized_schema['type']
        assert set(normal_schema['properties'].keys()) == set(optimized_schema['properties'].keys())
        assert normal_schema['required'] == optimized_schema['required']
        
        # Field types should be the same
        for field_name in normal_schema['properties']:
            normal_field = normal_schema['properties'][field_name]
            optimized_field = optimized_schema['properties'][field_name]
            
            # Remove titles for comparison
            normal_field_copy = {k: v for k, v in normal_field.items() if k != 'title'}
            optimized_field_copy = {k: v for k, v in optimized_field.items() if k != 'title'}
            
            assert normal_field_copy == optimized_field_copy
    
    def test_all_functions_work_together(self):
        """Test that all public functions work correctly together."""
        # Test with a complex nested model
        test_model = DeepNestedModel
        
        # All functions should work without errors
        minified_normal = get_json_schema(test_model, optimize_for_tokens=False)
        minified_optimized = get_json_schema(test_model, optimize_for_tokens=True)
        formatted_normal = get_formatted_json_schema_human_readable(test_model, optimize_for_tokens=False)
        formatted_optimized = get_formatted_json_schema_human_readable(test_model, optimize_for_tokens=True)
        
        # All should be valid JSON
        assert json.loads(minified_normal)
        assert json.loads(minified_optimized)
        assert json.loads(formatted_normal)
        assert json.loads(formatted_optimized)
        
        # Optimized should be shorter
        assert len(minified_optimized) < len(minified_normal)
        assert len(formatted_optimized) < len(formatted_normal) 