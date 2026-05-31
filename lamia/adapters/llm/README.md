# Lamia LLM Adapters

Adapters provide a unified interface for both remote (API-based) and local
(on-device) LLM providers.

## Architecture

```
BaseLLMAdapter (base.py)
├── generate()              — default: OpenAI chat completions POST to API_URL
├── _post_json()            — internal: HTTP + error classification
├── _get_or_create_session()— internal: lazy session with Bearer auth
├── _resolve_api_url()      — internal: reads API_URL attribute
├── _request_headers()      — internal: Content-Type + Bearer from self.api_key
└── close()                 — abstract
```

Built-in adapters (OpenAI, Anthropic) override `generate()` entirely because
they use SDKs or non-standard response formats.

---

## Implementing a New Adapter

### Path 1: OpenAI-compatible API (no generate override)

```python
class MyAdapter(BaseLLMAdapter):
    API_URL = "https://api.example.com/v1/chat/completions"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = None

    @classmethod
    def name(cls) -> str:
        return "myprovider"

    @classmethod
    def env_var_names(cls) -> list[str]:
        return ["MYPROVIDER_API_KEY"]

    @classmethod
    def is_remote(cls) -> bool:
        return True

    async def close(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None
```

### Path 2: Custom HTTP (override generate)

```python
from lamia.adapters.llm.base import raise_for_status, raise_for_connection_error

class MyAdapter(BaseLLMAdapter):
    # ... identity methods ...

    async def generate(self, prompt, model, response_model=None):
        try:
            async with self.session.post(url, json=payload) as resp:
                if resp.status != 200:
                    raise_for_status(resp.status, await resp.text(), "my-api error")
                data = await resp.json()
        except aiohttp.ClientError as e:
            raise_for_connection_error(e, "my-api connection error")
        return LLMResponse(text=..., raw_response=data, usage=..., model=model.name)
```

### Path 3: SDK (override generate)

```python
from lamia.adapters.llm.base import raise_for_sdk_error

class MyAdapter(BaseLLMAdapter):
    # ... identity methods ...

    async def generate(self, prompt, model, response_model=None):
        try:
            response = await self.sdk_client.chat(...)
        except Exception as e:
            raise_for_sdk_error(e, "my-sdk error")
        return LLMResponse(text=..., raw_response=response, usage=..., model=model.name)
```

---

## Error Classification

| Function | When to use |
|---|---|
| (automatic) | Default `generate()` — handled by `_post_json` |
| `raise_for_status(status, text, prefix)` | Custom HTTP with status code |
| `raise_for_connection_error(exc, prefix)` | Network/transport failures |
| `raise_for_sdk_error(exc, prefix)` | SDK exceptions with status attributes |

All are public module-level functions in `base.py`.

---

## Contract Checking

`contract_checker.py` validates custom adapters at load time. Checks method
existence, signatures, and return types. If the adapter overrides `generate()`
without `API_URL`, logs an advisory about error handling.

---

## Tips

- Use `LLMResponse` dataclass for all outputs.
- Read API keys from environment variables (never hardcode).
- For local adapters, provide clear error messages if the engine is not running.
- See OpenAI/Anthropic adapters for real-world examples of the custom-generate path.
