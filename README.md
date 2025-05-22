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