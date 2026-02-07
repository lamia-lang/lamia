# Hybrid Python Syntax

Lamia supports a hybrid Python syntax that allows you to write LLM commands, file operations, and web requests directly as function definitions with automatic type validation.

## Basic Syntax

Define functions with string commands that get automatically executed:

```python
def generate_story():
    "Write a short story about a robot discovering emotions"

def read_config() -> JSON:
    "./config.json"

def fetch_webpage() -> HTML:
    "https://example.com"
```

## Command Types

Lamia automatically detects the command type based on the string content:

### LLM Commands
Any text that doesn't look like a file path or URL gets sent to the LLM:

```python
def write_email():
    "Write a professional email about the quarterly report"

def generate_code():
    "Create a Python function that calculates fibonacci numbers"
```

### File Operations

#### Reading Files

Use relative paths (starting with `./` or `../`) or absolute paths to read files:

```python
# Relative paths
def read_data():
    "./data/input.txt"

def load_settings() -> JSON:
    "../config/settings.json"

# Absolute paths  
def read_logs():
    "/var/log/application.log"

def load_database() -> JSON:
    "C:\\Users\\Data\\database.json"
```

You can also use the `file` action API for programmatic file reads:

```python
content = file.read("/path/to/file.txt")
content = file.read("config.json", encoding="latin-1")
```

#### Writing to Files

Use the `-> File(...)` return type syntax to generate content and write it to a file:

```python
# Write with type validation — content must be valid HTML
def generate_page() -> File(HTML, "output.html"):
    "Generate an HTML page about cats"

# Write without type validation — content saved as plain text
def generate_text() -> File("output.txt"):
    "Generate some text about neural networks"

# Async file write
async def generate_async() -> File(HTML, "output.html"):
    "Generate HTML content asynchronously"
```

The function executes the command, validates the result against the type (if provided), writes it to the file, and returns the result.

**Appending** instead of overwriting:

```python
def add_rows() -> File(CSV, "data.csv", append=True):
    "Generate additional CSV rows for the dataset"
```

**Custom encoding:**

```python
def generate_latin() -> File("output.txt", encoding="latin-1"):
    "Generate text with special characters"
```

**Expression-level file write** (without wrapping in a function):

```python
# LLM prompt to file
"Generate HTML about cats" -> File(HTML, "output.html")

# Web scraping to file
web.get_text(".content") -> File(HTML, "scraped.html")
```

**Web function with file output:**

```python
def scrape_to_file() -> File(HTML, "scraped.html"):
    return web.get_text(".content")
```

You can also use the `file` action API for programmatic writes:

```python
file.write("/path/to/file.txt", "Hello, World!")
file.write("output.json", json.dumps(data))
file.append("/var/log/app.log", "New log entry\n")
```

#### File Write Syntax Reference

| Syntax | Description |
|--------|-------------|
| `-> File("path")` | Write untyped content to file |
| `-> File(Type, "path")` | Write type-validated content to file |
| `-> File(Type, "path", append=True)` | Append instead of overwrite |
| `-> File("path", encoding="latin-1")` | Write with custom encoding |
| `-> File(Type[Model], "path")` | Write with parametric type validation |

### Web Requests
URLs automatically trigger web requests:

```python
def get_weather() -> JSON:
    "https://api.weather.com/current"

def scrape_news() -> HTML:
    "https://news.example.com"
```

## Return Types

Specify return types for automatic validation and parsing:

```python
from lamia.types import HTML, JSON

def get_user_data() -> JSON:
    "./users.json"

def generate_webpage() -> HTML:
    "Create a landing page with a contact form"

def write_summary():
    "Write a summary of the quarterly results"  # Returns plain text
```

## Multiline Commands

Use triple quotes for complex, multiline prompts:

