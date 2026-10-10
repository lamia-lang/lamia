import pytest
from enum import Enum
from pydantic import BaseModel, Field
from lamia.validation.validators.file_validators import XMLStructureValidator

# The tests that are common to all file structure validators should go to multi_file_format folder
# Tests exclusive to XML format should go here

class SimpleModel(BaseModel):
    title: str
    value: int

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_xml_structure_validator_xml_should_be_case_sensitive(strict):
    validator = XMLStructureValidator(model=SimpleModel, strict=strict)
    invalid_xml = '<root><TITLE>Test</TITLE><Value>123</value></root>'
    result = await validator.validate(invalid_xml)
    assert result.is_valid is False


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskModel(BaseModel):
    title: str
    priority: Priority = Field(description="Task priority")


@pytest.mark.asyncio
async def test_xml_initial_hint_includes_enum_values():
    validator = XMLStructureValidator(model=TaskModel, strict=True, generate_hints=True)
    hint = validator.initial_hint
    assert "<priority>one of ['high', 'medium', 'low']</priority>" in hint


@pytest.mark.asyncio
async def test_xml_enum_validation_accepts_valid_value():
    validator = XMLStructureValidator(model=TaskModel, strict=False, generate_hints=True)
    xml = "<root><title>Fix bug</title><priority>high</priority></root>"
    result = await validator.validate(xml)
    assert result.is_valid
    assert result.typed_result.priority == Priority.HIGH


@pytest.mark.asyncio
async def test_xml_enum_validation_rejects_invalid_value():
    validator = XMLStructureValidator(model=TaskModel, strict=False, generate_hints=True)
    xml = "<root><title>Fix bug</title><priority>urgent</priority></root>"
    result = await validator.validate(xml)
    assert not result.is_valid


EMAIL_PATTERN = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"


class ContactWithRegex(BaseModel):
    name: str
    email: str = Field(pattern=EMAIL_PATTERN, description="Valid email")


@pytest.mark.asyncio
async def test_xml_initial_hint_includes_regex_pattern():
    validator = XMLStructureValidator(model=ContactWithRegex, strict=True, generate_hints=True)
    hint = validator.initial_hint
    assert "pattern" in hint
    assert "[a-zA-Z0-9._%+-]+" in hint