                    ╭──────────────────────╮
                    │        LAMIA         │
                    │    ⚡ LLM Engine ⚡   │
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

## Programmatic Usage

```python
import asyncio
from lamia.engine import LamiaEngine

async def main():
    # Initialize the engine
    async with LamiaEngine() as engine:
        # Generate a response
        response = await engine.generate(
            "Explain quantum computing in simple terms.",
            temperature=0.7,
            max_tokens=1000
        )
        print(f"Response: {response.text}")
        print(f"Model used: {response.model}")
        print(f"Token usage: {response.usage}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Project Structure

- `lamia/`: Core package
  - `engine.py`: Main engine implementation
  - `llm_manager.py`: LLM adapter management
  - `config_manager.py`: Configuration handling
  - `cli.py`: Command-line interface
- `adapters/`: Model-specific adapters
  - `llm/`: Language Model adapters
- `examples/`: Example implementations
  - `custom_validators/`: Custom validator examples

## Validators

Lamia includes a robust validation system to ensure LLM outputs meet specific criteria.

### Built-in Validators

- **HTML Validator**: Ensures output is valid HTML markup
- **JSON Validator**: Validates JSON structure and syntax
- **Regex Validator**: Matches output against custom regex patterns
- **Length Validator**: Enforces minimum and maximum length constraints

### Custom Validators

The `examples/custom_validators/` directory contains example implementations:

1. **Code Validator** (`code_validator.py`):
```python
from lamia.adapters.llm.validation.base import BaseValidator

validator = CodeValidator(language="python", strict=True)
result = validator.validate(code)
```

2. **Sentiment Validator** (`sentiment_validator.py`):
```python
from examples.custom_validators.sentiment_validator import validate_sentiment

result = validate_sentiment("This is a great example!")
```

## Advanced Usage

### Using Multiple Models with Fallback

```python
from lamia.engine import LamiaEngine

async def generate_with_fallback():
    async with LamiaEngine() as engine:
        # Configure validation with fallback
        response = await engine.generate(
            "Write a Python function that implements quicksort.",
            temperature=0.7
        )
        # If primary model fails validation, it will automatically
        # try fallback models as configured
        return response

```

### Custom Validation Chain

```python
validation:
  enabled: true
  max_retries: 3
  validators:
    - type: "length"
      min_length: 100
      max_length: 1000
    - type: "custom_file"
      path: "path/to/your/validator.py"
    - type: "regex"
      pattern: "^[\\s\\S]*$"
```

## Development

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - Unix/MacOS: `source venv/bin/activate`
4. Install development dependencies: `pip install -e ".[dev]"`
5. Run tests: `pytest tests/`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[MIT License](LICENSE)