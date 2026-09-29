# Custom LLM Adapters

Use custom adapters when you want to add a provider Lamia does not ship by default.

## Where adapter files live

Place adapter files in an `extensions/adapters/` folder in your project:

```text
your-project/
├── extensions/
│   └── adapters/
│       └── mistral.py
└── app.py
```

Lamia discovers these adapters automatically.  The file name should match
the provider name returned by `name()`.

---

## Example 1 — Zero-config (OpenAI-compatible API)

For providers that use the OpenAI `/v1/chat/completions` convention, you
only need to set `API_URL` and identity methods. Here's an example adapter for Mistral:

```python
# extensions/adapters/mistral.py
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

    async def close(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None
```

That's it. The base class handles session creation, Bearer auth from
`self.api_key`, the POST request, response parsing, and HTTP error
classification. Use it with:

```bash
export MISTRAL_API_KEY="..."
```

```python
from lamia import Lamia
lamia = Lamia("mistral:mistral-large-latest")
```

### LLM providers compatible with the default generate() (OpenAI convention)

These providers all use the same `/v1/chat/completions` request/response
format.  A zero-config adapter (just `API_URL` + identity) works for all:

| Provider | API_URL | Notes |
|----------|---------|-------|
| Mistral | `https://api.mistral.ai/v1/chat/completions` | |
| Groq | `https://api.groq.com/openai/v1/chat/completions` | |
| Together AI | `https://api.together.xyz/v1/chat/completions` | |
| Fireworks AI | `https://api.fireworks.ai/inference/v1/chat/completions` | |
| Perplexity | `https://api.perplexity.ai/chat/completions` | |
| DeepSeek | `https://api.deepseek.com/v1/chat/completions` | |
| OpenRouter | `https://openrouter.ai/api/v1/chat/completions` | Aggregator |
| Anyscale | `https://api.endpoints.anyscale.com/v1/chat/completions` | |
| vLLM | `http://localhost:8000/v1/chat/completions` | Self-hosted |
| Ollama | `http://localhost:11434/v1/chat/completions` | Local, OpenAI-compat mode |
| LM Studio | `http://localhost:1234/v1/chat/completions` | Local |
| LocalAI | `http://localhost:8080/v1/chat/completions` | Local |
| text-generation-webui | `http://localhost:5000/v1/chat/completions` | Local, with OpenAI ext |

---

## Example 2 — Custom HTTP (Google Gemini API)

When the API uses HTTP but has a different request or response structure,
override `generate()`.  Use the public functions `raise_for_status()` and
`raise_for_connection_error()` from `lamia.adapters.llm.base` to get
automatic retry classification.

```python
# extensions/adapters/gemini_http.py
from lamia.adapters.llm.base import (
    BaseLLMAdapter, LLMResponse,
    raise_for_status, raise_for_connection_error,
)
from typing import Optional
from lamia import LLMModel
import aiohttp


class GeminiHttpAdapter(BaseLLMAdapter):
    """Direct Gemini HTTP adapter (/v1beta/models/*:generateContent)."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None

    @classmethod
    def name(cls) -> str:
        return "gemini-http"

    @classmethod
    def env_var_names(cls) -> list[str]:
        return ["GEMINI_API_KEY"]

    @classmethod
    def is_remote(cls) -> bool:
        return True

    async def async_initialize(self) -> None:
        if self.session is None:
            self.session = aiohttp.ClientSession(headers={"content-type": "application/json"})

    async def generate(self, prompt, model, response_model=None):
        if self.session is None:
            await self.async_initialize()

        model_name = model.get_model_name_without_provider() or "gemini-pro"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
        }
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_name}:generateContent?key={self.api_key}"
        )

        try:
            async with self.session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise_for_status(response.status, error_text, "Gemini API error")
                data = await response.json()
        except aiohttp.ClientError as e:
            raise_for_connection_error(e, "Failed to communicate with Gemini API")

        text = ""
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                if "text" in part:
                    text = part["text"]
                    break
            if text:
                break

        return LLMResponse(
            text=text,
            raw_response=data,
            usage=data.get("usage", {}),
            model=model.name,
        )

    async def close(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None
```

Key points:
- `raise_for_status(status, text, prefix)` — classifies 429/4xx/5xx automatically
- `raise_for_connection_error(exc, prefix)` — marks network failures as transient
- These are public functions, not private methods

---

## Example 3 — SDK adapter

When the provider has a Python SDK, use it directly and map exceptions with
`raise_for_sdk_error()`:

```python
# extensions/adapters/cohere.py
from lamia.adapters.llm.base import BaseLLMAdapter, LLMResponse, raise_for_sdk_error
from lamia import LLMModel
import cohere


class CohereAdapter(BaseLLMAdapter):

    def __init__(self, api_key: str):
        self.client = cohere.AsyncClientV2(api_key=api_key)

    @classmethod
    def name(cls) -> str:
        return "cohere"

    @classmethod
    def env_var_names(cls) -> list[str]:
        return ["COHERE_API_KEY"]

    @classmethod
    def is_remote(cls) -> bool:
        return True

    async def generate(self, prompt, model, response_model=None):
        try:
            response = await self.client.chat(
                model=model.get_model_name_without_provider(),
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            raise_for_sdk_error(e, "Cohere API error")

        return LLMResponse(
            text=response.message.content[0].text,
            raw_response=response,
            usage={"total_tokens": response.meta.tokens.input_tokens + response.meta.tokens.output_tokens},
            model=model.name,
        )

    async def close(self) -> None:
        pass
```

