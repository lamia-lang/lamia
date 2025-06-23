import pytest
from pydantic import BaseModel
from lamia.validation.validators.file_validators import XMLStructureValidator

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_xml_validator(strict):
    validator = XMLStructureValidator(strict=strict)
    valid_xml = '<root><title>Test</title><value>123</value></root>'
    invalid_xml = '<title>Test</title><value>abc</value>'
    result = await validator.validate(valid_xml)
    assert result.is_valid is True
    result = await validator.validate(invalid_xml)
    assert result.is_valid is False 