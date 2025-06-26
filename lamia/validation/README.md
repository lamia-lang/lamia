# Validation Module

This module provides a flexible framework for validating LLM responses in Lamia. Validators can be combined, customized to ensure your outputs meet quality and format requirements.

---

## Built-in Validators
### File validators
- **HTMLValidator**: Checks if the response is well-formed HTML.
- **JSONValidator**: Checks if the response is valid JSON.
- **YAMLValidator**: Checks if the response is valid YAML.
- **XMLValidator**: Checks if the response is valid XML.
- **MarkdownValidator**: Checks if the response is valid Markdown.
- **CSVValidator**: Checks if the response is valid CSV.

### File Structure Validators

These validators not only check if the response is valid in the given format, but also validate that it matches a specific Pydantic model structure:

- **JSONStructureValidator**: Validates JSON against a Pydantic model schema
- **YAMLStructureValidator**: Validates YAML against a Pydantic model schema  
- **XMLStructureValidator**: Validates XML against a Pydantic model schema
- **HTMLStructureValidator**: Validates HTML against a Pydantic model schema
- **MarkdownStructureValidator**: Validates Markdown against a Pydantic model schema
- **CSVStructureValidator**: Validates CSV against a Pydantic model schema

### Other Validators
- **ObjectValidator**: Checks if the response is of the requested type
- **RegexValidator**: Checks if the response matches a given regex pattern.
- **LengthValidator**: Checks if the response length is within specified bounds.
- **FunctionalValidator**: Executes custom validation logic using a provided function.

---

## Ways of using validators

1. From Python code: Lamia(..., validators=[...])
2. By defining in config.yaml to use from the command line

## Combining/Nesting Validators

You can combine multiple validators in your `config.yaml` file or when initializing Lamia construct . Validators are applied in sequence; the response must pass all to be considered valid.

**Example: Check that a response is valid HTML and does not exceed 1000 characters:**

``` html_with_max_check_engine  = Lamia(...)

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

#### 1. Simple Validators
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

#### 2. Validators with strict or permissive support
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

You will need to create a strict code validator instance with 

CodeValidator(strict=True) and just call a validate() on it. You do not need to call validate_permissive() or validate_strict() directly. That allows to use all validators with a same command

---

### Strict and Forgiving Validation

Each validator supports a `strict` flag (set in config or code). If omitted, strict mode is used by default.
- `strict: true` (default): Only accepts pure, valid output (e.g., only the code, with no extra text).
- `strict: false`: Accepts output that contains a valid block (e.g., a valid code block within a longer response).

---

**Important:**
- Do **not** implement both `validate()` and `validate_strict`/`validate_permissive` in the same class.
- If you implement only `validate()`, your validator is non-context-aware.
- If you implement both `validate_strict()` and `validate_permissive()`, your validator is context-aware.

## Implementing File Validators

Generally, file validators need to support both strict or permissive modes. You can create a
new file validator for not yet supported file type by extending `DocumentStructureValidator`.

### Using DocumentStructureValidator

The `DocumentStructureValidator` is an abstract base class that provides a framework for validating structured documents against Pydantic models. It handles the heavy lifting of:

- **Payload extraction**: Finding the relevant content in LLM responses (with or without markdown code blocks)
- **Structure validation**: Recursively validating nested Pydantic models
- **Type conversion**: Converting parsed data to expected types using TypeMatcher
- **Error handling**: Providing helpful error messages and hints
- **Strict vs permissive modes**: Supporting both validation approaches

### Abstract Methods to Implement

When extending `DocumentStructureValidator`, you need to implement these abstract methods:

```python
from lamia.validation.validators.file_validators.file_structure.document_structure_validator import DocumentStructureValidator

