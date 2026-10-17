# Lamia LLM Adapters

Adapters provide a unified interface for both remote (API-based) and local
(on-device) LLM providers.

## Architecture

```
BaseLLMAdapter (base.py)
├── generate()              — abstract
├── generate_messages()     — default: joins turns into one prompt for generate()
└── close()                 — abstract

OpenAICompatibleAdapter (openai_compatible_adapter.py)
├── generate()              — delegates to generate_messages() with one user turn
├── generate_messages()     — POSTs native role-tagged messages to API_URL
├── close()                 — closes the HTTP session
├── _build_payload()        — request body: model, messages, sampling fields set on the model
├── _parse_response()       — chat completions body → LLMResponse
├── _request_headers()      — Content-Type + Bearer from self.api_key
└── _post_json()            — HTTP + error classification
```

`OpenRouterAdapter` derives from `OpenAICompatibleAdapter`. `OpenAIAdapter`, `AnthropicAdapter`, `LamiaAdapter` and the local adapters derive from `BaseLLMAdapter` and implement their own requests.

---

## Implementing a New Adapter

### Path 1: OpenAI-compatible API (derive from OpenAICompatibleAdapter)

```python
from lamia.adapters.llm.openai_compatible_adapter import OpenAICompatibleAdapter

class MyAdapter(OpenAICompatibleAdapter):
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
```

Override `_build_payload()`, `_parse_response()`, `_request_headers()` or `REQUEST_TIMEOUT_SECONDS` to customize. A `BaseLLMAdapter` subclass that sets `API_URL` without implementing `generate()` fails to load with an error pointing to `OpenAICompatibleAdapter`.

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
| (automatic) | `OpenAICompatibleAdapter` subclasses — handled by `_post_json` |
| `raise_for_status(status, text, prefix)` | Custom HTTP with status code |
| `raise_for_connection_error(exc, prefix)` | Network/transport failures |
| `raise_for_sdk_error(exc, prefix)` | SDK exceptions with status attributes |

The three functions are public module-level functions in `base.py`.

---

## Contract Checking

`contract_checker.py` validates custom adapters at load time. Checks method existence, signatures, and return types. If the adapter overrides `generate()` without `API_URL`, logs an advisory about error handling.

User adapter discovery registers only concrete adapter classes defined in the scanned file; imported and abstract classes are skipped.

---

## Tips

- Use `LLMResponse` dataclass for all outputs.
- Read API keys from environment variables (never hardcode).
- For local adapters, provide clear error messages if the engine is not running.
- See OpenAI/Anthropic adapters for real-world examples of the custom-generate path, and `OpenRouterAdapter` for an `OpenAICompatibleAdapter` subclass.
