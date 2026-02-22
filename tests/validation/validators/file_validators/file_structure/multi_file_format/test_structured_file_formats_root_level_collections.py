# This file tests validation of models where the root type is a collection (List[T], set[T], etc.)
import pytest
from pydantic import BaseModel
from lamia.validation.validators.file_validators import *
from typing import Any, List

# TODO: Enable these tests when we have a way to test the new logic
pytest.skip("skip this file", allow_module_level=True)

FILE_CONTENT_VALIDATOR_PAIR_TWO_DISTINCT_PARAGRAPHS = [
    ("<html><body><p>paragraph1</p><p>paragraph2</p><body></html>", HTMLStructureValidator),
    ("<root><p>paragraph1</p><p>paragraph2</p></root>", XMLStructureValidator),
    ('{"div1":{"p": "paragraph1"}, "div2":{"p": "paragraph2"}}', JSONStructureValidator), # JSON does not allow repetion of of the same key on the same level
    ("div1:\n  p: paragraph1\ndiv2:\n  p: paragraph2\n", YAMLStructureValidator), # YAML does not allow repetion of of the same key on the same level
    ("p;\nparagraph1;\nparagraph2;", CSVStructureValidator),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("file_content, validator_class", FILE_CONTENT_VALIDATOR_PAIR_TWO_DISTINCT_PARAGRAPHS)
async def test_file_structure_validator_should_select_first_when_many_fields_with_same_name(strict, file_content, validator_class):
    class P1(BaseModel):
      p: str

    validator = validator_class(model=P1, strict=False)
    result = await validator.validate(file_content)
    assert result.is_valid is True
    assert result.typed_result.p == "paragraph1"

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("file_content, validator_class", FILE_CONTENT_VALIDATOR_PAIR_TWO_DISTINCT_PARAGRAPHS)
async def test_file_structure_validator_check_one_type_in_list(strict, file_content, validator_class):
    class Paragraph(BaseModel):
      p: str

    validator = validator_class(model=List[Paragraph], strict=False)
    result = await validator.validate(file_content)
    assert result.is_valid is True
    assert len(result.typed_result) == 2
    assert result.typed_result[0].p == "paragraph1"
    assert result.typed_result[1].p == "paragraph2"

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("file_content, validator_class", FILE_CONTENT_VALIDATOR_PAIR_TWO_DISTINCT_PARAGRAPHS)
async def test_file_structure_validator_check_one_type_in_set_unique_items(strict, file_content, validator_class):
    class Paragraph(BaseModel):
      p: str

    validator = validator_class(model=set[Paragraph], strict=False)
    result = await validator.validate(file_content)
    assert result.is_valid is True
    assert len(result.typed_result) == 2
    assert result.typed_result[0].p == "paragraph1"
    assert result.typed_result[1].p == "paragraph2"

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("file_content, validator_class", [
    ("<html><body><p>dup_value</p><p>dup_value</p><body></html>", HTMLStructureValidator),
    ("<root><p>dup_value</p><p>dup_value</p></root>", XMLStructureValidator),
    ('{"div1":{"p": "dup_value"}, "div2":{"p": "dup_value"}}', JSONStructureValidator), # JSON does not allow repetion of of the same key on the same level
    ("div1:\n  p: dup_value\ndiv2:\n  p: dup_value\n", YAMLStructureValidator), # YAML does not allow repetion of of the same key on the same level
    ("p;\nparagraph1;\nparagraph2;", CSVStructureValidator),
])
async def test_file_structure_validator_check_one_type_in_set_unique_items(strict, file_content, validator_class):
    class Paragraph(BaseModel):
        p: str

    validator = validator_class(model=set[Paragraph], strict=False)
    result = await validator.validate(file_content)
    assert result.is_valid is True
    assert len(result.typed_result) == 1
    assert result.typed_result[0].p == "dup_value"

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("file_content, validator_class", [
    ("<html><body><p>Flat</p><p><span>non-flat</span></p><body></html>", HTMLStructureValidator),
    ("<root><p>Flat</p><p><span>non-flat</span></p></root>", XMLStructureValidator),
    ('{"div1":{"p": "Flat"}, "div2":{"p": {"span": "non-flat"}}}', JSONStructureValidator),
    ("div1:\n  p: Flat\ndiv2:\n  p: span: non-flat\n", YAMLStructureValidator)
])
async def test_file_structure_validator_flat_paragraphs_and_non_flat_paragraphs(strict, file_content, validator_class):
    class FlatAndNonFlatParagraphs(BaseModel):
      p: Any

    validator = validator_class(model=List[FlatAndNonFlatParagraphs], strict=strict)
    result = await validator.validate(file_content)
    assert result.is_valid is True
    assert len(result.typed_result) == 2
    assert result.typed_result.p == "Flat"
    if validator_class == HTMLStructureValidator:
        assert result.typed_result.p == "<span>non-flat</span>"
    elif validator_class == XMLStructureValidator:
        assert result.typed_result.p == "<span>non-flat</span>"
    elif validator_class == JSONStructureValidator:
        assert result.typed_result.p == {"span": "non-flat"}
    elif validator_class == YAMLStructureValidator:
        assert result.typed_result.p == "span: non-flat"

    class FlatParagraphs(BaseModel):
      p: str

    validator = validator_class(model=List[FlatParagraphs], strict=strict)
    result = await validator.validate(file_content)
    assert result.is_valid is True
    assert len(result.typed_result) == 1
    assert result.typed_result.p == "Flat"
    