class MyFormatStructureValidator(DocumentStructureValidator):
    @classmethod
    def name(cls) -> str:
        """Return the validator name for configuration (e.g., 'my_format_structure')"""
        return "my_format_structure"

    @classmethod  
    def file_type(cls) -> str:
        """Return the file type name (e.g., 'MyFormat')"""
        return "my_format"

    def extract_payload(self, response: str) -> str:
        """Extract the relevant data block from the response string.
        
        This should handle markdown code blocks and plain text extraction.
        Return None if no valid payload is found.
        """
        # Example: Look for ```myformat blocks or parse directly
        pass

    def load_payload(self, payload: str) -> Any:
        """Parse the extracted payload string into a Python object.
        
        This is where you use your format's parser (e.g., json.loads, yaml.safe_load).
        """
        pass

    def find_element(self, tree, key):
        """Find a direct child element/field with the given key in the parsed tree."""
        pass

    def get_text(self, element):
        """Extract text/primitive value from an element."""
        pass

    def has_nested(self, element):
        """Return True if the element has nested structure (not just a primitive value)."""
        pass

    def iter_direct_children(self, tree):
        """Iterate over direct children of the tree/element."""
        pass

    def get_name(self, element):
        """Get the name/tag/key of the element (format-specific)."""
        pass

    def find_all(self, tree, key):
        """Recursively find all elements with the given key in the tree."""
        pass

    def get_subtree_string(self, elem):
        """Convert an element back to its string representation in the original format."""
        pass

    def _describe_structure(self, model, indent=0):
        """Generate human-readable structure description for hints.
        
        Should return a list of strings describing the expected structure
        in your format's syntax.
        """
        pass
```

### Constructor Parameters

The `DocumentStructureValidator` constructor accepts these parameters:

- `model`: A Pydantic model class to validate against (optional)
- `model_name`: String name of a model to import (alternative to `model`)
- `schema`: Dict schema to create a dynamic model (alternative to `model`)
- `strict`: Boolean for strict vs permissive validation (default: True)
- `model_module`: Module to import models from when using `model_name` (default: "models")
- `generate_hints`: Whether to generate helpful hints in error messages (default: False)

### Example Usage

```python
# Using with a Pydantic model
from pydantic import BaseModel

class Person(BaseModel):
    name: str
    age: int

validator = JSONStructureValidator(model=Person, strict=False, generate_hints=True)

# Using with model name (will import from models.Person)
validator = JSONStructureValidator(model_name="Person", model_module="myapp.models")

# Using with dynamic schema
schema = {"name": (str, ...), "age": (int, ...)}
validator = JSONStructureValidator(schema=schema)
```

### Configuration in config.yaml

```yaml
validation:
  enabled: true
  validators:
    - type: "json_structure"
      model_name: "Person"
      model_module: "models"
      strict: false
      generate_hints: true
```

### Advanced Features

#### JSON Schema Generation

The validation module includes utilities for generating JSON schemas from Pydantic models, with optional token optimization:

```python
from lamia.validation.validators.file_validators.file_structure.schema_utils import (
    get_json_schema, 
    get_formatted_json_schema_human_readable
)

# Get compact JSON schema
schema = get_json_schema(model, optimize_for_tokens=True)

# Get human-readable formatted schema  
readable_schema = get_formatted_json_schema_human_readable(model)
```

#### Type Matching and Conversion

The `TypeMatcher` utility handles automatic type conversion and validation:

- Converts strings to appropriate types (int, float, bool, etc.)
- Handles optional types (Union[T, None])
- Tracks information loss during conversions
- Supports strict vs permissive type matching

#### Error Handling

The validation framework provides specialized exception types:

- `BaseValidationError`: Base exception with hint support
- `TextAroundPayloadError`: When extra text surrounds valid content
- `InvalidPayloadError`: When no valid payload is found

These exceptions automatically generate helpful hints for the LLM to improve its responses.

---

## Validation Results

All validators return a `ValidationResult` object with these fields:

- `is_valid`: Boolean indicating if validation passed
- `error_message`: Error description if validation failed
- `hint`: Helpful hint for fixing the response
- `raw_text`: Original input text
- `validated_text`: Extracted/cleaned valid content
- `result_type`: Parsed and validated object (e.g., Pydantic model instance)
- `info_loss`: Dictionary describing any information lost during type conversion