# Validation

Lamia validates LLM responses automatically when you specify return types. Validators ensure outputs meet format and quality requirements before your code uses them.

## Built-in Validators

### File Format Validators

| Type | Description |
|------|-------------|
| `HTML` | Well-formed HTML |
| `JSON` | Valid JSON |
| `YAML` | Valid YAML |
| `XML` | Valid XML |
| `Markdown` | Valid Markdown |
| `CSV` | Valid CSV |

### Structure Validators

Validate file format AND match a Pydantic model schema:

```python
from pydantic import BaseModel

class UserProfile(BaseModel):
    name: str
    age: int
    email: str

# In .hu files — validates JSON structure matches the model
def get_user() -> JSON[UserProfile]:
    "Generate a user profile"

# From Python
result = lamia.run("Generate a user profile", JSON[UserProfile])
```

Available structure validators: `JSON[Model]`, `YAML[Model]`, `XML[Model]`, `HTML[Model]`, `Markdown[Model]`, `CSV[Model]`

### Other Validators

| Type | Description |
|------|-------------|
| `ObjectValidator` | Validates response matches a requested type |
| `RegexValidator` | Matches a regex pattern |
| `LengthValidator` | Checks response length bounds |
| `AtomicTypeValidator` | Validates atomic types (int, float, bool, string) |
| `FunctionalValidator` | Custom validation logic via a function |

## Configuration

### From config.yaml

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
    - type: "length"
      max_length: 1000
```

### From Python

```python
lamia = Lamia(
    ...,
    validators=[
        {"type": "html"},
        {"type": "json", "strict": False},
        {"type": "regex", "pattern": r"^\d{4}-\d{2}-\d{2}$"}
    ]
)
```

## Strict vs Permissive Mode

Each validator supports a `strict` flag (default: `true`):

- **`strict: true`**: Only accepts pure, valid output (no extra text around it)
- **`strict: false`**: Accepts output that contains a valid block within a longer response

```yaml
validators:
  - type: "json"
    strict: false  # Extracts JSON from within explanatory text
```

## Combining Validators

Validators are applied in sequence. The response must pass all of them:

```yaml
validation:
  enabled: true
  validators:
    - type: "html"
    - type: "length"
      max_length: 1000
```

## Ordered Fields (CSV, JSON, etc.)

For formats where field order matters, use `__ordered_fields__`:

```python
from collections import OrderedDict
from pydantic import BaseModel

class Report(BaseModel):
    title: str
    description: str
    # These fields must appear in this order in the output
    __ordered_fields__ = OrderedDict([
        ("col1", int),
        ("col2", str),
    ])
```

## Atomic Types

Validate that LLM output is a single value:

```yaml
validators:
  - type: "atomic_type"
    atomic_type: "integer"  # or "float", "bool", "string"
```

```python
from lamia.validation.validators import AtomicTypeValidator

lamia = Lamia(..., validators=[AtomicTypeValidator(atomic_type="integer")])
```

## HTML Structure Validation

Validate HTML matches a specific tag structure:

```python
class Body(BaseModel):
    h1: str

class HtmlStructure(BaseModel):
    title: str
    body: Body

# From config
# validators:
#   - type: "html_structure"
#     model: HtmlStructure

# From Python
from lamia.validation.validators import HTMLStructureValidator
lamia = Lamia(..., validators=[HTMLStructureValidator(model=HtmlStructure)])
```

## Validation Results

All validators return a `ValidationResult`:

| Field | Description |
|-------|-------------|
| `is_valid` | Whether validation passed |
| `error_message` | Error description if failed |
| `hint` | Suggestion for fixing the response |
| `validated_text` | Extracted/cleaned valid content |
| `result_type` | Parsed object (e.g., Pydantic model instance) |

## Contract Checking

Lamia automatically validates custom validator implementations at load time:

```yaml
validation:
  enable_contract_checking: true   # Default: true
  strict_contract_checking: false  # Reject validators that fail checks
```

## Selector Usage with Validators

For details on using selectors within file type validators, see the [Selector Usage Guide](../validation/selector-usage-guide.md).

## Creating Custom Validators

For implementing your own validators, see the [Validation Module Developer Guide](https://github.com/lamia-lang/lamia/blob/main/lamia/validation/README.md).