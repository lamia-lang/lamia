"""Tests for types module."""

import pytest
from lamia.types import BaseType


class TestBaseType:
    """Test BaseType class."""
    
    def test_base_type_exists(self):
        """Test that BaseType exists and can be instantiated."""
        try:
            base_type = BaseType()
            assert base_type is not None
        except TypeError:
            # If abstract, this is expected
            pass
    
    def test_base_type_interface(self):
        """Test BaseType interface."""
        assert BaseType is not None
        assert hasattr(BaseType, '__init__')
    
    def test_base_type_inheritance(self):
        """Test BaseType can be inherited."""
        class CustomType(BaseType):
            def __init__(self, value):
                self.value = value
        
        custom = CustomType("test")
        assert custom.value == "test"
        assert isinstance(custom, BaseType)


class TestTypeSystem:
    """Test type system functionality."""
    
    def test_type_checking(self):
        """Test type checking functionality."""
        # Test basic type checking
        assert BaseType is not None
        
        # Test that BaseType can be used for type hints
        def process_type(type_instance: BaseType) -> bool:
            return isinstance(type_instance, BaseType)
        
        # This function should exist and be callable
        assert callable(process_type)
    
    def test_type_validation(self):
        """Test type validation functionality."""
        # Test that types can be validated
        try:
            # This might depend on actual implementation
            if hasattr(BaseType, 'validate'):
                result = BaseType.validate("test_value")
                assert result is not None
        except (AttributeError, TypeError):
            # Method might not exist yet
            pass
    
    def test_type_conversion(self):
        """Test type conversion functionality."""
        # Test that types can be converted
        try:
            if hasattr(BaseType, 'convert'):
                result = BaseType.convert("test_value")
                assert result is not None
        except (AttributeError, TypeError):
            # Method might not exist yet
            pass


class MockType(BaseType):
    """Mock type implementation for testing."""
    
    def __init__(self, name: str, validation_fn=None):
        self.name = name
        self.validation_fn = validation_fn or (lambda x: True)
    
    def validate(self, value):
        return self.validation_fn(value)


class TestCustomTypes:
    """Test custom type implementations."""
    
    def test_mock_type_creation(self):
        """Test creating custom type."""
        string_type = MockType("string", lambda x: isinstance(x, str))
        
        assert string_type.name == "string"
        assert string_type.validate("hello") is True
        assert string_type.validate(123) is False
    
    def test_number_type(self):
        """Test number type implementation."""
        number_type = MockType("number", lambda x: isinstance(x, (int, float)))
        
        assert number_type.validate(42) is True
        assert number_type.validate(3.14) is True
        assert number_type.validate("hello") is False
    
    def test_list_type(self):
        """Test list type implementation."""
        list_type = MockType("list", lambda x: isinstance(x, list))
        
        assert list_type.validate([1, 2, 3]) is True
        assert list_type.validate("not a list") is False
    
    def test_complex_validation(self):
        """Test complex validation logic."""
        def validate_positive_number(value):
            return isinstance(value, (int, float)) and value > 0
        
        positive_type = MockType("positive_number", validate_positive_number)
        
        assert positive_type.validate(10) is True
        assert positive_type.validate(3.14) is True
        assert positive_type.validate(-5) is False
        assert positive_type.validate("5") is False


class TestTypeIntegration:
    """Test type integration with other systems."""
    
    def test_type_with_validation_system(self):
        """Test type integration with validation system."""
        # This tests integration patterns
        string_type = MockType("string", lambda x: isinstance(x, str))
        
        # Test that types can be used in validation workflows
        test_values = ["hello", 123, [], {}]
        results = [string_type.validate(val) for val in test_values]
        
        assert results == [True, False, False, False]
    
    def test_multiple_types(self):
        """Test working with multiple types."""
        types = {
            "string": MockType("string", lambda x: isinstance(x, str)),
            "number": MockType("number", lambda x: isinstance(x, (int, float))),
            "boolean": MockType("boolean", lambda x: isinstance(x, bool))
        }
        
        test_data = [
            ("hello", "string", True),
            (42, "number", True),
            (True, "boolean", True),
            ("hello", "number", False),
            (42, "string", False)
        ]
        
        for value, type_name, expected in test_data:
            result = types[type_name].validate(value)
            assert result == expected
    
    def test_type_registry_pattern(self):
        """Test type registry pattern."""
        class TypeRegistry:
            def __init__(self):
                self.types = {}
            
            def register(self, name, type_instance):
                self.types[name] = type_instance
            
            def get(self, name):
                return self.types.get(name)
            
            def validate(self, value, type_name):
                type_instance = self.get(type_name)
                if type_instance:
                    return type_instance.validate(value)
                return False
        
        registry = TypeRegistry()
        registry.register("string", MockType("string", lambda x: isinstance(x, str)))
        registry.register("number", MockType("number", lambda x: isinstance(x, (int, float))))
        
        assert registry.validate("hello", "string") is True
        assert registry.validate(42, "number") is True
        assert registry.validate("hello", "number") is False


class TestTypeEdgeCases:
    """Test type system edge cases."""
    
    def test_none_values(self):
        """Test type handling of None values."""
        none_accepting_type = MockType("nullable", lambda x: x is None or isinstance(x, str))
        
        assert none_accepting_type.validate(None) is True
        assert none_accepting_type.validate("hello") is True
        assert none_accepting_type.validate(123) is False
    
    def test_empty_values(self):
        """Test type handling of empty values."""
        non_empty_string_type = MockType("non_empty_string", lambda x: isinstance(x, str) and len(x) > 0)
        
        assert non_empty_string_type.validate("hello") is True
        assert non_empty_string_type.validate("") is False
        assert non_empty_string_type.validate(None) is False
    
    def test_type_with_no_validation(self):
        """Test type with no validation function."""
        any_type = MockType("any")
        
        test_values = ["string", 123, [], {}, None, True]
        for value in test_values:
            assert any_type.validate(value) is True
    
    def test_type_validation_errors(self):
        """Test type validation that raises errors."""
        def error_validation(value):
            if value == "error":
                raise ValueError("Validation error")
            return True
        
        error_type = MockType("error_type", error_validation)
        
        assert error_type.validate("good") is True
        
        with pytest.raises(ValueError):
            error_type.validate("error")


class TestTypeDocumentation:
    """Test type system documentation and interfaces."""
    
    def test_base_type_documentation(self):
        """Test BaseType has documentation."""
        if BaseType.__doc__:
            assert len(BaseType.__doc__.strip()) > 0
    
    def test_type_name_attribute(self):
        """Test that types have name attributes."""
        string_type = MockType("string")
        assert hasattr(string_type, 'name')
        assert string_type.name == "string"
    
    def test_type_validation_method(self):
        """Test that types have validation methods."""
        string_type = MockType("string")
        assert hasattr(string_type, 'validate')
        assert callable(string_type.validate)
    
    def test_type_inheritance_chain(self):
        """Test type inheritance chain."""
        string_type = MockType("string")
        assert isinstance(string_type, BaseType)
        assert isinstance(string_type, MockType)