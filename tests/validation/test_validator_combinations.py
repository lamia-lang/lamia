import pytest
from lamia.engine.validation_strategies.llm_validation_strategy import LLMValidationStrategy
from lamia.validation.validators import HTMLValidator, LengthValidator

async def test_combined_html_and_length_validators():
    html_validator = HTMLValidator(strict=True, generate_hints=True)
    length_validator = LengthValidator(max_length=20, strict=True, generate_hints=True)

    registry = {
        html_validator.name: html_validator,
        length_validator.name: length_validator,
    }

    strategy = LLMValidationStrategy(registry)

    # Valid HTML and length
    result = await strategy.validate("<html>short</html>")
    assert result.is_valid

    # Valid HTML, too long
    result = await strategy.validate("<html>this is a very long html string</html>")
    assert not result.is_valid
    assert "too long" in result.error_message

    # Not HTML
    result = await strategy.validate("plain text")
    assert not result.is_valid
    assert "Invalid HTML".lower() in result.error_message.lower() 