```python
def create_documentation():
    '''
    Create comprehensive documentation for a REST API that includes:
    - Authentication methods
    - All available endpoints
    - Request/response examples
    - Error handling
    '''

def generate_complex_html() -> HTML:
    """
    Generate a responsive HTML page with:
    - Navigation header
    - Hero section with call-to-action
    - Features grid (3 columns)
    - Contact form
    - Footer with social links
    """
```

## Parameter Substitution

Functions can accept parameters and reference them in command strings using `{parameter_name}` syntax:

```python
from pydantic import BaseModel

class WeatherModel(BaseModel):
    city: str
    temperature: float
    conditions: str

def generate_report(weather_data: WeatherModel, location: str):
    "Generate a weather report for {location} using current conditions: {weather_data}"

def create_summary(data: dict, title: str, style: str):
    "Create a {style} summary titled '{title}' based on this data: {data}"

# Usage
weather = WeatherModel(city="NYC", temperature=22.5, conditions="sunny")
report = await generate_report(weather, "New York City")
```

## Model Selection

Functions can specify which AI model to use via the `models` parameter. You can specify a single model or a list of models for fallback:

```python
def analyze_with_gpt(models="openai:gpt-4"):
    "Analyze the user interface and suggest improvements"

def analyze_with_claude(models="anthropic:claude-3-opus-20240229"):
    "Write a technical analysis of the market trends"

def analyze_with_fallback(models=["openai:gpt-4", "anthropic:claude-3-haiku-20240307"]):
    "Generate a comprehensive report with model fallback"

# Usage - the models parameter automatically gets passed to lamia.run()
result = await analyze_with_gpt()  # Uses OpenAI GPT-4
analysis = await analyze_with_claude()  # Uses Claude Opus  
report = await analyze_with_fallback()  # Tries GPT-4, falls back to Claude Haiku
```

**Note**: The `models` parameter only applies to LLM commands. For web navigation and file operations, the models parameter is ignored since these don't involve language model processing.

Parameters are automatically serialized:
- **Pydantic models**: Serialized to JSON using `model_dump_json()`
- **Simple types** (str, int, float): Converted to string representation
- **Complex objects**: Converted to JSON if possible

## Smart Type Resolution

For parametric return types like `HTML[WeatherModel]`, Lamia returns a `LamiaResult` with both text and structured data. Smart resolution automatically extracts the right value based on context:

```python
def get_weather() -> HTML[WeatherModel]:
    "https://api.weather.com/current"  # Returns both HTML text and WeatherModel data

def save_weather_html():
    "./weather.html"  # File operation

async def main():
    result = await get_weather()  # LamiaResult object
    
    # Smart resolution: gets structured data (WeatherModel)
    weather_data: WeatherModel = result
    
    # Smart resolution: gets raw HTML text for file operations
    with open("weather.html", "w") as f:
        f.write(result)  # Uses result_text
    
    # Pass structured data to other functions
    report = await generate_report(weather_data, "NYC")
```

**Resolution rules:**
- **Typed assignments/parameters**: Extract `result_type` (structured data)
- **File operations/string context**: Extract `result_text` (raw text)
- **Simple return types** (HTML, JSON): No smart resolution needed

## Function Execution

Functions become async automatically and can be called normally:

```python
# Define functions
from lamia.types import HTML

class WeatherModel(BaseModel):
    city: str
    temperature: float

def get_weather() -> HTML[WeatherModel]:
    "https://api.weather.com/current"

def write_report(weather_data: WeatherModel) -> HTML:
    "Write a weather report based on the data"

# Use them in your code
async def main():
    weather_data = await get_weather()
    report = await write_report(weather_data)
    print(report)
```

## Parallel Execution

Since functions are async, you can run multiple operations in parallel:

```python
import asyncio

async def main():
    # Run multiple operations concurrently
    results = await asyncio.gather(
        get_weather(),
        read_config(),
        fetch_webpage()
    )
    
    weather, config, webpage = results
```

## File Path Conventions

To avoid ambiguity between file paths and LLM prompts, follow these conventions:

