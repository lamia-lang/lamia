# Validation Module

This module provides a flexible framework for validating LLM responses in Lamia. Validators can be combined, customized to ensure your outputs meet quality and format requirements.

---

## Method Contracts and Return Values

### BaseValidator Abstract Methods

When implementing custom validators, you must follow these strict contracts:

#### `name` property
- **Returns**: `str` - A unique name for the validator
- **When**: Always called during validator registration
- **Contract**: Must return a string that doesn't conflict with built-in validators

#### `initial_hint` property  
- **Returns**: `str` - A hint for the LLM prompt
- **When**: Called before sending requests to the LLM
- **Contract**: Must return a descriptive string to guide LLM behavior

#### `validate()` method (Simple validators)
- **Parameters**: `response: str, **kwargs`
- **Returns**: `ValidationResult` - Always returns a ValidationResult object
- **When**: Called for each validation check
- **Contract**: Must return `ValidationResult(is_valid=True/False, ...)` - never None

#### `validate_strict()` / `validate_permissive()` methods (Context-aware validators)
- **Parameters**: `response: str, **kwargs`
- **Returns**: `ValidationResult` - Always returns a ValidationResult object  
- **When**: Called based on the `strict` flag
- **Contract**: Must return `ValidationResult(is_valid=True/False, ...)` - never None
- **Important**: If implementing these, do NOT implement `validate()` as well

### DocumentStructureValidator Abstract Methods

For file structure validators, these methods have specific contracts:

#### `extract_payload(response: str) -> str | None`
- **Returns**: 
  - `str` - The extracted payload when valid content is found
  - `None` - When no valid payload is found in the response
- **When**: Called during parsing to extract valid content from LLM response
- **Contract**: 
  - Must return `None` if no valid payload can be extracted
  - Must return the clean payload string if extraction succeeds
  - Should handle both markdown code blocks and plain text

#### `load_payload(payload: str) -> Any`
- **Returns**: `Any` - Parsed Python object from the payload
- **When**: Called after successful payload extraction
- **Contract**: 
  - Must parse the payload string into appropriate Python objects
  - Should raise exceptions for invalid payloads (caught by framework)
  - Never called with None payload

#### `find_element(tree, key) -> Any | None`
- **Returns**: 
  - The found element if key exists
  - `None` if key not found
- **When**: Called during structure validation
- **Contract**: Must handle the parsed tree structure for your format

#### `get_text(element) -> Any`
- **Returns**: The primitive value or text content of the element
- **When**: Called to extract values from parsed elements
- **Contract**: Must return the actual value (str, int, float, bool, etc.)

#### `has_nested(element) -> bool`
- **Returns**: `bool` - True if element has nested structure
- **When**: Called to determine if recursive validation is needed
- **Contract**: Must accurately detect nested vs primitive elements

#### `iter_direct_children(tree) -> Iterator`
- **Returns**: Iterator yielding direct child elements
- **When**: Called during recursive structure traversal
- **Contract**: Must yield only direct children, not all descendants

#### `get_name(element) -> str | None`
- **Returns**: The name/tag/key of the element
- **When**: Called to identify elements during validation
- **Contract**: Format-specific implementation

#### `find_all(tree, key) -> List`
- **Returns**: List of all elements matching the key
- **When**: Called for recursive searches
- **Contract**: Must find all occurrences, not just first match

#### `get_subtree_string(elem) -> str`
- **Returns**: String representation of the element in original format
- **When**: Called for error reporting and debugging
- **Contract**: Must produce valid format-specific string

#### `_describe_structure(model, indent=0) -> List[str]`
- **Returns**: List of strings describing expected structure
- **When**: Called to generate helpful hints for users
- **Contract**: Must return format-specific structure description

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

These validators not only check if the response is valid in the given format, but also validate that it matches a specific Pydantic model structure, concurrently they create an result object according to the provided pydantic schema, just like ObjectValidator (see below). When the type
can be fetched these vlaidators will fetch it from the file so that you can use teh data in a structured form

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
- **AtomicTypeValidator**: Ensures output is a valid atomic type (integer, float, bool, or string)

