# Lamia Engine

This directory contains the core engine implementation and management for Lamia, including the main engine, LLM adapter management, and configuration handling.

## Quick Start

### Minimal Example

```python
from lamia import Lamia

# Option 1: Set API keys as environment variables (recommended)
# import os
# os.environ["OPENAI_API_KEY"] = "sk-..."
# os.environ["ANTHROPIC_API_KEY"] = "sk-ant..."

# Option 2: Pass API keys directly (leanest for scripts)
lamia = Lamia("openai", "ollama", api_keys={"openai": "sk-...", "anthropic": "sk-ant..."})

answer = lamia.run("Explain quantum computing in simple terms.")
print(answer)
```

## Project Structure (Engine)

- `engine.py`: Main engine implementation
- `llm_manager.py`: LLM adapter management
- `config_manager.py`: Configuration handling

## Exception: MissingAPIKeysError

`MissingAPIKeysError` is raised if a required API key for an LLM engine (e.g., OpenAI, Anthropic) is missing from the environment.

### When is it raised?
- When the default or any fallback engine in your config requires an API key, but the key is not set in the environment or passed via `api_keys`.

### What does it contain?
- The exception message lists all missing engines and the required environment variables.

### How to handle it
- Catch the exception and handle it as appropriate (log, fallback, notify user, etc).

### Example
```python
from lamia import Lamia
from lamia.engine.llm_manager import MissingAPIKeysError

try:
    lamia = Lamia("openai", api_keys={"openai": "sk-..."})
    answer = lamia.run("Hello world!")
except MissingAPIKeysError as e:
    print(str(e))
    # Handle error (e.g., exit, log, etc)
```

If you see this error, provide the missing API keys as environment variables, via the `api_keys` argument, or remove the relevant engines from your config.

## Advanced Usage

### Using Multiple Models with Fallback

```python
from lamia import Lamia

lamia = Lamia("openai", "ollama", api_keys={"openai": "sk-..."})
answer = lamia.run("Write a Python function that implements quicksort.")
print(answer)
```

### Setting Temperature and Max Tokens

You can override generation parameters per call:

```python
from lamia import Lamia

lamia = Lamia("openai", api_keys={"openai": "sk-..."})
answer = lamia.run(
    "Write a creative story about a robot.",
    temperature=0.9,   # More creative
    max_tokens=500     # Limit response length
)
print(answer)
```

### Custom Validators (Simple Functions and Lamia Validators)

You can provide a list of validators to the `validators` argument. Each validator can be:
- A simple function that takes the response text and returns True/False
- A Lamia validator class instance (with a `.validate(text)` method)
- You can mix both in the same list

If any validator fails, a `ValueError` is raised.

```python
from lamia import Lamia
from lamia.validators import LengthValidator

def must_contain_hello(text):
    return "hello" in text.lower()

length_validator = LengthValidator(min_length=10, max_length=1000)

lamia = Lamia(
    "openai",
    api_keys={"openai": "sk-..."},
    validators=[must_contain_hello, length_validator]
)

answer = lamia.run("Say hello world!")
print(answer)
```

---

**For most users, just use:**

```python
from lamia import Lamia
lamia = Lamia("openai", "ollama", api_keys={"openai": "sk-..."})
answer = lamia.run("What is quantum computing?")
print(answer)