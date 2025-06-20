import pytest
from lamia.adapters.llm.strategy import ValidationStrategy, RetryConfig
from lamia.validators import HTMLValidator, LengthValidator
from examples.custom_validators.code_validator import CodeValidator

async def test_config_loading_builtin_validators():
    config = RetryConfig(
        max_retries=1,
        fallback_models=[],
        validators=[
            {"type": "html"},
            {"type": "length", "max_length": 10}
        ]
    )
    registry = {
        "html": HTMLValidator,
        "length": LengthValidator
    }
    strategy = ValidationStrategy(config, registry)
    result = await strategy.validate_response("<b>short</b>")
    assert result.is_valid
    result = await strategy.validate_response("<b>this is a very long html string</b>")
    assert not result.is_valid

async def test_config_loading_custom_class_validator():
    # Simulate config for a custom validator (class-based)
    validator_class = CodeValidator
    registry = {"code_python": validator_class}
    config = RetryConfig(
        max_retries=1,
        fallback_models=[],
        validators=[{"type": "code_python", "language": "python", "strict": True}]
    )
    strategy = ValidationStrategy(config, registry)
    valid_code = "def foo():\n    return 1"
    invalid_code = "def foo(\n    return 1"
    result = await strategy.validate_response(valid_code)
    assert result.is_valid
    result = await strategy.validate_response(invalid_code)
    assert not result.is_valid
    assert "parsing failed" in result.error_message.lower() or "syntax" in result.error_message.lower() 