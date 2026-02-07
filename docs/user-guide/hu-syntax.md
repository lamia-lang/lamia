# .hu File Syntax

Lamia `.hu` files use a hybrid Python syntax that lets you write LLM commands, file operations, and web actions as regular function definitions. Run them with:

```bash
lamia your_script.hu
```

## Command Types

Lamia detects the command type automatically based on the string content:

```python
# LLM command — plain text goes to the AI
def generate_story():
    "Write a short story about a robot discovering emotions"

# File read — paths are read from disk
def read_config() -> JSON:
    "./config.json"

# Web request — URLs trigger HTTP requests
def fetch_data() -> JSON:
    "https://api.example.com/data"
```

## Return Types

Specify return types for automatic validation:

```python
def get_data() -> JSON:
    "./users.json"            # Must be valid JSON

def generate_page() -> HTML:
    "Create a login form"     # Must be valid HTML

def plain_text():
    "Write a summary"         # No validation, returns text
```

Available types: `HTML`, `JSON`, `YAML`, `XML`, `Markdown`, `CSV`, `TEXT`

## File Operations

### Reading Files

Use relative or absolute paths:

```python
def read_data():
    "./data/input.txt"

def load_settings() -> JSON:
    "../config/settings.json"

def read_logs():
    "/var/log/application.log"
```

Or the `file` action API:

```python
content = file.read("/path/to/file.txt")
content = file.read("data.csv", encoding="latin-1")
```

### Writing to Files

Use `-> File(...)` to generate content and save it:

```python
# With type validation
def generate_page() -> File(HTML, "output.html"):
    "Generate an HTML page about cats"

# Without type validation
def generate_text() -> File("output.txt"):
    "Generate some text"

# Append instead of overwrite
def add_rows() -> File(CSV, "data.csv", append=True):
    "Generate additional CSV rows"

# Custom encoding
def generate_latin() -> File("output.txt", encoding="latin-1"):
    "Generate text with special characters"
```

Expression-level file writes (no function wrapper needed):

```python
"Generate HTML about cats" -> File(HTML, "output.html")

web.get_text(".content") -> File(HTML, "scraped.html")
```

Or the `file` action API:

```python
file.write("/path/to/file.txt", "Hello, World!")
file.append("/var/log/app.log", "New log entry\n")
```

| Syntax | Description |
|--------|-------------|
| `-> File("path")` | Write untyped content |
| `-> File(Type, "path")` | Write with type validation |
| `-> File(Type, "path", append=True)` | Append instead of overwrite |
| `-> File("path", encoding="...")` | Custom encoding |
| `-> File(Type[Model], "path")` | Parametric type validation |

## File Context (`with files()`)

Reference local files in LLM prompts using `{@filename}` syntax:

```python
with files("~/Documents/"):
    def answer_question(question: str, models="openai:gpt-4"):
        """
        Answer: {question}
        
        Use information from {@resume.pdf} and {@cover_letter.txt}
        """
```

Files are resolved using smart search (exact match, content grep, fuzzy matching). PDF and DOCX are automatically extracted to text.

```python
{@resume.pdf}                     # Search indexed directories
{@/Users/me/Documents/resume.pdf} # Absolute path
{@resum.pdf}                      # Fuzzy match → resume.pdf
{@config}                         # Finds config.yaml, config.json, etc.
```

Multiple directories and nested contexts:

```python
with files("~/Documents/", "~/projects/"):
    with session("job_application"):
        def fill_form(models="openai:gpt-4"):
            "Fill the form using {@resume.pdf}"
```

For full details see the [File Context Reference](files-context.md).

## Session Management

Use `with session()` for multi-step workflows that persist across runs:

```python
def login_to_site():
    with session("login"):
        web.navigate("https://example.com/login")
        web.type_text("#username", "your_username")
        web.type_text("#password", "your_password")
        web.click("#login-button")
    
    # Always runs — session block is skipped if already completed
    web.navigate("https://example.com/dashboard")
```

**First run**: executes the block, saves session on success.
**Subsequent runs**: detects valid session, skips the block.

Sessions are stored in `.lamia_sessions/`. Clear with `rm -rf .lamia_sessions/`.

## Web Actions

Use the `web` object for browser automation:

```python
web.navigate("https://example.com")
web.click("#login-button")
web.type_text("#username", "user@example.com")
text = web.get_text(".result")
web.wait_for(".loading", "hidden")
web.screenshot("page.png")
```

Scoped elements:

```python
modal = web.get_element("div.modal")
modal.click("button.close")

fields = web.get_elements("div.form-field")
for field in fields:
    label = field.get_text("label")
    field.type_text("input", "answer")
```

## Parameters and Models

### Parameter Substitution

```python
def generate_report(data: dict, style: str):
    "Create a {style} report based on: {data}"
```

### Model Selection

```python
def analyze(models="openai:gpt-4"):
    "Analyze the data"

def with_fallback(models=["openai:gpt-4", "anthropic:claude-3-haiku-20240307"]):
    "Generate a report with model fallback"
```

## Async and Parallel Execution

Functions become async automatically:

```python
import asyncio

async def main():
    results = await asyncio.gather(
        get_weather(),
        read_config(),
        fetch_webpage()
    )
```

## Complete Example

```python
from lamia.types import JSON, HTML

# Read data
def load_users() -> JSON:
    "./users.json"

# Generate content with AI
def create_report():
    '''
    Generate a user activity report including:
    - Engagement metrics
    - Most active features
    - Recommendations
    '''

# Write AI output to file
def generate_dashboard() -> File(HTML, "dashboard.html"):
    "Create an admin dashboard with user statistics"

# Full workflow
async def main():
    users = await load_users()
    report = await create_report()
    dashboard = await generate_dashboard()
```