---

## Model Types and Order Enforcement in File Structure Validators

File structure validators (such as CSVStructureValidator, JSONStructureValidator, etc.) use the provided model to validate the structure and types of the file. The type of model you provide can also control whether the order of fields is enforced:

- **dict or Pydantic BaseModel**: Order of fields/columns does NOT matter. The validator will check that all required fields are present (and, in strict mode, that there are no extra fields), but the order in the file can be different from the order in the model.
- **OrderedDict**: Order of fields/columns IS enforced. The validator will require that the file's fields/columns appear in exactly the same order as in the OrderedDict model. This is especially useful for formats like CSV, where downstream workflows may depend on column order.

**Example:**

```python
# Order does not matter
class MyModel(BaseModel):
    myint: int
    mystr: str

# Order matters (col1 must come before col2)
ordered_model = OrderedDict([
    ("col1", int),
    ("col2", str),
])

# Nested tyoe enforced
class MyComplexModel(BaseModel):
    # the order is irrelevant for these 4 fields. but the myModel1 will be read with the values that appears the first in the file
    myint: int
    myModel1: MyModel
    mystr: str
    myModel2: MyModel
    # but the col1 must always come with col2
    OrderedDict([
        ("col1", int),
        ("col2", str),
    ])
```

This approach is extensible: you can use other mapping types or wrappers in the future to control more nuanced validation logic (such as enforcing order for only some fields).

**Note:** For most file formats (JSON, YAML, XML, HTML, Markdown), order is not semantically important for flat models, so order is only enforced if you explicitly use an OrderedDict model.

---

## Ways of using validators

1. From Python code: Lamia(..., validators=[...])
2. By defining in config.yaml to use from the command line

### Configuration Examples

**YAML Configuration:**
```yaml
validation:
  enabled: true
  validators:
    - type: "html"
      strict: true
    - type: "json"
      strict: false
    - type: "regex"
      pattern: "^\\d{4}-\\d{2}-\\d{2}$"
      strict: true
    - type: "length"
      max_length: 1000
```

**Python Code:**
```python
lamia = Lamia(
    ...,
    validators=[
        {"type": "html"},
        {"type": "json", "strict": False},
        {"type": "regex", "pattern": r"^\\d{4}-\\d{2}-\\d{2}$", "strict": True}
    ]
)
```

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

## Strict and Forgiving Validation

Each validator supports a `strict` flag (set in config or code). If omitted, strict mode is used by default.
- `strict: true` (default): Only accepts pure, valid output (e.g., only the HTML, JSON, or pattern match, with no extra text).
- `strict: false`: Accepts output that contains a valid block (e.g., a valid HTML or JSON block within a longer response).

---

## Built-in Validator Details

### Atomic Type Validator

The `atomic_type` validator allows you to validate that the LLM output is a valid integer, float, boolean, or string. This is useful for enforcing that the response is a single value of a specific type.

#### Usage from config.yaml

```yaml
validators:
  - type: "atomic_type"
    atomic_type: "integer"  # or "float", "bool", "string"
    strict: true  # Optional, default is true
```

#### Usage from Python code

```python
from lamia.validation.validators import AtomicTypeValidator

lamia = Lamia(
    ...,
    validators=[AtomicTypeValidator(atomic_type="integer")]
)
```

#### How it works
- In strict mode, the response must be exactly the specified type (e.g., only an integer, with no extra text).
- In forgiving mode (`strict: false`), the response is valid if it contains exactly one value of the specified type.
- If there are multiple values of the type in the response, validation fails.

#### Examples

**Valid integer:**
```
42
```

**Valid float:**
```
3.1415
```

**Valid boolean:**
```
true
```

**Valid string:**
```
hello world
```

**Invalid (multiple values):**
```
42 and 43
```

### HTML Structure Validator

The `html_structure` validator allows you to validate the structure of HTML output using a Pydantic model. This is useful for ensuring that generated HTML matches a specific tag and nesting structure.

#### Usage from config.yaml

