import pytest
from lamia.validation.validators.object_validator import ObjectValidator
import asyncio
from pydantic import BaseModel
import json
from pydantic import constr, Field

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_object_validator_valid(strict):
    schema = {"a": "int", "b": "string"}
    validator = ObjectValidator(schema=schema, strict=strict)
    valid_json = '{"a": 1, "b": "hello"}'
    result = await validator.validate(valid_json)
    assert result.is_valid
    assert result.typed_result is not None
    assert result.typed_result.a == 1
    assert result.typed_result.b == "hello"
    assert result.info_loss is None

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_object_validator_invalid_type(strict):
    schema = {"a": "int", "b": "string"}
    validator = ObjectValidator(schema=schema, strict=strict)
    invalid_json = '{"a": "not_an_int", "b": "hello"}'
    result = await validator.validate(invalid_json)
    assert not result.is_valid
    assert "Field 'a':" in result.error_message and "Cannot" in result.error_message and "convert" in result.error_message
    assert result.typed_result is None
    assert result.info_loss is None

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_object_validator_missing_field(strict):
    schema = {"a": "int", "b": "string"}
    validator = ObjectValidator(schema=schema, strict=strict)
    missing_field_json = '{"a": 1}'
    result = await validator.validate(missing_field_json)
    assert not result.is_valid
    assert "Missing field 'b'" in result.error_message
    assert result.typed_result is None
    assert result.info_loss is None

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_object_validator_invalid_json(strict):
    schema = {"a": "int", "b": "string"}
    validator = ObjectValidator(schema=schema, strict=strict)
    invalid_json = '{a: 1, b: "hello"}'  # Not valid JSON
    result = await validator.validate(invalid_json)
    assert not result.is_valid
    assert ("Response is not valid JSON:" in result.error_message or 
            "No valid JSON object found" in result.error_message or
            "Extracted JSON is not valid" in result.error_message)
    assert result.typed_result is None
    assert result.info_loss is None

@pytest.mark.asyncio
async def test_object_validator_permissive_extracts_json():
    schema = {"a": "int", "b": "string"}
    validator = ObjectValidator(schema=schema, strict=False)
    text_with_json = 'Here is your object: {"a": 1, "b": "hello"} Thank you!'
    result = await validator.validate(text_with_json)
    assert result.is_valid
    assert result.validated_text == '{"a": 1, "b": "hello"}'
    assert result.typed_result is not None
    assert result.typed_result.a == 1    
    assert result.typed_result.b == "hello"
    assert result.info_loss is None

# --- Pydantic BaseModel tests ---
class MyModel(BaseModel):
    a: int
    b: str

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_object_validator_valid_pydantic(strict):
    validator = ObjectValidator(schema=MyModel, strict=strict)
    valid_json = '{"a": 42, "b": "world"}'
    result = await validator.validate(valid_json)
    assert result.is_valid
    assert result.typed_result is not None
    assert result.typed_result.a == 42
    assert result.typed_result.b == "world"
    assert result.info_loss is None

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_object_validator_invalid_type_pydantic(strict):
    validator = ObjectValidator(schema=MyModel, strict=strict)
    invalid_json = '{"a": "oops", "b": "world"}'
    result = await validator.validate(invalid_json)
    assert not result.is_valid
    assert "Field 'a':" in result.error_message and "Cannot" in result.error_message and "convert" in result.error_message
    assert result.typed_result is None
    assert result.info_loss is None

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_object_validator_missing_field_pydantic(strict):
    validator = ObjectValidator(schema=MyModel, strict=strict)
    missing_field_json = '{"a": 42}'
    result = await validator.validate(missing_field_json)
    assert not result.is_valid
    assert "Missing field 'b'" in result.error_message
    assert result.typed_result is None
    assert result.info_loss is None

# --- Hint generation tests ---
def test_object_validator_initial_hint_contains_schema():
    """Test that the initial hint contains the JSON schema."""
    schema = {"a": "int", "b": "string"}
    validator = ObjectValidator(schema=schema)
    hint = validator.initial_hint
    
    # Check that the hint contains the base message
    assert "Please ensure the response is a valid JSON object matching the required schema" in hint
    assert "with no explanation or extra text" in hint
    assert "Schema:" in hint
    
    # Check that the hint contains JSON schema
    assert "{" in hint and "}" in hint
    
    # Extract and validate the JSON schema part
    schema_start = hint.find("Schema: ") + len("Schema: ")
    json_schema_str = hint[schema_start:]
    
    # Should be valid JSON
    json_schema = json.loads(json_schema_str)
    assert isinstance(json_schema, dict)
    assert "type" in json_schema
    assert json_schema["type"] == "object"
    assert "properties" in json_schema
