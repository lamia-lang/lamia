import pytest
from lamia.engine.validation_strategies.llm_validation_strategy import LLMValidationStrategy
from lamia.validation.validators import HTMLValidator, LengthValidator
from examples.custom_validators.code_validator import CodeValidator

async def test_config_loading_builtin_validators():
    html_validator = HTMLValidator(strict=True, generate_hints=True)
    length_validator = LengthValidator(max_length=20, strict=True, generate_hints=True)

    registry = {
        html_validator.name: html_validator,
        length_validator.name: length_validator,
    }

    strategy = LLMValidationStrategy(registry)
    result = await strategy.validate("<html>short</html>")
    assert result.is_valid
    result = await strategy.validate("<html>this is a very long html string</html>")
    assert not result.is_valid

async def test_config_loading_custom_class_validator():
    # Simulate config for a custom validator (class-based)
    validator_class = CodeValidator
    validator_instance = validator_class(language="python", strict=True, generate_hints=True)
    registry = {validator_instance.name: validator_instance}

    strategy = LLMValidationStrategy(registry)
    valid_code = "def foo():\n    return 1"
    invalid_code = "def foo(\n    return 1"
    result = await strategy.validate(valid_code)
    assert result.is_valid
    result = await strategy.validate(invalid_code)
    assert not result.is_valid
    assert "parsing failed" in result.error_message.lower() or "syntax" in result.error_message.lower() 