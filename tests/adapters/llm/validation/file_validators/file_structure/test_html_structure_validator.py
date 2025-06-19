import pytest
from pydantic import BaseModel
from lamia.adapters.llm.validation.validators.file_validators import HTMLStructureValidator
from typing import Any

# The tests that are common to all file structure validators should go to multi_file_format folder
# Tests exclusive to HTML format should go here

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_html_structure_validator_should_allow_doctype(strict):
    class HTMLModel(BaseModel):
      body: Any

    validator = HTMLStructureValidator(model=HTMLModel, strict=strict)
    valid_html = """
    <!DOCTYPE html>
    <html>
      <body>
      <p>123</p>
      </body>
    </html>
    """
    result = await validator.validate(valid_html)
    assert result.is_valid is True


@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_html_structure_validator_tag_to_model_field_case_insensitive_mapping(strict):
    class SimpleModel(BaseModel):
        title: str
        value: int

    validator = HTMLStructureValidator(model=SimpleModel, strict=strict)
    valid_xml = '<html><TITLE>Test</TITLE><Value>123</value></html>'
    result = await validator.validate(valid_xml)
    assert result.is_valid is True