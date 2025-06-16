import pytest
from pydantic import BaseModel
from lamia.adapters.llm.validation.validators.file_validators import XMLStructureValidator

# The tests that are common to all file structure validators should go to multi_file_format folder
# Tests exclusive to XML format should go here

class SimpleModel(BaseModel):
    title: str
    value: int

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_xml_structure_validator_xml_should_be_case_sensitive(strict):
    validator = XMLStructureValidator(model=SimpleModel, strict=strict)
    invalid_xml = '<root><TITLE>Test</TITLE><Value>123</value></root>'
    result = await validator.validate(invalid_xml)
    assert result.is_valid is False