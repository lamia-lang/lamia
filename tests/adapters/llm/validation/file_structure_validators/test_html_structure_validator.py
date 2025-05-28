import pytest
from pydantic import BaseModel
from lamia.adapters.llm.validation.validators.file_validators import HTMLStructureValidator
from typing import Any

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_html_structure_validator_head_and_body_present(strict):
    class HTMLModel(BaseModel):
      head: Any
      body: Any

    validator = HTMLStructureValidator(model=HTMLModel, strict=strict)
    valid_html = """
    <html>
      <head>
      <title>Test</title>
      </head>
      <body>
      <p>123</p>
      </body>
    </html>
    """
    result = await validator.validate(valid_html)
    assert result.is_valid is True

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_html_structure_validator_valid_without_head_and_body(strict):
    class HTMLModel(BaseModel):
      head: Any
      body: Any

    validator = HTMLStructureValidator(model=HTMLModel, strict=strict)
    valid_html = """
    <html>
    </html>
    """
    result = await validator.validate(valid_html)
    assert result.is_valid is False

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_html_structure_validator_empty_html(strict):
    class HTMLModel(BaseModel):
      head: Any
      body: Any

    validator = HTMLStructureValidator(model=HTMLModel, strict=strict)
    empty_html = ""
    result = await validator.validate(empty_html)
    assert result.is_valid is False

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_html_structure_validator_deep_nesting(strict):
    class HTMLModel(BaseModel):
      title: str
      p: str

    validator = HTMLStructureValidator(model=HTMLModel, strict=strict)
    html = """
    <html>
      <head>
        <title>Test</title>
      </head>
      <body>
        <p>123</p>
      </body>
    </html>
    """
    result = await validator.validate(html)
    assert result.is_valid is not strict

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_html_structure_validator_correct_type_with_complex_model(strict):
    class HeadModel(BaseModel):
      title: str

    class BodyModel(BaseModel):
      p: int

    class HTMLModel(BaseModel):
      head: HeadModel
      body: BodyModel

    validator = HTMLStructureValidator(model=HTMLModel, strict=strict)
    html = """
    <html>
      <head>
        <title>Test</title>
      </head>
      <body>
        <p>123</p>
      </body>
    <html>
    """
    result = await validator.validate(html)
    assert result.is_valid is True

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_html_structure_validator_correct_type_with_complex_model(strict):
    class HeadModel(BaseModel):
      title: str

    class BodyModel(BaseModel):
      p: int

    class HTMLModel(BaseModel):
      head: HeadModel
      body: BodyModel

    validator = HTMLStructureValidator(model=HTMLModel, strict=strict)
    html = """
    <html>
      <head>
        <title>Test</title>
      </head>
      <body>
        <p>abc</p>
      </body>
    <html>
    """
    result = await validator.validate(html)
    assert result.is_valid is False