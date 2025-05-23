                    ╭──────────────────────╮
                    │        LAMIA         │
                    │    ⚡ LLM Engine ⚡    │
                    ╰──────────────────────╯
           🔮 Language Model Interface Automation

     Seamlessly connect with OpenAI, Anthropic, & Ollama

# Lamia

A Python project for interpreting and interacting with various Large Language Models (LLMs) through a unified interface. Lamia provides a consistent way to work with different LLM providers (OpenAI, Anthropic, Ollama) while ensuring output quality through customizable validation.

## Features

- 🤖 Multi-model support (OpenAI, Anthropic, Ollama)
- 🔄 Automatic fallback to alternative models
- ✅ Built-in and custom validation system
- 🛠 Configurable through YAML
- 🔌 Extensible adapter architecture
- 💻 Interactive CLI interface

## Installation

### For Users

If you just want to use Lamia in your project:

```bash
pip install .
```

### For Developers

If you plan to modify Lamia or contribute to its development:

```bash
# Install in development mode (-e flag makes the installation editable)
pip install -e .

# Install with development tools for code quality and testing
pip install -e ".[dev]"
```

The development installation includes:
- `pytest`: For running the test suite
- `black`: For code formatting
- `isort`: For import sorting
- `flake8`: For code linting

## Quick Start

1. Create a configuration file (`config.yaml`) in your project root:

```yaml
# Default model to use
default_model: "ollama"  # Options: openai, anthropic, ollama

# Model configurations
models:
  ollama:
    enabled: true
    model: "llama2"
    base_url: "http://localhost:11434"
    temperature: 0.7
    max_tokens: 2000
    context_size: 4096
```

2. Set up your environment:

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and replace the dummy API keys with your actual keys
# For OpenAI: Replace sk-your-openai-key-here with your actual OpenAI API key
# For Anthropic: Replace sk-ant-your-anthropic-key-here with your actual Anthropic API key
```

⚠️ **Important**: Never commit your `.env` file to version control! The `.gitignore` file already includes it, but make sure not to force-add it.

For Ollama:
```bash
# Make sure Ollama is installed: https://ollama.ai/download
# The service will be started automatically when needed
```

3. Start the interactive CLI:

```bash
lamia
```

This will start an interactive session where you can enter prompts and receive responses:

```
Lamia Interactive Mode
Enter your prompts (Ctrl+C or 'exit' to quit)
----------------------------------------

🤖 > Tell me about neural networks

Thinking... 🤔

🔮 Response:
----------------------------------------
Neural networks are computational systems inspired by biological brains...
----------------------------------------
Model: llama2
Tokens used: {'prompt_tokens': 5, 'completion_tokens': 42, 'total_tokens': 47}

🤖 > 
```

Use Ctrl+C or type 'exit' to quit the interactive session.

## Project Structure

- `lamia/`: Core package
  - `engine/`: Engine implementation and management
  - `cli.py`: Command-line interface
- `adapters/`: Model-specific adapters
  - `llm/`: Language Model adapters
- `examples/`: Example implementations
  - `custom_validators/`: Custom validator examples

## Validators

Lamia includes a robust validation system to ensure LLM outputs meet specific criteria.

### Strict vs. Forgiving Validation

Each validator supports a `strict` flag, which controls how strictly the output is validated:
- `strict: true` (default): Only accepts pure, valid output (e.g., only the HTML, JSON, or pattern match, with no extra text).
- `strict: false`: Accepts output that contains a valid block (e.g., a valid HTML or JSON block within a longer response).

If the `strict` flag is omitted, strict validation is used by default.

**Example config:**
```yaml
validation:
  enabled: true
  validators:
    - type: "html"
      strict: true
    - type: "json"
    - type: "regex"
      pattern: "^\\d{4}-\\d{2}-\\d{2}$"
      strict: true
```

**Example code:**
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

### Built-in Validators

- **HTML Validator**: Ensures output is valid HTML markup
- **JSON Validator**: Validates JSON structure and syntax
- **Regex Validator**: Matches output against custom regex patterns
- **Length Validator**: Enforces minimum and maximum length constraints
- **Atomic Type Validator**: Ensures output is a valid atomic type (integer, float, bool, or string)

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
from lamia.adapters.llm.validation.validators import AtomicTypeValidator

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
from lamia.adapters.llm.validation.validators import HTMLStructureValidator

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

## Development

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - Unix/MacOS: `source venv/bin/activate`
4. Install development dependencies: `pip install -e ".[dev]"`
5. Run tests: `pytest tests/` 

### Custom Validators

The `examples/custom_validators/` directory contains example implementations.

## Model Configuration

You can configure each model in your `config.yaml`. For advanced control, you can specify whether a model supports context memory (chat history) using the `has_context_memory` property. This affects how Lamia handles retries and prompt construction for validation.

Example:

```yaml
models:
  ollama:
    enabled: true
    default_model: neural-chat
    models:
      - name: neural-chat
        has_context_memory: true
      - name: llama2
        has_context_memory: false
  openai:
    enabled: true
    default_model: gpt-3.5-turbo
    models:
      - gpt-3.5-turbo  # has_context_memory will be inferred as true
      - text-davinci-003
        has_context_memory: false  # override if needed
```

**Note:**
- If `has_context_memory` is not set for a model, Lamia will use adapter-specific logic to infer whether the model supports context memory:
  - **OpenAI:** Most `gpt-*` and `*turbo*` models are chat-based and support context memory. Legacy completion models (e.g., `text-davinci-003`) are stateless.
  - **Anthropic:** All Claude models are chat-based and support context memory.
  - **Ollama:** If the model name contains `chat` or `instruct`, context memory is assumed; otherwise, it is not.
- You can always override the default by specifying `has_context_memory` in your config.

## License

[MIT License](LICENSE)