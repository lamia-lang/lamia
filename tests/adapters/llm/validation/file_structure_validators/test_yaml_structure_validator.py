import pytest
from pydantic import BaseModel
from lamia.adapters.llm.validation.validators.file_structure_validators import YAMLStructureValidator

class SimpleModel(BaseModel):
    title: str
    value: int

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_yaml_structure_validator(strict):
    validator = YAMLStructureValidator(model=SimpleModel, strict=strict)
    valid_yaml = 'title: Test\nvalue: 123\n'
    invalid_yaml = 'title: Test\nvalue: abc\n'
    result = await validator.validate(valid_yaml)
    assert result.is_valid is True
    result = await validator.validate(invalid_yaml)
    assert result.is_valid is False 