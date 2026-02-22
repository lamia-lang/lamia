import pytest
import asyncio
from pydantic import BaseModel
from typing import List, Optional

from lamia.validation.validators.file_validators.file_structure.html_structure_validator import HTMLStructureValidator
from lamia.validation.validators.file_validators.file_structure.json_structure_validator import JSONStructureValidator
from lamia.validation.validators.file_validators.file_structure.xml_structure_validator import XMLStructureValidator
from lamia.validation.validators.file_validators.file_structure.yaml_structure_validator import YAMLStructureValidator
from lamia.validation.validators.file_validators.file_structure.csv_structure_validator import CSVStructureValidator
from lamia.validation.validators.file_validators.file_structure.markdown_structure_validator import MarkdownStructureValidator, Heading1, Paragraph


# Test Models with nested structures that will cause info_loss
class Address(BaseModel):
    street: str
    number: int  # Will cause info_loss if given "123.5"
    zip_code: str

class Person(BaseModel):
    name: str
    age: int  # Will cause info_loss if given "25.7" 
    score: float
    address: Address

class Company(BaseModel):
    name: str
    employee_count: int  # Will cause info_loss if given "100.8"
    employees: List[Person]

# Simple flat model for CSV (CSV doesn't support nested structures)
class FlatPerson(BaseModel):
    name: str
    age: int  # Will cause info_loss if given "25.7"
    score: float


# Test data that will cause info_loss (float values for int fields)
TEST_DATA = {
    "html": {
        "content": """<html>
        <name>John Doe</name>
        <age>25.7</age>
        <score>85.123</score>
        <address>
            <street>Main St</street>
            <number>123.5</number>
            <zip_code>12345</zip_code>
        </address>
</html>""",
        "model": Person,
        "expected_info_loss_fields": ["age", "address"]  # age direct, address.number nested
    },
    
    "json": {
        "content": """{
    "name": "John Doe",
    "age": "25.7",
    "score": 85.123,
    "address": {
        "street": "Main St",
        "number": "123.5",
        "zip_code": "12345"
    }
}""",
        "model": Person,
        "expected_info_loss_fields": ["age", "address"]
    },
    
    "xml": {
        "content": """<root>
<name>John Doe</name>
<age>25.7</age>
<score>85.123</score>
<address>
    <street>Main St</street>
    <number>123.5</number>
    <zip_code>12345</zip_code>
</address>
</root>""",
        "model": Person,
        "expected_info_loss_fields": ["age", "address"]
    },
    
    "yaml": {
        "content": """name: John Doe
age: 25.7
score: 85.123
address:
  street: Main St
  number: 123.5
  zip_code: "12345"
""",
        "model": Person,
        "expected_info_loss_fields": ["age", "address"]
    },
    
    "csv": {
        "content": """name,age,score
John Doe,25.7,85.123""",
        "model": FlatPerson,
        "expected_info_loss_fields": ["age"]  # CSV is flat, only direct field info_loss
    },
}

VALIDATOR_CLASSES = {
    "html": HTMLStructureValidator,
    "json": JSONStructureValidator,
    "xml": XMLStructureValidator,
    "yaml": YAMLStructureValidator,
    "csv": CSVStructureValidator,
}


