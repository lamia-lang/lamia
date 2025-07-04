import pytest
from pydantic import BaseModel
from collections import OrderedDict
from lamia.validation.validators.file_validators import MarkdownStructureValidator
from lamia.validation.validators.file_validators.file_structure.markdown_structure_validator import Heading1, Heading2, Paragraph

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
    assert result.is_valid
    # Check raw text values
    assert result.validated_text['title'] == "My Title"
    assert result.validated_text['intro'] == "This is the intro paragraph."
    assert result.validated_text['subtitle'] == "Subsection"
    assert result.validated_text['body'] == "This is the body paragraph."
    
    # Check typed values in result_type
    assert isinstance(result.result_type, MyDocumentModel)
    print(type(result.result_type.title))
    assert isinstance(result.result_type.title, Heading1)
    assert isinstance(result.result_type.intro, Paragraph)
    assert isinstance(result.result_type.subtitle, Heading2)
    assert isinstance(result.result_type.body, Paragraph)
    
    # Check the actual values in typed fields using .text property
    assert result.result_type.title.text == "My Title"
    assert result.result_type.intro.text == "This is the intro paragraph."
    assert result.result_type.subtitle.text == "Subsection"
    assert result.result_type.body.text == "This is the body paragraph."

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_markdown_structure_validator_invalid_md_file(strict):
    class TitleOnlyModel(BaseModel):
        title: Heading2

    validator2 = MarkdownStructureValidator(model=TitleOnlyModel, strict=strict)
    invalid_md2 = '##title text must be whitespaced after the hash in markdown'
    result2 = await validator2.validate(invalid_md2)
    assert not result2.is_valid
    assert "Missing element(s) for field(s): title" in result2.error_message

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
    assert result.result_type.intro == "This is the intro paragraph."

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_markdown_structure_validator_ordered_fields_correct_order(strict):
    """Test that OrderedDict validation passes when markdown elements are in correct order."""
    markdown_content = """# Test Title

This is a paragraph.

## Subsection

Another paragraph here.
"""

    class RequestModel(BaseModel):
        __ordered_fields__ = OrderedDict([
            ("title", Heading1),
            ("intro", Paragraph),
            ("subtitle", Heading2),
            ("body", Paragraph),
        ])
    
    validator = MarkdownStructureValidator(model=RequestModel, strict=strict)
    
    result = await validator.validate(markdown_content)
    assert result.is_valid is True
    print(result)
    assert result.result_type.title.text == "Test Title"
    assert result.result_type.intro.text == "This is a paragraph."
    assert result.result_type.subtitle.text == "Subsection"
    assert result.result_type.body.text == "Another paragraph here."

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_markdown_structure_validator_ordered_fields_incorrect_order(strict):
    """Test that OrderedDict validation fails when markdown elements are in wrong order."""
    # Content has Heading2 before Heading1 (wrong order)
    markdown_content = """## Subsection First

This is a paragraph.

# Test Title

Another paragraph here.
"""

    class RequestModel(BaseModel):
        __ordered_fields__ = OrderedDict([
            ("title", Heading1),
            ("intro", Paragraph),
            ("subtitle", Heading2),
            ("body", Paragraph),
        ])
    
    # Model expects Heading1 first, then Paragraph, then Heading2, then Paragraph
    validator = MarkdownStructureValidator(model=RequestModel, strict=strict)
    
    result = await validator.validate(markdown_content)
    # Should fail because field order doesn't match expected order
    assert result.is_valid is False
    assert "field order" in result.error_message.lower()
