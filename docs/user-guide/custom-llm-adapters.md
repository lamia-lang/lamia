# Custom LLM Adapters

Use custom adapters when you want to add a provider Lamia does not ship by default.

## Where adapter files live

Place adapter files in an `extensions/adapters/` folder in your project:

```text
your-project/
├── extensions/
│   └── adapters/
│       └── mistral_adapter.py
└── app.py
```

Lamia discovers these adapters automatically.

## Full remote adapter example (Mistral)

```python
# extensions/adapters/mistral_adapter.py
from lamia.adapters.llm.base import BaseLLMAdapter, LLMResponse
from typing import Optional, Type
from pydantic import BaseModel
from lamia import LLMModel
import aiohttp


class MistralAdapter(BaseLLMAdapter):
    API_URL = "https://api.mistral.ai/v1/chat/completions"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None

    @classmethod
    def name(cls) -> str:
        return "mistral"

    @classmethod
    def env_var_names(cls) -> list[str]:
        return ["MISTRAL_API_KEY"]

    @classmethod
    def is_remote(cls) -> bool:
        return True

    async def async_initialize(self) -> None:
        self.session = aiohttp.ClientSession(headers={
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    async def generate(
        self,
        prompt: str,
        model: LLMModel,
        response_model: Optional[Type[BaseModel]] = None,
    ) -> LLMResponse:
        payload = {
            "model": model.get_model_name_without_provider(),
            "messages": [{"role": "user", "content": prompt}],
        }
        async with self.session.post(self.API_URL, json=payload) as resp:
            data = await resp.json()
            return LLMResponse(
                text=data["choices"][0]["message"]["content"],
                raw_response=data,
                usage=data.get("usage", {}),
                model=model.name,
            )

    async def close(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None
```

## Critical properties

These class methods define provider identity, credential lookup, and local/remote behavior:

```python
@classmethod
def name(cls) -> str:
    return "mistral"

@classmethod
def env_var_names(cls) -> list[str]:
    return ["MISTRAL_API_KEY"]

@classmethod
def is_remote(cls) -> bool:
    return True
```

- `name()` controls the provider prefix in model strings, for example `mistral:mistral-large-latest`.
- `env_var_names()` controls which environment variables Lamia will try for credentials.
- `is_remote()` tells Lamia whether this adapter calls a network API (`True`) or a local runtime (`False`).

If `is_remote()` returns `True`, your adapter usually needs a key from one of `env_var_names()` to work.

## Example usage

Use it with:

```python
from lamia import Lamia

lamia = Lamia("mistral:mistral-large-latest")
```

Set credentials:

```bash
export MISTRAL_API_KEY="..."
```

## Local adapter example (vLLM OpenAI-compatible server)

This pattern is similar to local adapters like Ollama: local runtime, no API key required, `is_remote() == False`.

```python
# extensions/adapters/vllm_adapter.py
from lamia.adapters.llm.base import BaseLLMAdapter, LLMResponse
from typing import Optional, Type
from pydantic import BaseModel
from lamia import LLMModel
import aiohttp


class VllmAdapter(BaseLLMAdapter):
    def __init__(self, base_url: str = "http://localhost:8000/v1"):
        self.base_url = base_url.rstrip("/")
        self.session: Optional[aiohttp.ClientSession] = None

    @classmethod
    def name(cls) -> str:
        return "vllm"

    @classmethod
    def env_var_names(cls) -> list[str]:
        return []

    @classmethod
    def is_remote(cls) -> bool:
        return False

    async def async_initialize(self) -> None:
        self.session = aiohttp.ClientSession(headers={"Content-Type": "application/json"})

    async def generate(
        self,
        prompt: str,
        model: LLMModel,
        response_model: Optional[Type[BaseModel]] = None,
    ) -> LLMResponse:
        payload = {
            "model": model.get_model_name_without_provider(),
            "messages": [{"role": "user", "content": prompt}],
        }
        async with self.session.post(f"{self.base_url}/chat/completions", json=payload) as resp:
            data = await resp.json()
            usage = data.get("usage", {})
            return LLMResponse(
                text=data["choices"][0]["message"]["content"],
                raw_response=data,
                usage=usage,
                model=model.name,
            )

    async def close(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None
```

Use it with:

```python
from lamia import Lamia

lamia = Lamia("vllm:meta-llama/Llama-3.1-8B-Instruct")
```

## Interface checklist

Your adapter must implement:

- `name()`
- `env_var_names()`
- `is_remote()`
- `generate(...)`
- `close()`

Optional but recommended:

- `async_initialize()`
- `supports_structured_output` property (set `True` only if your adapter truly supports native structured output)

