import pytest
from pydantic import BaseModel
from lamia.adapters.llm.validation.validators.file_validators import CSVValidator

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_csv_validator(strict):
    validator = CSVValidator(strict=strict)
    valid_csv = 'title,value\nTest,123\nFoo,456\n'
    invalid_csv = 'title,value\nTest,abc\nFoo\n'
    result = await validator.validate(valid_csv)
    assert result.is_valid is True
    result = await validator.validate(invalid_csv)
    assert result.is_valid is False