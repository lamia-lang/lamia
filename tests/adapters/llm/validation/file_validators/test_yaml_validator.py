import pytest
from pydantic import BaseModel
from lamia.adapters.llm.validation.validators.file_validators import YAMLValidator


@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_yaml_structure_validator(strict):
    validator = YAMLValidator(strict=strict)
    valid_yaml = 'title: Test\nvalue: 123\n'
    invalid_yaml = 'title: Test\nvalue: abc\n'
    result = await validator.validate(valid_yaml)
    assert result.is_valid is True
    result = await validator.validate(invalid_yaml)
    assert result.is_valid is False 