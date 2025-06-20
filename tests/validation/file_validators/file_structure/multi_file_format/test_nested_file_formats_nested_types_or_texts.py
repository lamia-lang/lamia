# NOTE: Type checking logic is now tested in unit tests for TypeMatcher. These tests remain as integration tests for file structure validators.
import pytest
from pydantic import BaseModel
from lamia.validation.validators.file_validators import *
from typing import Any

FILE_CONTENT_VALIDATOR_PAIR_WITH_PRIMITIVES_TYPES = [
    (
        '<html><head><title>Test</title></head><body><p>This is a paragraph.</p></body></html>',
        HTMLStructureValidator,
    ),
    (
        '<root><head><title>Test</title></head><body><p>This is a paragraph.</p></body></root>',
        XMLStructureValidator,
    ),
    (
        '{"head": {"title": "Test"}, "body": {"p": "This is a paragraph."}}',
        JSONStructureValidator,
    ),
    (
        'head:\n  title: Test\nbody:\n  p: This is a paragraph.\n',
        YAMLStructureValidator,
    ),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("file_content, validator_class", FILE_CONTENT_VALIDATOR_PAIR_WITH_PRIMITIVES_TYPES)
async def test_file_structure_validator_deep_nesting(strict, file_content, validator_class):
    class TwoLevelNesting(BaseModel):
        title: str
        p: str

    validator = validator_class(model=TwoLevelNesting, strict=strict)  
    result = await validator.validate(file_content)
    assert result.is_valid is not strict
    if not strict:
        assert result.result_type.p == "This is a paragraph."
        assert result.result_type.title == "Test"
    else:
        assert result.error_message == "Missing <title>; Missing <p>"



@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("file_content, validator_class", FILE_CONTENT_VALIDATOR_PAIR_WITH_PRIMITIVES_TYPES)
async def test_file_structure_validator_exact_nestig(strict, file_content, validator_class):
    class Paragraph(BaseModel):
        p: str

    class Title(BaseModel):
        title: str

    class Root(BaseModel):
        head: Title
        body: Paragraph

    validator = validator_class(model=Root, strict=strict)  
    result = await validator.validate(file_content)
    assert result.is_valid is True
    assert result.result_type.body.p == "This is a paragraph."
    assert result.result_type.head.title == "Test"

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("file_content, validator_class", FILE_CONTENT_VALIDATOR_PAIR_WITH_PRIMITIVES_TYPES)
async def test_file_structure_validator_complex_text_structure_to_str(strict, file_content, validator_class):
    class Model(BaseModel):
        head: str

    validator = validator_class(model=Model, strict=strict)
    result = await validator.validate(file_content)
    assert result.is_valid is False

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("file_content, validator_class", FILE_CONTENT_VALIDATOR_PAIR_WITH_PRIMITIVES_TYPES)
async def test_file_structure_validator_direct_children_with_any_type(strict, file_content, validator_class):
    class Model(BaseModel):
      head: Any
      body: Any

    validator = validator_class(model=Model, strict=strict)
    result = await validator.validate(file_content)
    assert result.is_valid is True
    if validator_class == HTMLStructureValidator:
        assert result.result_type.head == "<head><title>Test</title></head>"
        assert result.result_type.body == "<body><p>This is a paragraph.</p></body>"
    elif validator_class == XMLStructureValidator:
        assert result.result_type.head == "<head><title>Test</title></head>"
        assert result.result_type.body == "<body><p>This is a paragraph.</p></body>"
    elif validator_class == JSONStructureValidator:
        assert result.result_type.head == '{"title":"Test"}'
        assert result.result_type.body == '{"p":"This is a paragraph."}'
    elif validator_class == YAMLStructureValidator:
        assert result.result_type.head == 'title: Test\n'
        assert result.result_type.body == 'p: This is a paragraph.\n'

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("file_content, validator_class", FILE_CONTENT_VALIDATOR_PAIR_WITH_PRIMITIVES_TYPES)
async def test_html_structure_validator_incorrect_type_with_complex_model(strict, file_content, validator_class):
    class HeadModel(BaseModel):
      title: str

    class BodyModel(BaseModel):
      p: int

    class HTMLModel(BaseModel):
      head: HeadModel
      body: BodyModel

    validator = HTMLStructureValidator(model=HTMLModel, strict=strict)
    result = await validator.validate(file_content)
    assert result.is_valid is False
