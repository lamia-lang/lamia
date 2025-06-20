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

### Context-Aware vs Non-Context-Aware Validators

There are two styles of validators you can implement:

#### 1. Non-Context-Aware Validators
- **Implement only the `validate()` method.**
- These validators check the response as-is and do not "clean" or extract content.
- Example: SentimentValidator (see below).

**Example:**
```python
from lamia.validation.base import BaseValidator, ValidationResult

class SimpleSentimentValidator(BaseValidator):
    @property
    def name(self) -> str:
        return "sentiment"

    @property
    def initial_hint(self) -> str:
        return "Please ensure the response is positive."

    async def validate(self, response: str, **kwargs) -> ValidationResult:
        if "good" in response.lower() or "great" in response.lower():
            return ValidationResult(is_valid=True)
        return ValidationResult(is_valid=False, error_message="Response is not positive.")
```

#### 2. Context-Aware Validators
- **Implement both `validate_strict()` and `validate_permissive()` methods.**
- These validators extract or "clean" the relevant content in permissive mode, passing it to subsequent validators.
- Example: CodeValidator (see below).

**Example:**
```python
from lamia.validation.base import BaseValidator, ValidationResult
import ast
import re

class CodeValidator(BaseValidator):
    @property
    def name(self) -> str:
        return "code_python"

    @property
    def initial_hint(self) -> str:
        return "Please return only valid Python code, with no explanation or extra text."

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        try:
            ast.parse(response)
            return ValidationResult(is_valid=True)
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Code parsing failed: {str(e)}",
                hint=self.initial_hint
            )

    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        match = re.search(r'```(?:python)?\n([\s\S]+?)```', response)
        code = match.group(1) if match else response
        try:
            ast.parse(code)
            return ValidationResult(is_valid=True, validated_text=code)
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Code parsing failed: {str(e)}",
                hint=self.initial_hint
            )
```

**Important:**
- Do **not** implement both `validate()` and `validate_strict`/`validate_permissive` in the same class.
- If you implement only `validate()`, your validator is non-context-aware.
- If you implement both `validate_strict()` and `validate_permissive()`, your validator is context-aware.

---

### Strict and Forgiving Validation

Each validator supports a `strict` flag (set in config or code). If omitted, strict mode is used by default.
- `strict: true` (default): Only accepts pure, valid output (e.g., only the code, with no extra text).
- `strict: false`: Accepts output that contains a valid block (e.g., a valid code block within a longer response).

---

## Using Custom Validators in `