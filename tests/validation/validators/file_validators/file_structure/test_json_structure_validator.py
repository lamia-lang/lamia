import pytest
from enum import Enum
from pydantic import BaseModel, Field
from lamia.validation.validators.file_validators import JSONStructureValidator

# The tests that are common to all file structure validators should go to multi_file_format folder
# Tests exclusive to JSON format should go here

class SimpleModel(BaseModel):
    title: str
    value: int

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_json_structure_validator(strict):
    validator = JSONStructureValidator(model=SimpleModel, strict=strict)
    valid_json = '{"title": "Test", "value": 123}'
    invalid_json = '{"title": "Test", "value": "abc"}'
    result = await validator.validate(valid_json)
    assert result.is_valid is True
    result = await validator.validate(invalid_json)
    assert result.is_valid is False


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskModel(BaseModel):
    title: str
    priority: Priority = Field(description="Task priority")


@pytest.mark.asyncio
async def test_json_initial_hint_includes_enum_values_in_structure():
    validator = JSONStructureValidator(model=TaskModel, strict=True, generate_hints=True)
    hint = validator.initial_hint
    assert "\"priority\": one of ['high', 'medium', 'low']" in hint


@pytest.mark.asyncio
async def test_json_schema_includes_enum_values():
    validator = JSONStructureValidator(model=TaskModel, strict=True, generate_hints=True)
    hint = validator.initial_hint
    assert '"enum":["high","medium","low"]' in hint


@pytest.mark.asyncio
async def test_json_enum_validation_accepts_valid_value():
    validator = JSONStructureValidator(model=TaskModel, strict=True, generate_hints=True)
    json_text = '{"title": "Fix bug", "priority": "high"}'
    result = await validator.validate(json_text)
    assert result.is_valid
    assert result.typed_result.priority == Priority.HIGH


@pytest.mark.asyncio
async def test_json_enum_validation_rejects_invalid_value():
    validator = JSONStructureValidator(model=TaskModel, strict=True, generate_hints=True)
    json_text = '{"title": "Fix bug", "priority": "urgent"}'
    result = await validator.validate(json_text)
    assert not result.is_valid