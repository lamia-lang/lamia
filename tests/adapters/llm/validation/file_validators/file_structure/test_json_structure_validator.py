import pytest
from pydantic import BaseModel
from lamia.adapters.llm.validation.validators.file_validators import JSONStructureValidator

class SimpleModel(BaseModel):
    title: str
    value: int

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_json_structure_validator(strict):
    validator = JSONStructureValidator(model=SimpleModel, strict=strict)
    valid_json = '{"title": "Test", "value": 123}'
    invalid_json = '{"title": "Test", "value": "abc"}'
    result = await validator.validate(valid_json)
    assert result.is_valid is True
    result = await validator.validate(invalid_json)
    assert result.is_valid is False 