`raise_for_sdk_error(exc, prefix)` reads structured `status_code` / `status`
fields from the exception object. No string parsing.

---

## Example 4 — Claude Pro or Max subscription { #claude-subscription }

This adapter routes requests through [anthropic-max-router](https://github.com/nsxdavid/anthropic-max-router), a local OpenAI-compatible proxy backed by Anthropic's Claude API via OAuth. It lets Lamia run on a Claude Pro ($20/mo) or Max ($100/$200/mo) subscription with flat-rate billing instead of pay-per-token.

!!! warning
    Using this adapter may result in your account being banned by Anthropic. It is an example of a custom adapter for a provider not officially supported by Lamia.

**1.** Save the following as `extensions/adapters/claude_max.py` in your project:

```python
import asyncio
import logging
from typing import Optional, Type

import aiohttp

from lamia.adapters.llm.base import (
    BaseLLMAdapter, LLMResponse, make_strict_schema, strip_for_anthropic,
    raise_for_status, raise_for_connection_error,
)
from lamia import LLMModel
from pydantic import BaseModel

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://127.0.0.1:3000"


class ClaudeMaxAdapter(BaseLLMAdapter):

    @classmethod
    def name(cls) -> str:
        return "claude-max"

    @classmethod
    def env_var_names(cls) -> list[str]:
        return []

    @classmethod
    def is_remote(cls) -> bool:
        return False

    def __init__(self, base_url: str = DEFAULT_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.session: Optional[aiohttp.ClientSession] = None

    async def async_initialize(self) -> None:
        if self.session is None:
            self.session = aiohttp.ClientSession(
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=600),
            )

    async def generate(
        self,
        prompt: str,
        model: LLMModel,
        response_model: Optional[Type[BaseModel]] = None,
    ) -> LLMResponse:
        if self.session is None:
            await self.async_initialize()
        assert self.session is not None

        model_name = model.get_model_name_without_provider() or "claude-sonnet-4"

        payload: dict = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }

        if model.temperature is not None:
            payload["temperature"] = model.temperature
        if model.max_tokens is not None:
            payload["max_tokens"] = model.max_tokens
        if model.top_p is not None:
            payload["top_p"] = model.top_p
        if response_model is not None:
            # The router proxies to Anthropic's API, which rejects JSON Schema
            # value-constraint keywords (minimum, maxLength, etc.) outright.
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "schema": strip_for_anthropic(make_strict_schema(response_model)),
                    "strict": True,
                },
            }

        url = f"{self.base_url}/v1/chat/completions"
        logger.debug("Requesting %s with model=%s", url, model_name)

        try:
            async with self.session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise_for_status(response.status, error_text, "claude-max-api error")
                data = await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            raise_for_connection_error(e, "claude-max-api connection error")

        usage_data = data.get("usage", {})

        return LLMResponse(
            text=data["choices"][0]["message"]["content"],
            raw_response=data,
            usage={
                "prompt_tokens": usage_data.get("prompt_tokens", 0),
                "completion_tokens": usage_data.get("completion_tokens", 0),
                "total_tokens": usage_data.get("total_tokens", 0),
            },
            model=model_name,
        )

    async def close(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None
```

**2.** Start anthropic-max-router on port 3000 (see [anthropic-max-router setup](https://github.com/nsxdavid/anthropic-max-router)).

**3.** Add the model to your `config.yaml`:

```yaml
model_chain:
  - name: "claude-max:claude-sonnet-4-5-20250929"
    max_retries: 3
```

Any Claude model name works after the `claude-max:` prefix (e.g. `claude-max:claude-opus-4`).

---

## Error handling summary

| Adapter type | How errors are classified |
|---|---|
| Zero-config (default `generate()`) | Fully automatic — base class handles it |
| Custom HTTP (`generate()` override) | Call `raise_for_status()` and `raise_for_connection_error()` |
| SDK (`generate()` override) | Call `raise_for_sdk_error()` |

Classification rules:

- HTTP `429` -> `ExternalOperationRateLimitError`
- HTTP `4xx` (except `429`) -> `ExternalOperationPermanentError`
- HTTP `5xx` -> `ExternalOperationTransientError`
- connection/timeout/client failures -> `ExternalOperationTransientError`

---

## Contract checking

When Lamia loads a custom adapter, it validates the implementation
automatically. Violations are logged as warnings:

- `name()` returns a non-empty string
- `is_remote()` returns a boolean
- `env_var_names()` returns a list of strings
- `generate()` has the correct signature
- `close()` exists and is callable

If the adapter overrides `generate()` without defining `API_URL`, an info
message reminds you to handle HTTP errors via the public helper functions.

---

## Import style (global imports only)

Keep all imports at module top level. Do not use local imports inside methods.

---

## Interface checklist

Must implement:

- `name()`
- `env_var_names()`
- `is_remote()`
- `close()`

For zero-config adapters, also set:

- `API_URL` (class attribute or property)

For custom adapters, override:

- `generate(prompt, model, response_model)` — full control over request/response

Optional:

- `models()` — allows `lamia models --provider <name>`
- `async_initialize()` — custom startup (default auto-creates session when `API_URL` exists)
- `supports_structured_output` property
