import pytest
from lamia.adapters.llm.validation.custom_loader import load_validator
from examples.custom_validators.code_validator import CodeValidator
from examples.custom_validators.sentiment_validator import validate_sentiment

# Built-in Validators Tests
class TestBuiltInValidators:
    def test_html_validator(self):
        validator = load_validator("html", {})
        
        # Test valid HTML
        valid_html = "<html><body><h1>Test</h1></body></html>"
        result = validator.validate(valid_html)
        assert result["is_valid"] is True
        assert result["error_message"] is None

        # Test invalid HTML
        invalid_html = "<html><body><h1>Test</h1></body>"
        result = validator.validate(invalid_html)
        assert result["is_valid"] is False
        assert result["error_message"] is not None

    def test_json_validator(self):
        validator = load_validator("json", {})
        
        # Test valid JSON
        valid_json = '{"key": "value", "number": 42}'
        result = validator.validate(valid_json)
        assert result["is_valid"] is True
        assert result["error_message"] is None

        # Test invalid JSON
        invalid_json = '{"key": "value", number: 42}'
        result = validator.validate(invalid_json)
        assert result["is_valid"] is False
        assert result["error_message"] is not None

    def test_regex_validator(self):
        config = {"pattern": "^[a-zA-Z0-9]+$"}
        validator = load_validator("regex", config)
        
        # Test valid pattern
        valid_text = "abc123"
        result = validator.validate(valid_text)
        assert result["is_valid"] is True
        assert result["error_message"] is None

        # Test invalid pattern
        invalid_text = "abc 123!"
        result = validator.validate(invalid_text)
        assert result["is_valid"] is False
        assert result["error_message"] is not None

    def test_length_validator(self):
        config = {"min_length": 5, "max_length": 10}
        validator = load_validator("length", config)
        
        # Test valid length
        valid_text = "Hello!"
        result = validator.validate(valid_text)
        assert result["is_valid"] is True
        assert result["error_message"] is None

        # Test too short
        short_text = "Hi"
        result = validator.validate(short_text)
        assert result["is_valid"] is False
        assert result["error_message"] is not None

        # Test too long
        long_text = "This is way too long"
        result = validator.validate(long_text)
        assert result["is_valid"] is False
        assert result["error_message"] is not None

# Custom Validators Tests
class TestCodeValidator:
    def test_python_code_validation(self):
        validator = CodeValidator(language="python", strict=True)
        
        # Test valid Python code
        valid_code = """
def hello():
    print("Hello, World!")
"""
        result = validator.validate(valid_code)
        assert result["is_valid"] is True
        assert result["error_message"] is None

        # Test invalid Python code
        invalid_code = """
def hello()
    print("Hello, World!")
"""
        result = validator.validate(invalid_code)
        assert result["is_valid"] is False
        assert result["error_message"] is not None

    def test_unsupported_language(self):
        validator = CodeValidator(language="javascript", strict=True)
        
        code = "console.log('Hello');"
        result = validator.validate(code)
        assert result["is_valid"] is False
        assert "Unsupported language" in result["error_message"]

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