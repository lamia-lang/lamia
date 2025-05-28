import pytest
from pydantic import BaseModel
from lamia.adapters.llm.validation.validators.file_validators import XMLStructureValidator

class SimpleModel(BaseModel):
    title: str
    value: int

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_xml_structure_validator(strict):
    validator = XMLStructureValidator(model=SimpleModel, strict=strict)
    valid_xml = '<root><title>Test</title><value>123</value></root>'
    invalid_xml = '<root><title>Test</title><value>abc</value></root>'
    result = await validator.validate(valid_xml)
    assert result.is_valid is True
    result = await validator.validate(invalid_xml)
    assert result.is_valid is False 