Define your Pydantic models in a `models/` folder (or any importable module):

```python
# models/html_structure.py
from pydantic import BaseModel

class Body(BaseModel):
    h1: str

class HtmlStructure(BaseModel):
    title: str
    body: Body
```

Reference the top-level model in your config using the short class name (imported from `models`):

```yaml
validators:
  - type: "html_structure"
    model: HtmlStructure  # Will be imported from the models folder
```

You can also use a full dotted path to a model in any package:

```yaml
validators:
  - type: "html_structure"
    model: myapp.models.html_structure.HtmlStructure
```

#### Usage from Python code

You can pass any model class from your Python path when constructing Lamia:

```python
from myapp.models.html_structure import HtmlStructure
from lamia.validation.validators import HTMLStructureValidator

lamia = Lamia(
    ...,
    validators=[HTMLStructureValidator(model=HtmlStructure)]
)
```

#### How it works
- The validator parses the HTML, maps tags to model fields (recursively), and validates the result using Pydantic.
- If you specify a string for `model`, it will be dynamically imported from the `models` module (by default), or from a full dotted path if provided.
- You can also provide a schema dict for quick prototyping.

#### Example
Given this HTML:
```html
<html><head><title>My Title</title></head><body><h1>Header</h1></body></html>
```
And the model above, validation will pass if the structure matches.

---

## Creating Custom Validators

You can create custom validators as either classes (subclassing `BaseValidator`) or as standalone functions.

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

**Important:**
- Do **not** implement both `validate()` and `validate_strict`/`validate_permissive` in the same class.
- If you implement only `validate()`, your validator is non-context-aware.
- If you implement both `validate_strict()` and `validate_permissive()`, your validator is context-aware.

## Implementing File Validators

Generally, file validators need to support both strict or permissive modes. You can create a
new file validator for not yet supported file type by extending `DocumentStructureValidator`.

In this case you don't need to write validate_strict and validate_strict() and validate_permissive() or validate() functions and inplemement the validator from zero

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

### Advanced Features

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

## Runtime Contract Checking

Lamia includes a comprehensive runtime contract checker that validates custom validator implementations against the documented contracts. This helps catch implementation errors that Python's type system might miss.

### Automatic Contract Checking

When you load custom validators through the ValidatorRegistry (via config.yaml or programmatically), the contract checker automatically runs to verify:

- Property return types (`name`, `initial_hint`)
- Validation method return types (`ValidationResult` objects)
- `extract_payload` returns `str` or `None` as documented
- All required abstract methods are implemented
- Method signatures match the expected contracts

### Configuration

Contract checking is enabled by default but can be configured:

```yaml
validation:
  enabled: true
  enable_contract_checking: true  # Enable/disable contract checking
  strict_contract_checking: false  # If true, reject validators that fail contract checks
  validators:
    - type: "custom_file"
      path: "my_validator.py"
```

### Manual Contract Checking

You can also run contract checks manually in your code:

```python
from lamia.validation.contract_checker import check_validator_contracts

# Check a validator class
passed, violations = await check_validator_contracts(MyCustomValidator)

if not passed:
    for violation in violations:
        print(f"Contract violation in {violation.method_name}:")
        print(f"  Expected: {violation.expected}")
        print(f"  Got: {violation.actual}")
        print(f"  Error: {violation.error_message}")
```

### What Gets Checked

#### BaseValidator Contracts
- `name` property returns non-empty string
- `initial_hint` property returns string
- `validate()` method returns `ValidationResult` object
- `validate_strict()` and `validate_permissive()` return `ValidationResult` objects

#### DocumentStructureValidator Contracts
- `extract_payload(response: str)` returns `str` or `None`
- All required abstract methods are implemented and callable
- Methods handle edge cases appropriately



### Benefits

Contract checking helps you:
- **Catch bugs early**: Find implementation errors before runtime
- **Ensure reliability**: Verify validators follow expected patterns
- **Improve debugging**: Get detailed error messages about what's wrong
- **Maintain consistency**: Ensure all custom validators work the same way

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