**✅ Clear file paths:**
- `./filename.txt` - relative file
- `../parent/file.json` - parent directory
- `/absolute/path/file.csv` - absolute path
- `C:\\Windows\\file.txt` - Windows absolute path

**✅ Clear LLM prompts:**
- `"analyze the data"` - no file extension or path indicators
- `"user preferences"` - general text without path structure

## Type Validation

Return types enable automatic validation:

```python
def get_config() -> JSON:
    "./config.json"  # Must return valid JSON

def generate_html() -> HTML:
    "Create a login form"  # Must return valid HTML

def write_text():
    "Write a summary"  # Returns plain text
```

## Error Handling

Functions will raise exceptions for:
- File not found
- Invalid URLs
- Network errors
- Type validation failures
- LLM API errors

```python
try:
    config = await get_config()
except FileNotFoundError:
    print("Config file not found")
except ValidationError:
    print("Invalid JSON format")
```

## Best Practices

1. **Use descriptive function names** that indicate what the operation does
2. **Specify return types** for automatic validation
3. **Use `./` prefix** for relative file paths to avoid ambiguity
4. **Keep LLM prompts clear** and avoid path-like strings
5. **Use multiline strings** for complex prompts
6. **Leverage async/await** for parallel operations

## Examples

### Complete Workflow

```python
from lamia.types import JSON, TEXT, HTML

# Data operations
def load_user_data() -> JSON:
    "./users.json"

def fetch_external_data() -> JSON:
    "https://api.example.com/data"

# Content generation
def create_user_report():
    '''
    Generate a detailed user activity report including:
    - User engagement metrics
    - Most active features
    - Recommendations for improvement
    '''

def generate_dashboard() -> HTML:
    "Create an admin dashboard with user statistics and charts"

# Main workflow
async def generate_admin_content():
    # Load data in parallel
    user_data, external_data = await asyncio.gather(
        load_user_data(),
        fetch_external_data()
    )
    
    # Generate content
    report = await create_user_report()
    dashboard = await generate_dashboard()
    
    return report, dashboard
```

This hybrid syntax makes it easy to combine file operations, web requests, and AI-generated content in a single, readable workflow.

## File Context (`with files()`)

Use `with files()` to index local directories so you can reference files in LLM prompts using `{@filename}` syntax:

```python
with files("~/Documents/", "~/projects/"):
    def answer_question(question: str, models="openai:gpt-4"):
        """
        Answer: {question}
        
        Use information from {@resume.pdf} and {@cover_letter.txt}
        """
```

Files are resolved using smart search: exact filename match, content grep, fuzzy matching, and path component matching. PDF and DOCX files are automatically extracted to text.

```python
# Exact path
{@resume.pdf}                     # Searches indexed directories
{@/Users/me/Documents/resume.pdf} # Absolute path always works

# Fuzzy matching
{@resum.pdf}    # Finds resume.pdf
{@config}       # Finds config.yaml, config.json, etc.
```

Nest with sessions for full workflows:

```python
with files("~/Documents/"):
    with session("job_application"):
        def fill_form(models="openai:gpt-4"):
            "Fill the form using {@resume.pdf}"
```

For full details on search strategies, error handling, and configuration see [File Context Documentation](../../docs/user-guide/files-context.md).

## Session Management

Use `with session()` for multi-step workflows that should persist across runs (login sequences, form filling, etc.). On subsequent runs, completed sessions are skipped automatically.

```python
def login_to_site():
    with session("login"):
        web.navigate("https://example.com/login")
        web.type_text("#username", "your_username")
        web.type_text("#password", "your_password")
        web.click("#login-button")
    
    # After session block — always runs
    web.navigate("https://example.com/dashboard")
```

**First run**: executes the block, saves the session on success.
**Subsequent runs**: detects valid session, skips the block entirely.

Sessions are stored in `.lamia_sessions/` and automatically invalidated on failure. Clear with `rm -rf .lamia_sessions/`.