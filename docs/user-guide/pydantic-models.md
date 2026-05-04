# Pydantic Models Guide

This guide covers how to define Pydantic models that work well with Lamia's structured output validation. Good model definitions lead to better LLM output — the `description` fields, type constraints, and field names all become part of the schema that guides the model's response.

## Basic model definition

Every field should have a `description` that tells the LLM what to put there:

```python
from pydantic import BaseModel, Field


class UserSummary(BaseModel):
    name: str = Field(description="User full name")
    role: Role = Field(description="Current role or job title")
    risk_level: int = Field(description="Risk level from 0 to 100")
```

Without descriptions, the LLM only sees field names and types. With descriptions, it knows exactly what you expect. This is the single most impactful thing you can do for output quality.

## Field constraints

Lamia enforces Pydantic field type and other constraints at validation time. When the LLM returns data that violates a constraint, Lamia rejects the response and retries with a feedback message explaining what went wrong.

### String constraints

```python
class Product(BaseModel):
    sku: str = Field(description="Product SKU code", min_length=3, max_length=20)
    name: str = Field(description="Product display name", min_length=1)
    category: str = Field(description="Product category", pattern=r"^(electronics|clothing|food|other)$")
```

Supported string constraints:

| Constraint | Example | What it does |
|------------|---------|--------------|
| `min_length` | `Field(min_length=3)` | Rejects strings shorter than 3 characters |
| `max_length` | `Field(max_length=100)` | Rejects strings longer than 100 characters |
| `pattern` | `Field(pattern=r"^[A-Z]{3}")` | Rejects strings that don't match the regex |

You can also use `constr` for the same effect:

```python
class Product(BaseModel):
    sku: constr(min_length=18, max_length=20)
```

Multiple constraints can be combined on a single field:

```python
class Config(BaseModel):
    code: str = Field(min_length=3, pattern=r"^abc")
```

### Numeric constraints

```python
class Metrics(BaseModel):
    score: float = Field(description="Score from 0.0 to 1.0", ge=0.0, le=1.0)
    count: int = Field(description="Number of items, must be positive", gt=0)
    percentage: float = Field(description="Percentage value", ge=0, le=100)
```

Supported numeric constraints:

| Constraint | Example | What it does |
|------------|---------|--------------|
| `gt` | `Field(gt=0)` | Greater than |
| `ge` | `Field(ge=0)` | Greater than or equal |
| `lt` | `Field(lt=100)` | Less than |
| `le` | `Field(le=100)` | Less than or equal |
| `multiple_of` | `Field(multiple_of=5)` | Must be a multiple of the value |

### Optional fields

Use `Optional` for fields that may not always be present:

```python
class Contact(BaseModel):
    name: str = Field(description="Full name")
    email: str = Field(description="Email address")
    phone: Optional[str] = Field(default=None, description="Phone number if available")
```

### Enum fields

Use Python enums to restrict values to a fixed set:

```python

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Ticket(BaseModel):
    title: str = Field(description="Issue title")
    priority: Priority = Field(description="Issue priority level")
    assignee: str = Field(description="Person assigned to the issue")
```

Lamia validates the enum value and provides clear error messages if the LLM returns an invalid option.

## Nested models

Models can reference other models for complex structures:

```python
from typing import List
from pydantic import BaseModel, Field


class Address(BaseModel):
    street: str = Field(description="Street address")
    city: str = Field(description="City name")
    country: str = Field(description="Country code, e.g. US, DE, JP")


class Employee(BaseModel):
    name: str = Field(description="Full name")
    title: str = Field(description="Job title")
    address: Address = Field(description="Home address")


class Department(BaseModel):
    name: str = Field(description="Department name")
    head: Employee = Field(description="Department head")
    members: List[Employee] = Field(description="All department members")
```

## Lists and dictionaries

```python

class AnalysisResult(BaseModel):
    keywords: List[str] = Field(
        description="Top 5 keywords from the text",
        min_length=1,
        max_length=5,
    )
    scores: Dict[str, float] = Field(description="Category scores, e.g. {'relevance': 0.9}")
    related_topics: List[str] = Field(description="Related topic names", max_length=10)
```

You can constrain collection sizes (number of elements) with Pydantic field constraints:

