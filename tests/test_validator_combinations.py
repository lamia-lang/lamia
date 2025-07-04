import pytest
from lamia.adapters.llm.strategy import ValidationStrategy, RetryConfig
from lamia.validation.validators import HTMLValidator, LengthValidator

async def test_combined_html_and_length_validators():
    config = RetryConfig(
        max_retries=1,
        fallback_models=[],
        validators=[
            {"type": "html"},
            {"type": "length", "max_length": 20}
        ]
    )
    registry = {
        "html": HTMLValidator,
        "length": LengthValidator
    }
    strategy = ValidationStrategy(config, registry)

    # Valid HTML and length
    result = await strategy.validate_response("<html>short</html>")
    assert result.is_valid

    # Valid HTML, too long
    result = await strategy.validate_response("<html>this is a very long html string</html>")
    assert not result.is_valid
    assert "too long" in result.error_message

    # Not HTML
    result = await strategy.validate_response("plain text")
    assert not result.is_valid
    assert "Invalid HTML".lower() in result.error_message.lower() 