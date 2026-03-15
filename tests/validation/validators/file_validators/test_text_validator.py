import pytest

from lamia.validation.validators.file_validators import TextValidator


@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_text_validator_always_valid(strict):
    validator = TextValidator(strict=strict)
    result = await validator.validate("Hello, world!")
    assert result.is_valid is True
    assert result.typed_result == "Hello, world!"
    assert result.validated_text == "Hello, world!"


@pytest.mark.asyncio
async def test_text_validator_strips_markdown_fences():
    validator = TextValidator()
    fenced = "```\nsome code\n```"
    result = await validator.validate(fenced)
    assert result.is_valid is True
    assert isinstance(result.typed_result, str)
    assert "```" not in result.typed_result
    assert "some code" in result.typed_result


@pytest.mark.asyncio
async def test_text_validator_strips_whitespace():
    validator = TextValidator()
    result = await validator.validate("  padded text  ")
    assert result.typed_result == "padded text"


@pytest.mark.asyncio
async def test_text_validator_empty_string():
    validator = TextValidator()
    result = await validator.validate("")
    assert result.is_valid is True
    assert result.typed_result == ""