import pytest
from pydantic import BaseModel
from collections import OrderedDict
from lamia.validation.validators.file_validators import MarkdownStructureValidator
from lamia.validation.validators.file_validators.file_structure.markdown_structure_validator import (
    Heading1, Heading2, Heading3, Heading4, Heading5, Heading6,
    Paragraph, Blockquote, OrderedList, UnorderedList, ListItem,
    DefinitionList, DefinitionTerm, DefinitionDescription,
    CodeBlock, FencedCode, IndentedCode,
    Table, TableRow, TableCell, HorizontalRule,
)
import mistune

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

def print_ast(markdown):
    """Helper function to print the AST for debugging."""
    ast = mistune.create_markdown(renderer='ast')(markdown)
    print(f"\nAST for markdown:\n{markdown}\n")
    print("AST structure:")
    print(ast)
    return ast

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("element_type,sample_text,context", [
    # Headers (no context needed)
    (Heading1, "# Heading 1", None),
    (Heading2, "## Heading 2", None),
    (Heading3, "### Heading 3", None),
    (Heading4, "#### Heading 4", None),
    (Heading5, "##### Heading 5", None),
    (Heading6, "###### Heading 6", None),
    
    # Block elements (no context needed)
    (Paragraph, "This is a paragraph.", None),
    (Blockquote, "> This is a blockquote.", None),
    (HorizontalRule, "---", None),
    
    # Lists
    (OrderedList, "1. First item\n2. Second item", None),
    (UnorderedList, "- First bullet\n- Second bullet", None),
    
    # Code blocks
    (CodeBlock, "```\ncode\n```", None),
    (FencedCode, "```python\ndef hello():\n    print('Hello')\n```", None),
    (IndentedCode, "    indented code block", None),
])
async def test_markdown_structure_validator_element_types(strict, element_type, sample_text, context):
    """Test each markdown element type with proper context where needed."""
    class SingleElementModel(BaseModel):
        content: element_type

    validator = MarkdownStructureValidator(model=SingleElementModel, strict=strict)
    
    # If context is provided, insert the sample text into it
    test_text = context.format(content=sample_text) if context else sample_text
    
    # Print AST for debugging
    ast = print_ast(test_text)
    
    result = await validator.validate(test_text)
    assert result.is_valid is True, f"Failed to validate {element_type.__name__} with text:\n{test_text}\nError: {result.error_message}"
    
    # Verify type and content
    assert isinstance(result.result_type.content, element_type)
    assert result.result_type.content.text.strip(), f"Empty text for {element_type.__name__}"
    
    # Test invalid format
    if element_type in [Heading1, Heading2, Heading3, Heading4, Heading5, Heading6]:
        invalid_text = f"#{element_type.__name__}"  # No space after #
    elif element_type == Blockquote:
        invalid_text = "Not a blockquote"  # Missing >
    else:
        invalid_text = ""  # Empty text for other types
    
    if invalid_text:
        result = await validator.validate(invalid_text)
        assert result.is_valid is False, f"Invalid format not caught for {element_type.__name__}"
        assert "Missing element(s)" in result.error_message

