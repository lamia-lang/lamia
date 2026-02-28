import pytest
from pydantic import BaseModel
from lamia.validation.validators.file_validators import YAMLValidator


@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_yaml_validator(strict):
    validator = YAMLValidator(strict=strict)
    valid_yaml = 'title: Test\nvalue: 123\n'
    invalid_yaml = 'title: Test\nvalue\n'
    result = await validator.validate(valid_yaml)
    assert result.is_valid is True
    result = await validator.validate(invalid_yaml)
    assert result.is_valid is False 

# test_yaml_validator.py
def test_yaml_overwrites_on_append():
    validator = YAMLValidator()
    result = validator.prepare_content_for_write("old: 1\n", "new: 2\n")
    assert result == "new: 2\n"


@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_yaml_duplicate_keys_rejected(strict):
    validator = YAMLValidator(strict=strict)
    dup_payload = 'a: 1\nb: 2\na: 3'
    result = await validator.validate(dup_payload)
    assert not result.is_valid
    assert "Duplicate key" in (result.error_message or "")