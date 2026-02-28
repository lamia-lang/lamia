import pytest
from pydantic import BaseModel
from lamia.validation.validators.file_validators import JSONValidator

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_json_validator(strict):
    validator = JSONValidator(strict=strict)
    valid_json = '{"title": "Test", "value": 123}'
    invalid_json = '{"title": "Test", "value": abc}'
    result = await validator.validate(valid_json)
    assert result.is_valid is True
    result = await validator.validate(invalid_json)
    assert result.is_valid is False

# test_json_validator.py
def test_json_overwrites_on_append():
    validator = JSONValidator()
    result = validator.prepare_content_for_write('{"old": 1}', '{"new": 2}')
    assert result == '{"new": 2}'


@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_json_duplicate_keys_rejected(strict):
    validator = JSONValidator(strict=strict)
    dup_payload = '{"a": 1, "b": 2, "a": 3}'
    result = await validator.validate(dup_payload)
    assert not result.is_valid
    assert "Duplicate key" in (result.error_message or "")