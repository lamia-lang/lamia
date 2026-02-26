# Lamia LLM Adapters

This directory contains adapters for integrating various Large Language Models (LLMs) into Lamia. Adapters provide a unified interface for both remote (API-based) and local (on-device) models.

## Adapter Types

- **Remote Adapters**: Connect to cloud APIs (e.g., OpenAI, Anthropic). Require API keys.
- **Local Adapters**: Run models on your machine (e.g., Ollama, llama.cpp). May require local services or model files.

---

## Implementing a New Adapter

All adapters must subclass `BaseLLMAdapter` from `base.py` and implement the following async methods:

- `name(cls)`: Return the provider name (e.g., 'openai', 'anthropic', 'ollama'). This method is used to identify the provider in the config.yaml file. For example, if you want to add an adapter for Mistral, you would return 'mistral', Then in the config.yaml file you can use 'mistral:<model_name>' in the model_chain section.
- `env_var_names(cls)`: Return a list of environment variable names to try, in order of precedence. You will usually use this for defining the API key environment variable names. You can return an empty list if no API key is required.
- `is_remote(cls)`: Return True if this adapter makes network calls, False for local.
- `initialize(self)`: Prepare resources (e.g., open API session, load model).
- `generate(self, prompt, ...)`: Generate a response from the model.
- `close(self)`: Clean up resources.

See `base.py` for the full interface and docstrings.

---

## Boilerplate Examples

### Remote Adapter (API-based)

```python
from .base import BaseLLMAdapter, LLMResponse
import aiohttp

class MyRemoteAdapter(BaseLLMAdapter):
    API_URL = "https://api.example.com/v1/generate"

    def __init__(self, api_key: str, model: str = "my-model"):
        self.api_key = api_key
        self.model = model
        self.session = None
        # ... Init other variables you might need

    async def initialize(self):
        self.session = aiohttp.ClientSession(headers={
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })

    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        payload = {"model": self.model, "prompt": prompt, **kwargs}
        async with self.session.post(self.API_URL, json=payload) as resp:
            data = await resp.json()
            return LLMResponse(
                text=data["result"],
                raw_response=data,
                usage=data.get("usage", {}),
                model=self.model
            )

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None
```

**Don't forget:** Add your API key to the `.env` file (e.g., `MY_REMOTE_API_KEY=...`). Never commit secrets to version control!

---

### Local Adapter (On-device)

```python
from .base import BaseLLMAdapter, LLMResponse
import subprocess
import aiohttp

class MyLocalAdapter(BaseLLMAdapter):
    def __init__(self, model_path: str, **engine_config):
        self.model_path = model_path
        self.engine_config = engine_config
        self.session = None

    async def initialize(self):
        # Optionally launch a local engine or check if running
        # subprocess.Popen(["my-engine", ...])
        self.session = aiohttp.ClientSession()

    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        # Example: send prompt to local HTTP server
        payload = {"model_path": self.model_path, "prompt": prompt, **kwargs}
        async with self.session.post("http://localhost:1234/generate", json=payload) as resp:
            data = await resp.json()
            return LLMResponse(
                text=data["result"],
                raw_response=data,
                usage=data.get("usage", {}),
                model=self.model_path
            )

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None
```

- For local adapters, consider making the engine launch/configuration flexible (e.g., via constructor args or config file).

---

## Configuration: `config.yaml`

Model and adapter settings are managed in `config.yaml` at the project root. Example:

```yaml
models:
  openai:
    enabled: true
    default_model: gpt-3.5-turbo
    models:
      - gpt-4
      - gpt-3.5-turbo
  ollama:
    enabled: true
    default_model: llama2
    models:
      - llama2
      - mixtral
```

- **Why list models in config.yaml?**
  - It provides validation, default settings, and a clear overview of available models.
  - It enables features like fallback, validation, and CLI auto-completion.
- **What if I want to use a model not listed?**
  - You can edit `config.yaml` at runtime, or (if your adapter supports it) allow dynamic model selection by passing the model name directly to the adapter. For maximum flexibility, consider making your adapter accept arbitrary model names, but warn users if the model is not in config.

---

## Adding a New Adapter

1. Create your adapter in a new file (e.g., `my_adapter.py`).
2. Subclass `BaseLLMAdapter` and implement the required methods.
3. Register your adapter in the appropriate `__init__.py` if you want it to be importable as part of the package.
4. Add configuration options to `config.yaml` if needed.
5. Document any required environment variables (API keys) in `.env.example`.

---

## Tips

- Use the provided `LLMResponse` dataclass for all outputs.
- For remote adapters, always read API keys from environment variables (never hardcode them).
- For local adapters, provide clear error messages if the engine is not installed or running.
- See existing adapters (OpenAI, Anthropic, Ollama) for real-world examples.

---

## Questions?

Open an issue. 