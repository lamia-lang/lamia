import pytest
from pydantic import BaseModel
from lamia.adapters.llm.validation.validators.file_validators import MarkdownStructureValidator
from lamia.adapters.llm.validation.validators.file_validators.file_structure.markdown_structure_validator import Heading1, Heading2, Paragraph

# Markdown is not a structured format, and in Lamia it is treated as a structured format by predefined classes like Heading1, Heading2, Paragraph, etc.

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_markdown_structure_validator_valid(strict):
    class MyDocumentModel(BaseModel):
        title: Heading1
        intro: Paragraph
        subtitle: Heading2
        body: Paragraph

    validator = MarkdownStructureValidator(model=MyDocumentModel, strict=strict)
    md = """
# My Title

This is the intro paragraph.

## Subsection

This is the body paragraph.
"""
    result = await validator.validate(md)
    print(result)
    assert result.is_valid
    assert result.validated_text['title'] == "My Title"
    assert result.validated_text['intro'] == "This is the intro paragraph."
    assert result.validated_text['subtitle'] == "Subsection"
    assert result.validated_text['body'] == "This is the body paragraph."

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_markdown_structure_validator_invalid_md_file(strict):
    class TitleOnlyModel(BaseModel):
        title: str

    validator = MarkdownStructureValidator(model=TitleOnlyModel, strict=strict)
    invalid_md1 = '**not closed bold text'
    result = await validator.validate(invalid_md1)
    assert not result.is_valid  
    invalid_md2 = '##title text must be whitespaced after the hash in markdown'
    result = await validator.validate(invalid_md2)
    assert not result.is_valid

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_markdown_structure_validator_missing_fields_in_text(strict):
    class MyDocumentModel(BaseModel):
        title: Heading1
        intro: Paragraph
        subtitle: Heading2
        body: Paragraph

    validator = MarkdownStructureValidator(model=MyDocumentModel, strict=strict)
    md = """
# My Title

## Subsection

This is the body paragraph.
"""
    result = await validator.validate(md)
    assert result.is_valid is False

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_markdown_structure_validator_additional_texts_in_file(strict):
    class MyDocumentModel(BaseModel):
        title: Heading1
        intro: Paragraph
        subtitle: Heading2
        body: Paragraph

    validator = MarkdownStructureValidator(model=MyDocumentModel, strict=strict)
    md = """
# My Title
# This is the additional Heading1

This is the intro paragraph.

This is the additional text.

## Subsection

This is the body paragraph.

This is the additional text.
"""
    result = await validator.validate(md)
    assert result.is_valid is not strict
    if result.is_valid:
        assert result.validated_text['title'] == "My Title"
        assert result.validated_text['intro'] == "This is the intro paragraph."
        assert result.validated_text['subtitle'] == "Subsection"
        assert result.validated_text['body'] == "This is the body paragraph."

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_markdown_structure_validator_should_select_first_when_many_fields_sameType(strict):
    class P1(BaseModel):
        intro: Paragraph

    validator = MarkdownStructureValidator(model=MyDocumentModel, strict=strict)
    md = """
# My Title
# This is the additional Heading1

This is the intro paragraph.

This is the additional text.

## Subsection

This is the third paragraph.
This is another text.
"""
    validator = MarkdownStructureValidator(model=P1, strict=False)
    result = await validator.validate(md)
    assert result.is_valid is True
    assert result.result_type.p == "This is the intro paragraph"