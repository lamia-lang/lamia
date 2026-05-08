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
- `generate(self, prompt, model, response_model=None)`: Generate a response from the LLM model.
- `close(self)`: Clean up resources.

See `base.py` for the full interface and docstrings.

---

## Boilerplate Examples

### Remote Adapter (API-based)

```python
from .base import BaseLLMAdapter, LLMResponse
import aiohttp
from typing import Optional, Type
from pydantic import BaseModel
from lamia import LLMModel

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

    async def generate(
        self,
        prompt: str,
        model: LLMModel,
        response_model: Optional[Type[BaseModel]] = None,
    ) -> LLMResponse:
        payload = {"model": model.get_model_name_without_provider(), "prompt": prompt}
        if response_model is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "schema": response_model.model_json_schema(),
                    "strict": True,
                },
            }
        async with self.session.post(self.API_URL, json=payload) as resp:
            data = await resp.json()
            return LLMResponse(
                text=data["result"],
                raw_response=data,
                usage=data.get("usage", {}),
                model=model.name
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
from typing import Optional, Type
from pydantic import BaseModel
from lamia import LLMModel

class MyLocalAdapter(BaseLLMAdapter):
    def __init__(self, model_path: str, **engine_config):
        self.model_path = model_path
        self.engine_config = engine_config
        self.session = None

    async def initialize(self):
        # Optionally launch a local engine or check if running
        # subprocess.Popen(["my-engine", ...])
        self.session = aiohttp.ClientSession()

    async def generate(
        self,
        prompt: str,
        model: LLMModel,
        response_model: Optional[Type[BaseModel]] = None,
    ) -> LLMResponse:
        # Example: send prompt to local HTTP server
        payload = {"model_path": self.model_path, "prompt": prompt}
        # Local adapters can ignore response_model if unsupported
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

## Error Handling

Lamia classifies adapter errors automatically at the framework boundary — **custom
adapters do not need to implement error normalization**.  Just let exceptions
propagate naturally and Lamia takes care of the rest.

### What the framework does for you

1. **Secret redaction** — any `sk-*` tokens in error messages are replaced with
   `[REDACTED]` before the message reaches the user or logs.
2. **Error classification** — raw exceptions are mapped to typed categories
   (`auth`, `rate_limit`, `quota`, `timeout`, `network`, `provider`) via
   `LLMProviderError.from_exception()`.
3. **User-facing messages** — concise, actionable text is generated per
   category (e.g. "Authentication failed: invalid API key").
4. **IDE integration** — the IDE shows different UI per error type (e.g. an
   "Update API Key" button for auth errors, "Retry" for transient ones).

### Best practices for custom adapters

- **Do** raise `RuntimeError` (or any exception) with a descriptive message.
  Include the HTTP status code and provider error text when available — the
  framework extracts useful information from it.

  ```python
  raise RuntimeError(f"MyProvider error ({response.status}): {error_text}")
  ```

- **Do** use `sanitize_api_error()` when including raw provider responses that
  might contain API keys.  This is optional defense-in-depth — the framework
  applies it again at the boundary — but prevents accidental leaks in your own
  log statements.

  ```python
  from lamia.adapters.llm.base import sanitize_api_error
  raise RuntimeError(f"MyProvider error: {sanitize_api_error(error_text)}")
  ```

- **Don't** implement your own error classification or user-message generation.
  The framework handles this centrally so all adapters behave consistently.

- **Don't** catch and swallow provider exceptions silently.  Let them propagate
  so the retry handler and error classifier can do their job.

### Error type reference

| Type | Typical cause | User sees |
|------|-------------|-----------|
| `auth` | Invalid / expired API key (401) | "Update API Key" button |
| `rate_limit` | Too many requests (429) | "Retry" button |
| `quota` | Insufficient credits (402) | Check provider account |
| `timeout` | Request timed out (408) | "Retry" button |
| `network` | Connection refused / DNS failure | "Retry" button |
| `provider` | Any other provider error | "Retry" button |

---

## Tips

- Use the provided `LLMResponse` dataclass for all outputs.
- For remote adapters, always read API keys from environment variables (never hardcode them).
- For local adapters, provide clear error messages if the engine is not installed or running.
- See existing adapters (OpenAI, Anthropic, Ollama) for real-world examples.

---

## Questions?

Open an issue. 