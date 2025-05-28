import pytest
from pydantic import BaseModel
from lamia.adapters.llm.validation.validators.file_validators import HTMLStructureValidator

class SimpleModel(BaseModel):
    title: str
    value: int

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_html_structure_validator(strict):
    validator = HTMLStructureValidator(model=SimpleModel, strict=strict)
    valid_html = """
    <title>Test</title>
    <value>123</value>
    """
    invalid_html = """
    <title>Test</title>
    <value>abc</value>
    """
    result = await validator.validate(f"<root>{valid_html}</root>")
    assert result.is_valid is True
    result = await validator.validate(f"<root>{invalid_html}</root>")
    assert result.is_valid is False 