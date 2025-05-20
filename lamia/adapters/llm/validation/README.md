# Validation Module

This module provides a flexible framework for validating LLM responses in Lamia. Validators can be combined, customized, and configured via `config.yaml` to ensure your outputs meet quality and format requirements.

---

## Built-in Validators

- **HTMLValidator**: Checks if the response is well-formed HTML.
- **JSONValidator**: Checks if the response is valid JSON.
- **RegexValidator**: Checks if the response matches a given regex pattern.
- **LengthValidator**: Checks if the response length is within specified bounds.

---

## Combining/Nesting Validators

You can combine multiple validators in your `config.yaml` file. Validators are applied in sequence; the response must pass all to be considered valid.

**Example: Check that a response is valid HTML and does not exceed 1000 characters:**

```yaml
validation:
  enabled: true
  validators:
    - type: "html"
    - type: "length"
      max_length: 1000
```

You can combine any number of built-in or custom validators this way.

---

## Creating Custom Validators

You can create custom validators as either classes (subclassing `BaseValidator`) or as standalone functions.

### Class-based Example

Create a file, e.g., `examples/custom_validators/code_validator.py`:

```python
from lamia.adapters.llm.validation.base import BaseValidator, ValidationResult
import ast

class CodeValidator(BaseValidator):
    @property
    def name(self) -> str:
        return "code_python"

    async def validate(self, response: str, **kwargs) -> ValidationResult:
        # Try to parse the response as Python code
        try:
            ast.parse(response)
            return ValidationResult(
                is_valid=True,
                error_message=None,
                validation_data={"reason": "Code parsed successfully"}
            )
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Code parsing failed: {str(e)}",
                validation_data={"reason": str(e)}
            )
```

### Function-based Example

Create a function, e.g., `examples/custom_validators/sentiment_validator.py`:

```python
def validate_sentiment(response: str, **kwargs):
    # Fake validation: succeed if 'good' is in the response, fail otherwise
    if 'good' in response.lower():
        return {
            "is_valid": True,
            "error_message": None,
            "validation_data": {"reason": "Found 'good' in response"}
        }
    else:
        return {
            "is_valid": False,
            "error_message": "Response does not contain 'good'",
            "validation_data": {"reason": "Missing 'good'"}
        }
```

---

## Using Custom Validators in `