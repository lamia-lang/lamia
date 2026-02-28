# .hu File Syntax

Lamia `.hu` and `.lm` files use a hybrid Python syntax that lets you write LLM commands, file operations, and web actions as regular function definitions. Lamia syntax can be combined with normal Python code. So you get the power of Python combined with human-friendly syntax for LLM commands and other operations needed for daily tasks by non-technical users. You can run Lamia scripts with:

```bash
lamia your_script.hu
```

## The execution flow

Lamia detects its own syntax and executes through its engine, the rest of the code is executed as normal Python code. Here are some function definitions that will be executed by Lamia:

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

Users must be careful, because unlike Python, Lamia functions must skip return statements. See the example below:

```python
# The return statement makes this a Python function which returns the string "Write a short story about a robot discovering emotions"
def generate_story():
   return "Write a short story about a robot discovering emotions"

# This function is a Lamia function which sends the string "Write a short story about a robot discovering emotions" to the AI.
def generate_story():
   "Write a short story about a robot discovering emotions"

```

Lamia uses `->` syntax to return data. In Python `->` is used to define the return type of the function. In Lamia it is used to actually return a value or stream data.

## Return Types

Without return types, Lamia feels incomplete. Return type markers are more than markers, they are extractors and validators at runtime. Here is an example of how to use return types:

```python
def get_data() -> JSON:
    "./users.json"   # Must be valid JSON - otherwise the function will fail

def generate_page() -> HTML:
    "Create a login form"   # Must be valid HTML - otherwise the function will fail

def plain_text() -> TEXT:
    "Write a summary"   # No validation, just extraction
```

Available types: `HTML`, `JSON`, `YAML`, `XML`, `Markdown`, `CSV`, `TEXT`

## Simplified Syntax

For one-line functions, defining functions seems like overkill sometimes. That is why Lamia provides a simplified syntax. The functions we wrote above can be shortened to:

```python
"./users.json" -> JSON:

"Create a login form" -> HTML:

"Write a summary" -> TEXT:
```

But for these executions we won't be able to catch the result of the function. We need to assign the result to a variable.

```python
data = "./users.json" -> JSON:

page = "Create a login form" -> HTML:

summary = "Write a summary" -> TEXT:
```

But if we are not interested in catching the values and we want to save the execution result to a file, we can use the `-> File(...)` syntax.

```python
"./users.json" -> File(JSON, "users.json"):

"Create a login form" -> File(HTML, "login.html"):

"Write a summary" -> File(TEXT, "summary.txt"):
```

### Model Selection

Instead of simplified syntax, we need function definitions if we want to execute the function later, execute many times in different parts of the script, etc.

There is however a very important reason to use function definitions: model selection. All LLM commands in Lamia scripts use the global model chain coming from the config.yaml file mostly. But for some LLM commands users might need to use different models and even model chains. Here are examples of how to use model selection:

```python
def analyze(models="openai:gpt-4"):
    "Analyze the data"

def with_fallback(models=["openai:gpt-4", "anthropic:sonnet-4"]):
    "Generate a report with model fallback"

# Same as above but gpt-4 will be retried twice before falling back to sonnet-4
def with_fallback(models=["openai:gpt-4", 'openai:gpt-4', "anthropic:sonnet-4"]):
    "Generate a report with model fallback"
```

## Variable substitution

Variable substitution is a feature that allows you to use variables in your LLM prompts, web actions and file operations. Example:

```python
def stock_data(ticker: str = "AAPL") -> File(CSV[StockQuote], "stocks.csv", append=True):
    "extract the stock quote data https://finance.yahoo.com/quote/{ticker}"

for ticker in ["AAPL", "NVDA", "GOOG"]:
    stock_data(ticker)

# Or with simpler syntax
for ticker in ["AAPL", "NVDA", "GOOG"]:
    "extract the stock quote data https://finance.yahoo.com/quote/{ticker}" -> File(CSV[StockQuote], "stocks.csv", append=True)
```

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

In addition, Lamia's `file` action API can be used:

```python
content = file.append("/path/to/file.txt")
content = file.read("data.csv", encoding="latin-1")
```

### Writing to Files

As we have seen, the `-> File(...)` syntax can be used to save the execution result to a file. For complex file operations:

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

## Imports

Lamia avoids explicit imports. All Lamia types and interfaces are available without any import statements. But if you mix it with Python code, you will import Python dependencies as usual.

Because of implicit imports, IDEs will show warnings on some Lamia commands. They need to be ignored if the syntax is correct.

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

## Advanced: Async and Parallel Execution

Functions can be defined as async and executed in parallel:

```python
import asyncio

async def main():
    results = await asyncio.gather(
        get_weather(),
        read_config(),
        fetch_webpage()
    )
```