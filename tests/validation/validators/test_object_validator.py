import pytest
from lamia.validation.validators.object_validator import ObjectValidator
import asyncio
from pydantic import BaseModel

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_object_validator_valid(strict):
    schema = {"a": "int", "b": "string"}
    validator = ObjectValidator(schema=schema, strict=strict)
    valid_json = '{"a": 1, "b": "hello"}'
    if strict:
        result = await validator.validate_strict(valid_json)
    else:
        result = await validator.validate_permissive(valid_json)
    assert result.is_valid

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_object_validator_invalid_type(strict):
    schema = {"a": "int", "b": "string"}
    validator = ObjectValidator(schema=schema, strict=strict)
    invalid_json = '{"a": "not_an_int", "b": "hello"}'
    if strict:
        result = await validator.validate_strict(invalid_json)
    else:
        result = await validator.validate_permissive(invalid_json)
    assert not result.is_valid
    assert "does not match schema" in result.error_message or "not valid JSON" in result.error_message

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_object_validator_missing_field(strict):
    schema = {"a": "int", "b": "string"}
    validator = ObjectValidator(schema=schema, strict=strict)
    missing_field_json = '{"a": 1}'
    if strict:
        result = await validator.validate_strict(missing_field_json)
    else:
        result = await validator.validate_permissive(missing_field_json)
    assert not result.is_valid
    assert "does not match schema" in result.error_message or "not valid JSON" in result.error_message

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_object_validator_invalid_json(strict):
    schema = {"a": "int", "b": "string"}
    validator = ObjectValidator(schema=schema, strict=strict)
    invalid_json = '{a: 1, b: "hello"}'  # Not valid JSON
    if strict:
        result = await validator.validate_strict(invalid_json)
    else:
        result = await validator.validate_permissive(invalid_json)
    assert not result.is_valid
    assert "not valid JSON" in result.error_message or "No valid JSON object found" in result.error_message

@pytest.mark.asyncio
async def test_object_validator_permissive_extracts_json():
    schema = {"a": "int", "b": "string"}
    validator = ObjectValidator(schema=schema, strict=False)
    text_with_json = 'Here is your object: {"a": 1, "b": "hello"} Thank you!'
    result = await validator.validate_permissive(text_with_json)
    assert result.is_valid
    assert result.validated_text == '{"a": 1, "b": "hello"}'

# --- Pydantic BaseModel tests ---
class MyModel(BaseModel):
    a: int
    b: str

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_object_validator_valid_pydantic(strict):
    validator = ObjectValidator(schema=MyModel, strict=strict)
    valid_json = '{"a": 42, "b": "world"}'
    if strict:
        result = await validator.validate_strict(valid_json)
    else:
        result = await validator.validate_permissive(valid_json)
    assert result.is_valid

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_object_validator_invalid_type_pydantic(strict):
    validator = ObjectValidator(schema=MyModel, strict=strict)
    invalid_json = '{"a": "oops", "b": "world"}'
    if strict:
        result = await validator.validate_strict(invalid_json)
    else:
        result = await validator.validate_permissive(invalid_json)
    assert not result.is_valid
    assert "does not match schema" in result.error_message or "not valid JSON" in result.error_message

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_object_validator_missing_field_pydantic(strict):
    validator = ObjectValidator(schema=MyModel, strict=strict)
    missing_field_json = '{"a": 42}'
    if strict:
        result = await validator.validate_strict(missing_field_json)
    else:
        result = await validator.validate_permissive(missing_field_json)
    assert not result.is_valid
    assert "does not match schema" in result.error_message or "not valid JSON" in result.error_message

# --- Hint generation tests ---
@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_object_validator_initial_hint_included(strict):
    schema = {"a": "int", "b": "string"}
    validator = ObjectValidator(schema=schema, strict=strict, generate_hints=True)
    invalid_json = '{"a": "not_an_int", "b": "hello"}'
    result = await validator.validate(invalid_json)
    if strict:
        assert result.hint is not None
        assert "Please ensure" in result.hint or "Please return only" in result.hint
    else:
        assert result.hint is None

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_object_validator_no_hint_when_disabled(strict):
    schema = {"a": "int", "b": "string"}
    validator = ObjectValidator(schema=schema, strict=strict, generate_hints=False)
    invalid_json = '{"a": "not_an_int", "b": "hello"}'
    result = await validator.validate(invalid_json)
    assert result.hint is None

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_object_validator_initial_hint_included_pydantic(strict):
    validator = ObjectValidator(schema=MyModel, strict=strict, generate_hints=True)
    invalid_json = '{"a": "not_an_int", "b": "hello"}'
    result = await validator.validate(invalid_json)
    if strict:
        assert result.hint is not None
        assert "Please ensure" in result.hint or "Please return only" in result.hint
    else:
        assert result.hint is None 