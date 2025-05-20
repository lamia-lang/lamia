# Lamia Engine

This directory contains the core engine implementation and management for Lamia, including the main engine, LLM adapter management, and configuration handling.

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

```yaml
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

## Project Structure (Engine)

- `engine.py`: Main engine implementation
- `llm_manager.py`: LLM adapter management
- `config_manager.py`: Configuration handling