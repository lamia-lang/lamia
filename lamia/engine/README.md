# Lamia Engine

This directory contains the core engine implementation and management for Lamia, including the main engine, LLM adapter management, and configuration handling.

## Quick Start

## Project Structure (Engine)

- `engine.py`: Main engine implementation
- `llm_manager.py`: LLM adapter management
- `config_manager.py`: Configuration handling

### Custom Validators (Simple Functions and Lamia Validators)

You can provide a list of validators to the `validators` argument. Each validator can be:
- A simple function that takes the response text and returns True/False
- A Lamia validator class instance (with a `.validate(text)` method)
- You can mix both in the same list

If any validator fails, a `ValueError` is raised.

**Requests from the easiest to advanced **

```python

from lamia import Lamia
import os

os.environ["OPENAI_API_KEY"] = "sk-..."
simple = Lamia("openai") # include a model without validation
answer = simple.run("Say hello world!")

with_default_validation = Lamia("ollama", "openai") # Default validation will be applied and if the request wil oollama fails openai reques will be send
with_default_validation.run("Give me an HTMl file")

lamia = Lamia("openai", "ollama", api_keys={"openai": "sk-..."})
answer = lamia.run("What is quantum computing?")


from lamia.validators import LengthValidator
def must_contain_hello(text):
    return "hello" in text.lower()

length_validator = LengthValidator(min_length=10, max_length=1000)

with_combined_validators = Lamia(
    "openai",
    api_keys={"openai": "sk-..."},
    validators=[must_contain_hello, length_validator]
)

answer = with_combined_validators.run("Say hello world!")

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


with_temperature_and_max_tokens = Lamia("openai", api_keys={"openai": "sk-..."})
answer = with_temperature_and_max_tokens.run(
    "Write a creative story about a robot.",
    temperature=0.9,   # More creative
    max_tokens=500     # Limit response length
)
```

## Exception: MissingAPIKeysError

`MissingAPIKeysError` is raised if a required API key for an LLM engine (e.g., OpenAI, Anthropic) is missing from the environment.

### When is it raised?
- When the default or any fallback engine in your config requires an API key, but the key is not set in the environment or passed via `api_keys`.

### What does it contain?
- The exception message lists all missing engines and the required environment variables.

### How to handle it
- Catch the exception and handle it as appropriate (log, fallback, notify user, etc).