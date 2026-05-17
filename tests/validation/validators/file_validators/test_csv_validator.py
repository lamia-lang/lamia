import pytest
from pydantic import BaseModel
from lamia.validation.validators.file_validators import CSVValidator

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_csv_validator(strict):
    validator = CSVValidator(strict=strict)
    valid_csv = 'title,value\nTest,123\nFoo,456\n'
    # Use a CSV that actually breaks csv.DictReader parsing (unquoted newline in field)
    invalid_csv = 'title,value\nTest\n,123\nFoo,456'
    result = await validator.validate(valid_csv)
    assert result.is_valid is True
    result = await validator.validate(invalid_csv)
    assert result.is_valid is False


class TestCSVValidatorAppend:

    def test_append_strips_duplicate_header(self) -> None:
        validator = CSVValidator()
        existing = "name,age\nAlice,30\n"
        new = "name,age\nBob,25\n"
        result = validator.prepare_content_for_write(existing, new)
        assert result == "name,age\nAlice,30\nBob,25\n"

    def test_append_keeps_everything_on_empty_file(self) -> None:
        validator = CSVValidator()
        result = validator.prepare_content_for_write("", "name,age\nAlice,30\n")
        assert result == "name,age\nAlice,30\n"

    def test_append_inserts_row_separator_when_existing_has_no_trailing_newline(self) -> None:
        validator = CSVValidator()
        existing = "name,age\nAlice,30\nBob,25"
        new = "name,age\nCarol,22\n"
        result = validator.prepare_content_for_write(existing, new)
        assert result == "name,age\nAlice,30\nBob,25\nCarol,22\n"