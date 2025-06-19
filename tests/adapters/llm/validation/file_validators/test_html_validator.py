import pytest
from pydantic import BaseModel
from lamia.adapters.llm.validation.validators.file_validators import HTMLValidator
from typing import Any

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_html_validator(strict):
    validator = HTMLValidator(strict=strict)
    valid_html = '<html><title>Test</title><value>123</value></html>'
    invalid_html = '<title>Test</title><value>abc</value>'
    result = await validator.validate(valid_html)
    assert result.is_valid is True
    result = await validator.validate(invalid_html)
    assert result.is_valid is False 