class TestInfoLossNestedStructures:
    """Test info_loss tracking with nested Pydantic models across all structure validators."""
    
    @pytest.mark.parametrize("validator_type", ["html", "json", "xml", "yaml", "csv"])
    @pytest.mark.parametrize("strict_mode", [True, False])
    async def test_info_loss_with_nested_models(self, validator_type, strict_mode):
        """Test info_loss tracking with nested models in strict and permissive modes."""
        
        # Skip markdown for now due to its special text extraction behavior
        if validator_type == "markdown":
            pytest.skip("Markdown validator has different text extraction behavior")
            

            
        test_config = TEST_DATA[validator_type]
        validator_class = VALIDATOR_CLASSES[validator_type]
        
        # Create validator instance
        validator = validator_class(
            model=test_config["model"],
            strict=strict_mode,
            generate_hints=False
        )
        
        # Run validation
        if strict_mode:
            # In strict mode, lossy conversions should FAIL
            result = await validator.validate_strict(test_config["content"])
            
            # Should fail because of lossy float->int conversions
            assert result.is_valid is False, f"Strict mode should fail for {validator_type} due to lossy conversions"
            assert "cannot strictly convert" in result.error_message.lower() or "cannot convert" in result.error_message.lower() or "field" in result.error_message.lower()
            # No info_loss in strict mode since validation failed
            assert result.info_loss is None or result.info_loss == {}
            
        else:
            # In permissive mode, lossy conversions should SUCCEED with info_loss tracking
            result = await validator.validate_permissive(test_config["content"])
            
            # Should succeed
            assert result.is_valid is True, f"Permissive mode should succeed for {validator_type}: {result.error_message}"
            assert result.typed_result is not None
            
            # Should have info_loss for the expected fields
            assert result.info_loss is not None, f"Permissive mode should track info_loss for {validator_type}"
            
            # Check that expected fields have info_loss
            for field in test_config["expected_info_loss_fields"]:
                assert field in result.info_loss, f"Field '{field}' should have info_loss in {validator_type}"
                
                # Verify the info_loss structure
                field_info_loss = result.info_loss[field]
                if isinstance(field_info_loss, dict) and "conversion" in field_info_loss:
                    # Direct field conversion
                    assert "original_value" in field_info_loss
                    assert "converted_value" in field_info_loss
                else:
                    # Nested field conversion (should be a dict with nested structure)
                    assert isinstance(field_info_loss, dict), f"Nested field '{field}' should have nested info_loss structure"

    @pytest.mark.parametrize("validator_type", ["html", "json", "xml", "yaml"])
    async def test_nested_info_loss_structure(self, validator_type):
        """Test that nested model info_loss has correct hierarchical structure."""
        

        
        test_config = TEST_DATA[validator_type]
        validator_class = VALIDATOR_CLASSES[validator_type]
        
        # Create validator in permissive mode
        validator = validator_class(
            model=test_config["model"],
            strict=False,
            generate_hints=False
        )
        
        result = await validator.validate_permissive(test_config["content"])
        
        assert result.is_valid is True
        assert result.info_loss is not None
        
        # Check nested structure for address field
        if "address" in result.info_loss:
            address_info_loss = result.info_loss["address"]
            assert isinstance(address_info_loss, dict)
            
            # Should have info_loss for the number field (123.5 -> 123)
            assert "number" in address_info_loss
            number_info_loss = address_info_loss["number"]
            assert "conversion" in number_info_loss
            assert "original_value" in number_info_loss
            assert "lost_decimal" in number_info_loss

    async def test_csv_flat_structure_info_loss(self):
        """Test that CSV validator correctly handles flat structure info_loss."""
        
        validator = CSVStructureValidator(model=FlatPerson, strict=False, generate_hints=False)
        
        csv_content = """name,age,score
John Doe,25.7,85.123
Jane Smith,30.2,92.456"""
        
        result = await validator.validate_permissive(csv_content)
        
        assert result.is_valid is True
        assert result.info_loss is not None
        
        # Should have info_loss for age field (25.7 -> 25)
        assert "age" in result.info_loss
        age_info_loss = result.info_loss["age"]
        assert age_info_loss["conversion"] == "str -> float -> int"
        assert age_info_loss["original_value"] == "25.7"
        assert age_info_loss["converted_value"] == 25
        assert abs(age_info_loss["lost_decimal"] - 0.7) < 1e-10

    async def test_no_info_loss_when_no_conversion_needed(self):
        """Test that no info_loss is tracked when no lossy conversions occur."""
        
        # Test data with exact types (no conversion needed)
        clean_json = """{
    "name": "John Doe",
    "age": 25,
    "score": 85.123,
    "address": {
        "street": "Main St",
        "number": 123,
        "zip_code": "12345"
    }
}"""
        
        validator = JSONStructureValidator(model=Person, strict=False, generate_hints=False)
        result = await validator.validate_permissive(clean_json)
        
        assert result.is_valid is True
        # Should have no info_loss since no conversions were needed
        assert result.info_loss is None or result.info_loss == {}

    @pytest.mark.parametrize("validator_type", ["html", "json", "xml", "yaml"])
    async def test_partial_info_loss_in_nested_structures(self, validator_type):
        """Test scenarios where only some nested fields have info_loss."""
        
                 # Create test data where only some fields need conversion
        if validator_type == "json":
            content = """{
                "name": "John Doe",
                "age": 25,
                "score": 85.123,
                "address": {
                    "street": "Main St",
                    "number": "123.5",
                    "zip_code": "12345"
                }
            }"""
        elif validator_type == "html":
            content = """<html>
                <body>
                    <name>John Doe</name>
                    <age>25</age>
                    <score>85.123</score>
                    <address>
                        <street>Main St</street>
                        <number>123.5</number>
                        <zip_code>12345</zip_code>
                    </address>
                </body>
            </html>"""
        elif validator_type == "xml":
            content = """<root>
                <name>John Doe</name>
                <age>25</age>
                <score>85.123</score>
                <address>
                    <street>Main St</street>
                    <number>123.5</number>
                    <zip_code>12345</zip_code>
                </address>
                </root>"""
        elif validator_type == "yaml":
            content = """
name: John Doe
age: 25
score: 85.123
address:
  street: Main St
  number: 123.5
  zip_code: "12345"
"""
        
        validator_class = VALIDATOR_CLASSES[validator_type]
        validator = validator_class(model=Person, strict=False, generate_hints=False)
        
        result = await validator.validate_permissive(content)
        
        assert result.is_valid is True
        assert result.info_loss is not None
        
        # Should only have info_loss for address.number, not for age
        assert "age" not in result.info_loss  # age=25 (int) -> int, no conversion
        assert "address" in result.info_loss   # address.number=123.5 -> 123, conversion
        
        address_info_loss = result.info_loss["address"]
        assert len(address_info_loss) == 1
        assert "number" in address_info_loss