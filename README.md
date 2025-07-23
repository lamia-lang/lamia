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
- ✅ Built-in and extensible validation system
- 🛠 Highly configurable
- 🔌 Extensible adapter architecture
- 💻 Can be used though CLI interface and by Python scripts 

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

### Running from any python script

```python
from lamia import Lamia

lamia = Lamia() # no LLM model is specified for teh session individual requests need to specify LLM model/s if they want to work with LLMs.

# Model chain with retries and fallbacks
ai_response = lamia.run(
    "Generate an HTML file about neural networks",
    "openai:gpt4o",      # Try GPT-4 first
    "anthropic:claude",  # Fall back to Claude if GPT-4 fails
    ("ollama:llama:7b", 2)  # Finally try Llama up to 2 times
)

lamia_with_model_chain = Lamia("ollama:llama:2b", "ollama:llama:7b")

# Now we are Lamia's type system to validate response
# Note, if we specify model chain here, the session's model chain ("ollama:llama:2b", "ollama:llama:7b") will be ignored for this particular request only
ai_response = lamia.run(
    "Generate a file about neural networks", HTML
)

#Full constructor with overriding retry_config that disables. retries ti fetch data from external systmes like LLMs when the first request fails. See "External System Retry Configuration" at the bottom if
openai_key = ...
anthropic_key = ...
lamia_full_constructor = Lamia(("openai:gpt4o", 2), "anthropic:claude-3-sonnet-20240229", api_keys={"openai":openai_key, "anthropic":anthropic_key}, retry_config=ExternalOperationRetryConfig(max_attempts=1))

responses = asyncio.gather(
    lamia.run_async(
        "Generate a file about neural networks", HTML, 
    ),
    lamia.run_async(
        "Generate a file about LLMs", Markdown, models = "deepseek-r1:14b"
    ),
)

class MyHTMLStructure(BaseModel):
    h1: str
    div: IconAndSubtitle
    p: str

class IconAndSubtitle(BaseModel):
    icon: str
    h2: str

ai_response = lamia.run(
    "Generate a file about neural networks", HTML[MyHTMLStructure]
)
```

### Running a standalone service

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

## Validation

Lamia includes a robust validation system to ensure LLM outputs meet specific quality and format requirements. Validators can be combined, customized, and configured to validate responses against various criteria.

### Quick Example

```python

Lamia(... Validators)

run_async(... Validators)


```

### Available Validators

- **File Validators**: HTML, JSON, YAML, XML, Markdown, CSV
- **Structure Validators**: Validate against Pydantic model schemas
- **Type Validators**: Atomic types, objects, regex patterns
- **Quality Validators**: Length constraints, functional validation

**📚 For complete validation documentation, examples, and guides:**
- **[Validation Module Documentation](lamia/validation/README.md)** - Comprehensive guide to all validators
- **[Custom Validator Examples](examples/custom_validators/)** - Example implementations

The validation documentation covers:
- All built-in validators and their configuration options
- Creating custom validators (simple and structure-aware)
- Strict vs permissive validation modes  
- Advanced features like type conversion and error handling
- Complete API reference and usage examples

## Advanced Configuration

### External System Retry Configuration

Lamia automatically handles retries for external system operations (API calls, file operations, etc). The default behavior is well-tuned for different operation types:
- Local operations: 1 attempt (no retries)
- Network operations: 3 attempts with exponential backoff
- LLM API calls: 5 attempts with longer delays

You should only override this configuration if the default behavior doesn't meet your specific needs:

```python
from lamia import Lamia
from datetime import timedelta

# Custom external system retry configuration - only if defaults don't suit your needs
# This is used to allow 10 mintes for the response and set ma attempts to 5
retry_config = ExternalOperationRetryConfig(
    max_attempts=5,                           # Maximum number of retry attempts
    max_total_duration=timedelta(minutes=10)  # Maximum total time for all retries
)

# Initialize Lamia with custom retry configuration
lamia = Lamia(retry_config=retry_config)
```

You might want to customize this for cases like:
- Unreliable network conditions requiring more retries
- Strict timeout requirements needing shorter retry durations
- Special rate limit handling for your API quotas

For most users, the default retry behavior will be appropriate, and you should focus on configuring your model chain retries in `run_async()`.

## Development

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - Unix/MacOS: `source venv/bin/activate`
4. Install development dependencies: `pip install -e ".[dev]"`
5. Run tests: `pytest tests/`

## License

# TODO: ...