def test_object_validator_initial_hint_contains_schema_pydantic():
    """Test that the initial hint contains the JSON schema for Pydantic models."""
    validator = ObjectValidator(schema=MyModel)
    hint = validator.initial_hint
    
    # Check that the hint contains the base message
    assert "Please ensure the response is a valid JSON object matching the required schema" in hint
    assert "with no explanation or extra text" in hint
    assert "Schema:" in hint
    
    # Check that the hint contains JSON schema
    assert "{" in hint and "}" in hint
    
    # Extract and validate the JSON schema part
    schema_start = hint.find("Schema: ") + len("Schema: ")
    json_schema_str = hint[schema_start:]
    
    # Should be valid JSON
    json_schema = json.loads(json_schema_str)
    assert isinstance(json_schema, dict)
    assert "type" in json_schema
    assert json_schema["type"] == "object"
    assert "properties" in json_schema
    
    # Check that it has the expected fields from MyModel
    properties = json_schema["properties"]
    assert "a" in properties
    assert "b" in properties
    assert properties["a"]["type"] == "integer"
    assert properties["b"]["type"] == "string"

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_object_validator_initial_and_retry_hints(strict):
    schema = {"a": "int", "b": "string"}
    validator = ObjectValidator(schema=schema, strict=strict, generate_hints=True)
    assert validator.initial_hint is not None

    invalid_json = '{"a": "not_an_int", "b": "hello"}'
    result = await validator.validate(invalid_json)
    assert not result.is_valid
    assert result.hint is not None
    assert result.error_message is not None
    assert validator.initial_hint in result.hint
    assert result.error_message in result.hint

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_object_validator_no_hint_when_hints_disabled(strict):
    schema = {"a": "int", "b": "string"}
    validator = ObjectValidator(schema=schema, strict=strict, generate_hints=False)
    #assert validator.initial_hint is None
    invalid_json = '{"a": "not_an_int", "b": "hello"}'
    result = await validator.validate(invalid_json)
    assert not result.is_valid
    assert result.hint is None

# --- End of hint generation tests ---

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_pydantic_field_constraints_are_enforced_on_objects(strict):
    class MyModel(BaseModel):
        mystr: str = Field(..., min_length=3)

    # the same but with a pydantic constr constraint
    class MyModelWithConstr(BaseModel):
        mystr: constr(min_length=3)

    validator = ObjectValidator(schema=MyModel, strict=strict)
    validator2 = ObjectValidator(schema=MyModelWithConstr, strict=strict)
    valid_json = '{"mystr": "abcd"}'
    invalid_json = '{"mystr": "a"}'

    result = await validator.validate(valid_json)
    result2 = await validator2.validate(valid_json)
    assert result.is_valid
    assert result2.is_valid
    assert result.typed_result is not None
    assert result2.typed_result is not None
    assert result.info_loss is None
    assert result2.info_loss is None

    result = await validator.validate(invalid_json)
    result2 = await validator2.validate(invalid_json)
    assert not result.is_valid
    assert not result2.is_valid
    assert "at least 3 characters" in result.error_message
    assert "at least 3 characters" in result2.error_message
    assert result.typed_result is None
    assert result2.typed_result is None
    assert result.info_loss is None
    assert result2.info_loss is None

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_pydantic_fields_with_multiple_constraints(strict):
    class MyModel(BaseModel):
        mystr: str = Field(..., min_length=3, pattern=r"^abc")

    validator = ObjectValidator(schema=MyModel, strict=strict)
    valid_json = '{"mystr": "abcd"}'
    invalid_json_short_and_pattern = '{"mystr": "a"}'
    invalid_json_pattern = '{"mystr": "def"}'

    result = await validator.validate(valid_json)
    assert result.is_valid
    assert result.typed_result is not None
    assert result.info_loss is None

    # Test short string (should report length constraint error)
    result = await validator.validate(invalid_json_short_and_pattern)
    assert not result.is_valid
    assert "at least 3 characters" in result.error_message
    assert result.typed_result is None
    assert result.info_loss is None

    # Test pattern violation (should report pattern constraint error)  
    result = await validator.validate(invalid_json_pattern)
    assert not result.is_valid

    assert "String should match pattern '^abc'" in result.error_message
    assert result.typed_result is None
    assert result.info_loss is None