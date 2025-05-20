import pytest
from lamia.adapters.llm.validation.validators import HTMLValidator, JSONValidator, RegexValidator, LengthValidator
from examples.custom_validators.code_validator import CodeValidator
from examples.custom_validators.sentiment_validator import validate_sentiment
import asyncio

# Built-in Validators Tests
class TestBuiltInValidators:
    async def test_html_validator(self):
        validator = HTMLValidator()
        valid_html = "<html><body><h1>Test</h1></body></html>"
        result = await validator.validate(valid_html)
        assert result.is_valid is True
        assert result.error_message is None

        invalid_html = "<html><body><h1>Test</h1></body>"
        result = await validator.validate(invalid_html)
        assert result.is_valid is False
        assert result.error_message is not None

    async def test_json_validator(self):
        validator = JSONValidator()
        valid_json = '{"key": "value", "number": 42}'
        result = await validator.validate(valid_json)
        assert result.is_valid is True
        assert result.error_message is None

        invalid_json = '{"key": "value", number: 42}'
        result = await validator.validate(invalid_json)
        assert result.is_valid is False
        assert result.error_message is not None

    async def test_regex_validator(self):
        validator = RegexValidator(pattern="^[a-zA-Z0-9]+$")
        valid_text = "abc123"
        result = await validator.validate(valid_text)
        assert result.is_valid is True
        assert result.error_message is None

        invalid_text = "abc 123!"
        result = await validator.validate(invalid_text)
        assert result.is_valid is False
        assert result.error_message is not None

    async def test_length_validator(self):
        validator = LengthValidator(min_length=5, max_length=10)
        valid_text = "Hello!"
        result = await validator.validate(valid_text)
        assert result.is_valid is True
        assert result.error_message is None

        short_text = "Hi"
        result = await validator.validate(short_text)
        assert result.is_valid is False
        assert result.error_message is not None

        long_text = "This is way too long"
        result = await validator.validate(long_text)
        assert result.is_valid is False
        assert result.error_message is not None

# Custom Validators Tests
class TestCodeValidator:
    async def test_python_code_validation(self):
        validator = CodeValidator(language="python", strict=True)
        valid_code = """
def hello():
    print(\"Hello, World!\")
"""
        result = await validator.validate(valid_code)
        assert result.is_valid is True
        assert result.error_message is None

        invalid_code = """
def hello()
    print(\"Hello, World!\")
"""
        result = await validator.validate(invalid_code)
        assert result.is_valid is False
        assert result.error_message is not None

    async def test_unsupported_language(self):
        validator = CodeValidator(language="javascript", strict=True)
        code = "console.log('Hello');"
        result = await validator.validate(code)
        assert result.is_valid is False
        assert "Unsupported language" in result.error_message

class TestSentimentValidator:
    def test_positive_sentiment(self):
        text = "This is a great and wonderful example!"
        result = validate_sentiment(text)
        assert result["is_valid"] is True
        assert result["validation_data"]["positive_count"] == 2
        assert result["validation_data"]["negative_count"] == 0

    def test_negative_sentiment(self):
        text = "This is a terrible and horrible example."
        result = validate_sentiment(text)
        assert result["is_valid"] is False
        assert result["validation_data"]["positive_count"] == 0
        assert result["validation_data"]["negative_count"] == 2

    def test_neutral_text(self):
        text = "This is a simple example."
        result = validate_sentiment(text)
        assert result["is_valid"] is True  # No negative words, so should pass
        assert result["validation_data"]["positive_count"] == 0
        assert result["validation_data"]["negative_count"] == 0 