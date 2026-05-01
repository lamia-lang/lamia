# LSG-2: .lm File Style Guide

This guide defines conventions for writing `.lm` (Lamia script) files.
`.lm` files are the orchestration layer -- they combine Python code
with Lamia syntax to wire prompts, files, web actions, and validation
into workflows.

## Core principle

`.lm` files are **Python + Lamia**. Follow PEP 8 for the Python parts.
but keep usage of Python code to a minimum only when Lamia syntax is not sufficient for the task.

## Indentation and formatting

Use 4 spaces for indentation (PEP 8). Never tabs.

```python
def analyze_code(language="python"):
    """
    Review the code in {@source.py} for bugs and style issues.
    Focus on {language}-specific patterns.
    """

for ticker in ["AAPL", "NVDA", "GOOG"]:
    data = get_stock(ticker=ticker) -> JSON[StockQuote]
    print(f"{ticker}: {data.price}")
```

## Return types

Always declare return types when you need validated output.
Lamia supports: `JSON`, `HTML`, `YAML`, `XML`, `CSV`, `Markdown`, `TEXT`.

### Format validation (type only)

```python
def load_config() -> JSON:
    "./config.json"

def generate_page() -> HTML[LandingPage]:
    "Create a login form"
```

### Strict vs permissive

Skip permissive Boolean flag and use HTML[Model] instead.   

```python
-> HTML[Model]         # permissive (default) - filler content arround the content you want to extract is allowed and model matched rules are relaxed a bit. Check Lamia documentation for more details.
-> HTML[Model, True]   # strict - response must be pure HTML, etc. and no drifts are allowed in the document conten
-> HTML[Model, False]  # Use HTML[Model] instead of this 
```

Use cases:
- Use strict mode for content generation (you control the output).
- Use permissive mode for parsing external content (HTML pages, API responses).

### Don't embed format instructions

Never put output schema in comments, docstrings, or prompt text:

```python
# Bad -- the schema belongs in a Pydantic model
def analyze():
    """
    Analyze the data.
    Output JSON:
    {"score": 0, "summary": "..."}
    """

# Good -- Pydantic model + return type
class Analysis(BaseModel):
    score: int
    summary: str

def analyze() -> JSON[Analysis]:
    "Analyze the data"
```

## Calling .hu functions

`.hu` functions are called like regular Python functions.
All arguments must be keyword arguments.

```python
# Good
result = summarize(aspect="key findings", max_words=200) -> HTML

# Bad -- positional arguments
result = summarize("key findings", 200) -> HTML
```

### Return type on the call site

The `-> Type` on `.hu` calls is where you specify what format
you expect back. The `.hu` file itself stays format-agnostic:

```python
# Same .hu prompt, different output formats
html_result = summarize(topic="AI") -> HTML
json_result = summarize(topic="AI") -> JSON[Summary]
text_result = summarize(topic="AI") -> TEXT
```

## Simplified syntax

For one-off commands that don't need a function name, use the
simplified arrow syntax:

```python
data = "./users.json" -> JSON:
page = "Create a login form" -> HTML:
```

## File operations

### Reading Files

Read files with Lamia syntax. Avoid using Python code to read files. Validation will be done automatically if needed.

```python
def read_data():
    "./data/input.txt"

def load_settings() -> JSON:
    "../config/settings.json"

content = read_data() -> TEXT # We can select the return type during the runtime.
settings = load_settings() # load_settings will always return a JSON object.
```

### Writing Files

Write files with Lamia syntax. Avoid using Python code to write files. Validation will be done automatically if needed.

Assign to a variable when you need the result. Use `-> File(...)`
when you want to write directly to disk: do 

```python
"Create a landing page" -> File(HTML, "index.html"):
"Generate test data" -> File(CSV, "fixtures.csv"):
```

If the result is needed in memory and written to a file, use a single operation:

```python
im_memory = "Generate test data" -> File(CSV, "fixtures.csv"):
```

# File context

Instead of using many paths to a directory in your code, use `with files("~/Documents/")` to scope file search directories and to avoid writing many paths to a directory in your code:

```python
with files("~/Documents/"):
    def answer_question(question: str):
        """
        Answer: {question}
        Use information from {@resume.pdf} and {@cover_letter.txt}
        """
```

## Variable naming

Follow PEP 8:

```python
# Good
review_result = review_code(language="python") -> JSON[Review]
stock_data = get_stock(ticker="AAPL") -> CSV[StockQuote]

# Bad
ReviewResult = review_code(language="python") -> JSON[Review]
x = get_stock(ticker="AAPL") -> CSV[StockQuote]
```

Pydantic models use `PascalCase` (standard Python class naming):

```python
class StockQuote(BaseModel):
    ticker: str
    price: float
    volume: int
```

## Model selection

Use a singular parameter for `models` when a function needs a specific LLM:

```python
def analyze(models="openai:gpt-4"):
    "Analyze the data"
```

Use an array of models for `models` when providing fallback models:

```python
def with_fallback(models=["openai:gpt-4", "anthropic:sonnet-4"]):
    "<some complicated task>"
```

## Imports

Imports are not needed in `.lm` files. All Lamia types and interfaces are available without any import statements. But if you mix it with Python code, you will import Python dependencies as usual.

Avoid import pydantic models as well.