| Constraint | Applies to | Example | What it does |
|------------|------------|---------|--------------|
| `min_length` | `List`, `Dict`, `str` | `Field(min_length=2)` | Requires at least 2 items (or chars for strings) |
| `max_length` | `List`, `Dict`, `str` | `Field(max_length=10)` | Allows at most 10 items (or chars for strings) |

For lists of nested objects, constraints still apply to list size:

```python
class Finding(BaseModel):
    severity: str = Field(description="Severity level")
    message: str = Field(description="Issue details")


class ReviewOutput(BaseModel):
    findings: List[Finding] = Field(
        description="Detected issues",
        min_length=1,
        max_length=20,
    )
```

For dictionaries, constraints control the number of keys:

```python
class MetricsByCategory(BaseModel):
    scores: Dict[str, float] = Field(
        description="Category scores where key is category name",
        min_length=1,
        max_length=12,
    )
```

## File type examples with Pydantic models

Lamia supports structure validation for `JSON`, `YAML`, `XML`, `HTML`, `Markdown`, and `CSV` with the same Pydantic model concepts.

### JSON

Use direct field mapping, and `alias` when JSON keys differ from Python field names:

```python
class UserSummary(BaseModel):
    user_name: str = Field(alias="userName", description="Display name")
    is_active: bool = Field(description="Whether the account is active")
```

### YAML

Use selectors when YAML keys are deeply nested:

```python
class ServiceConfig(BaseModel):
    host: str = Field(
        description="Database host",
        json_schema_extra={"selector": "$.database.host"},
    )
    port: int = Field(
        description="Database port",
        json_schema_extra={"selector": "$.database.port"},
        ge=1,
        le=65535,
    )
```

### XML

Use XPath selectors, including attribute extraction:

```python
class BookMeta(BaseModel):
    title: str = Field(
        description="Book title",
        json_schema_extra={"selector": "//book/title"},
    )
    author_name: str = Field(
        description="Author name from XML attribute",
        json_schema_extra={"selector": "//book/author/@name"},
    )
```

### HTML

HTML models support CSS and XPath selectors, including tag names, attributes, and fallback selector chains:

```python
class ProductPage(BaseModel):
    title: str = Field(
        description="Main page heading",
        json_schema_extra={"selectors": [
            "h1[itemprop='name']",
            "meta[property='og:title']",
            "//h1[contains(@class, 'product-title')]",
        ]},
    )
    price_text: str = Field(
        description="Price label as shown on page",
        json_schema_extra={"selectors": [
            "[data-testid='price']",
            "span[itemprop='price']",
            "//span[@class='price']",
        ]},
    )
    description: str = Field(
        description="Product description block",
        json_schema_extra={"selector": "div[data-section='description'] p"},
    )
```

Common HTML selector patterns:
- Tag by name: `h1`, `article`, `table`
- Tag + attribute: `meta[property='og:title']`, `a[rel='next']`
- Data attributes: `[data-testid='price']`
- XPath by attribute: `//div[@id='main']`, `//a[@href='/checkout']`

### Markdown

Use selectors for document elements like headings and code blocks:

```python
class ArticleSummary(BaseModel):
    title: str = Field(description="Main heading", json_schema_extra={"selector": "h1"})
    intro: str = Field(description="First paragraph", json_schema_extra={"selector": "p[0]"})
    snippet: str = Field(description="First code block", json_schema_extra={"selector": "code[0]"})
```

For a deeper selector reference (fallback chains, AI-assisted selectors, best practices), see the [Selector Usage Guide](../validation/selector-usage-guide.md).

## Tips for better output

1. **Be specific in descriptions.** Instead of `"price"`, write `"Open price from the Quote Summary section"`. The more specific, the more accurate the extraction.

2. **Use the right types.** If a value is always numeric, use `int` or `float`, not `str`. Lamia validates types and the LLM gets schema hints showing the expected type.

3. **Use `str` for formatted numbers.** Bid/ask prices like `"185.50 x 200"` contain non-numeric characters — model them as `str`, not `float`.

4. **Add constraints where they matter.** `Field(ge=0, le=1)` for confidence scores catches hallucinated values like `999.0`.

5. **Keep models flat when possible.** Deep nesting makes it harder for the LLM to produce valid output. Flatten when the structure allows it.

6. **Use enums for known categories.** If a field has a fixed set of valid values, use an `Enum` instead of `str` — it gives the LLM the exact options and Lamia validates the choice.