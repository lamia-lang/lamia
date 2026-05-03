# Using Lamia in Python Apps

## Why Lamia?

Every LLM provider ships its own SDK — OpenAI has `openai`, Anthropic has `anthropic`, Google has `google-genai`. They work, but they lock you into a single provider. Switch models and you rewrite your integration layer.

Multi-provider libraries solve the lock-in problem but create new ones. Some bury you in abstractions (chains, runnables, LCEL). Others, like Pydantic AI, get both validation and multi-provider support right — and offer a rich ecosystem of built-in tools (web search, code execution, file search, MCP) and agent patterns on top. If you need those capabilities, Pydantic AI is an excellent choice.

Lamia occupies a different niche. It is a **scripting language with a Python library**, not an agent framework. The Python API gives you the same validated LLM calls that `.lm` files use: `run()`, a Pydantic model, and typed data back. On top of that, Lamia has built-in web automation (browser control, form filling, scraping) and file operations that work from the same interface. The model fallback chain is declarative — list your models and Lamia tries them in order.

### Comparison matrix

This table reflects what each tool actually does well today. Lamia is young and the ecosystem is smaller.

| Feature | Lamia | Pydantic AI | OpenAI SDK | Anthropic SDK | LiteLLM | LangChain |
|---------|-------|-------------|-----------|--------------|---------|-----------|
| Multi-provider support | OpenAI, Anthropic, Ollama + custom adapters | OpenAI, Anthropic, Gemini, Groq, Mistral, Ollama, and more | OpenAI only | Anthropic only | 100+ providers | 70+ providers |
| Structured output validation | Built-in with retry feedback loop | First-class Pydantic validation with retries | Native JSON mode (strict) | Native JSON mode + tool use | Client-side JSON validation | Optional, schema-based |
| Model fallback chain | Built-in, declarative | `FallbackModel` with exception/response handlers | Manual | Manual | Via router | Manual |
| Built-in tools | Web automation, file I/O | Web search, code execution, file search, MCP, image gen | No | No | No | Via integrations |
| Custom validators (functional, length, type) | Built-in | Output validators | No | No | No | No |
| Custom LLM adapters | Drop-in via extensions folder | Model registration | N/A | N/A | Provider plugins | Provider wrappers |
| Async support | `run()` and `run_async()` | Native async + `run_sync()` | Async client | Async client | Async | Via LCEL |

Use Lamia when you want validated structured output with model fallback, web automation, and file operations in a single interface. Use Pydantic AI when you need agent patterns, built-in tools (web search, code execution, MCP), or deep observability. Use provider SDKs when you need only one provider and want zero abstraction. Use LiteLLM or LangChain when you need 70+ providers or deep ecosystem integrations.

## Install

```bash
pip install lamia-lang
```

```python
from lamia import Lamia
```

## Environment setup

Lamia loads API keys in two ways, depending on how your app manages secrets.

**Option 1 — Standard `.env` variables (zero-config)**

Lamia automatically loads from the environment variables or the `.env` files using hardcoded variable names. Just set the expected variables and Lamia picks them up:

```bash
# .env file
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

Loading priority (highest to lowest):

1. Shell environment variables (already set by the user)
2. Project-level `.env` in the current working directory

**Option 2 — Custom variable names via `api_keys`**

When your app uses different env variable names for the model API keys, or when you load them in a different way, pass them explicitly:

```python
import os
from lamia import Lamia

lamia = Lamia(
    "openai:gpt-4o-mini",
    api_keys={
        "openai": os.environ["MY_OPENAI_SECRET"],
        "anthropic": os.environ["MY_ANTHROPIC_SECRET"],
    }
)
```

This way Lamia never touches your environment — you control where the keys come from.

### Supported providers

Out of the box, Lamia ships adapters for:

- **OpenAI** — `openai:gpt-4o`, `openai:gpt-4o-mini`, etc.
- **Anthropic** — `anthropic:claude-sonnet-4-20250514`, `anthropic:claude-3-5-haiku-latest`, etc.
- **Ollama** — `ollama:llama3`, `ollama:mixtral`, etc. (requires a running Ollama process on your machine)

Note: Ollama does not work from the Python library when the Ollama service is not running on your machine. Lamia does not auto-start the Ollama process — make sure `ollama serve` is active before calling `Lamia("ollama:llama3")`.

For any provider not listed above, you can add a custom adapter (see [Extensions folder](#extensions-folder) below).

Model fallback is supported by passing multiple models:

```python
lamia = Lamia(
    "openai:gpt-4o-mini",
    "anthropic:claude-3-5-haiku-latest",
)
```

To retry with the same model before falling back, repeat it:

```python
lamia = Lamia(
    "openai:gpt-4o-mini",
    "openai:gpt-4o-mini",
    "anthropic:claude-3-5-haiku-latest",
)
```

## Structured output (recommended)

For production use, return typed data instead of free text.

```python
from pydantic import BaseModel, Field
from lamia import Lamia
from lamia.types import JSON


class UserSummary(BaseModel):
    name: str = Field(description="User full name")
    role: str = Field(description="Current role")
    risk_level: str = Field(description="low, medium, or high")


lamia = Lamia("openai:gpt-4o-mini")

summary = lamia.run(
    "Summarize user Jane Doe, Staff Engineer, with medium risk profile",
    return_type=JSON[UserSummary],
)

print(summary.name, summary.role, summary.risk_level)
```

Lamia validates the LLM response against your Pydantic model and retries with error feedback if validation fails. For advanced Pydantic model features (field constraints, patterns, descriptions, enums), see the [Pydantic Models Guide](pydantic-models.md).

## Multiple Lamia instances

You can create multiple `Lamia` instances with different models, configurations, or API keys. Each instance is independent:

```python
import os
from pydantic import BaseModel, Field
from lamia import Lamia
from lamia.types import JSON


class Summary(BaseModel):
    text: str = Field(description="Summary text")
    confidence: float = Field(description="Confidence 0.0 to 1.0")


fast_lamia = Lamia("openai:gpt-4o-mini")
smart_lamia = Lamia("anthropic:claude-sonnet-4-20250514")

quick_result = fast_lamia.run("Summarize: AI is transforming software", return_type=JSON[Summary])
deep_result = smart_lamia.run("Summarize: AI is transforming software", return_type=JSON[Summary])

print(f"Fast: {quick_result.text}")
print(f"Smart: {deep_result.text}")
```

This is useful when different parts of your app need different models — a cheap model for simple tasks and a powerful one for complex reasoning.

## Async usage

Use `run_async()` in async apps:

```python
import asyncio
from lamia import Lamia


async def main() -> None:
    lamia = Lamia("openai:gpt-4o-mini")
    result = await lamia.run_async("Write a short welcome message")
    print(result)


asyncio.run(main())
```

### Parallel LLM calls

Use `asyncio.gather` with `run_async` to execute multiple LLM calls concurrently:

```python
import asyncio
from pydantic import BaseModel, Field
from lamia import Lamia, ExternalOperationError
from lamia.types import JSON


class Sentiment(BaseModel):
    label: str = Field(description="positive, negative, or neutral")
    confidence: float = Field(description="Confidence score 0.0 to 1.0")


async def main() -> None:
    lamia = Lamia("openai:gpt-4o-mini")

    reviews = [
        "This product is amazing, best purchase ever!",
        "Terrible quality, broke after one day.",
        "It's okay, nothing special.",
    ]

    results = await asyncio.gather(
        *[
            lamia.run_async(
                f"Analyze the sentiment: {review}",
                return_type=JSON[Sentiment],
            )
            for review in reviews
        ],
        return_exceptions=True,
    )

    for review, result in zip(reviews, results):
        if isinstance(result, Exception):
            print(f"{review[:40]}... -> FAILED: {result}")
        else:
            print(f"{review[:40]}... -> {result.label} ({result.confidence})")


asyncio.run(main())
```

When using `return_exceptions=True`, failed calls (e.g., all models in the chain exhausted) return as exception objects instead of crashing the entire `gather`. This lets you handle partial failures gracefully — successful results are still available even if some calls failed.

If you omit `return_exceptions=True`, the first exception from any call will cancel the entire batch and propagate immediately.

## Error handling and exceptions

Lamia exports specific exception types you can import and catch:

```python
from lamia import (
    Lamia,
    MissingAPIKeysError,
    ExternalOperationError,
    ExternalOperationPermanentError,
    ExternalOperationTransientError,
    ExternalOperationRateLimitError,
    ExternalOperationFailedError,
    OllamaNotInstalledError,
)

lamia = Lamia("openai:gpt-4o-mini")

try:
    result = lamia.run("Generate a report")
except MissingAPIKeysError:
    print("API key not configured — check .env or pass api_keys=")
except ExternalOperationRateLimitError as e:
    print(f"Rate limited. Retry history: {e.retry_history}")
except ExternalOperationPermanentError as e:
    print(f"Permanent failure (bad key, invalid request): {e}")
except ExternalOperationTransientError as e:
    print(f"Temporary failure (network, timeout): {e}")
except ExternalOperationFailedError as e:
    print(f"Unclassified failure: {e.original_error}")
```

The exception hierarchy:

- `ExternalOperationError` — base class for all external failures
    - `ExternalOperationPermanentError` — won't resolve by retrying (bad API key, invalid request)
        - `OllamaNotInstalledError` — Ollama binary not found
    - `ExternalOperationTransientError` — temporary failures (network issues, timeouts)
    - `ExternalOperationRateLimitError` — API rate limits exceeded
    - `ExternalOperationFailedError` — unclassified failure

All `ExternalOperationError` subclasses carry `retry_history` (list of retry attempts) and `original_error` (the underlying exception).

### Available types

Lamia exports these return types from `lamia.types`:

```python
from lamia.types import JSON, HTML, CSV, YAML, XML, Markdown, TEXT
```

Use them with `return_type=` to validate and extract structured output:

```python
result = lamia.run("Create a login form", return_type=HTML)
data = lamia.run("List users", return_type=JSON[UserModel])
rows = lamia.run("Generate sales data", return_type=CSV[SalesRow])
```

Additional public types:

```python
from lamia import LLMModel, LamiaResult
from lamia.types import ExternalOperationRetryConfig, InputType
```

- `LLMModel` — typed model configuration with `temperature`, `max_tokens`, `top_p`, etc.
- `LamiaResult` — full result object with `result_text`, `typed_result`, and `tracking_context`
- `ExternalOperationRetryConfig` — retry behavior configuration
- `InputType` — enum of HTML input types for web form automation

## Extensions folder

The extensions folder lets you extend Lamia with custom LLM adapters and custom validators without modifying the Lamia source code.

By default, Lamia looks for an `extensions/` folder in the **current working directory** at the time the `Lamia` instance is created. Create the following folder structure for this in the root of your project:

```
your-project/
├── extensions/
│   ├── adapters/     # Custom LLM adapters (*.py files)
│   └── validators/   # Custom validators (*.py files)
├── your_app/
│   └── main.py       # Your Python app that uses Lamia
└── ...
```

If you need the extensions folder elsewhere (e.g., inside a package), pass it via `from_config()`:

```python
lamia = Lamia.from_config({
    "model_chain": [{"name": "openai:gpt-4o-mini"}],
    "extensions_folder": "path/to/my_extensions",
})
```

### Custom LLM adapters

To add a provider that Lamia doesn't support, create a Python file in `extensions/adapters/` that subclasses `BaseLLMAdapter`:

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

Now you can use it:

```python
lamia = Lamia("mistral:mistral-large-latest")
```

The `BaseLLMAdapter` interface requires these methods:

| Method | Purpose |
|--------|---------|
| `name()` | Provider identifier used in model strings (e.g., `"mistral"`) |
| `env_var_names()` | Environment variable names for API key lookup |
| `is_remote()` | `True` for cloud APIs, `False` for local models |
| `async_initialize()` | Set up HTTP sessions or load local models |
| `generate(prompt, model, response_model)` | Send prompt and return `LLMResponse` |
| `close()` | Clean up resources |

### Custom validators

Lamia uses validators automatically based on the `return_type` you pass to `run()`. The built-in validators (JSON, HTML, CSV, Markdown, YAML, XML) are selected by the type marker. Custom validators in the extensions folder follow the same pattern — they are discovered and loaded automatically by the engine.

Currently, there is no public API to attach a custom validator directly to a `run()` call from the Python library. Custom validators are used when the engine resolves return types from `.lm` file execution. It is planned to add a public API to attach a custom validator directly to a `run()` call in the future.

```python
result = lamia.run("Generate a report", return_type=JSON[Report])

# Your custom validation
if result.confidence < 0.5:
    raise ValueError(f"Low confidence: {result.confidence}")
```

To define a custom validator for use in `.lm` workflows, create a Python file in `extensions/validators/` that subclasses `BaseValidator`:

```python
# extensions/validators/profanity_validator.py
from lamia.validation.base import BaseValidator, ValidationResult


class ProfanityValidator(BaseValidator):
    BLOCKED_WORDS = {"badword1", "badword2"}

    def __init__(self, strict: bool = True):
        super().__init__(strict=strict)

    @classmethod
    def name(cls) -> str:
        return "profanity"

    @property
    def initial_hint(self) -> str:
        return "Please ensure the response contains no profanity."

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        words = set(response.lower().split())
        found = words & self.BLOCKED_WORDS
        if found:
            return ValidationResult(
                is_valid=False,
                error_message=f"Profanity detected: {', '.join(found)}",
                hint=self.initial_hint,
            )
        return ValidationResult(is_valid=True, validated_text=response)

    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        return await self.validate_strict(response, **kwargs)
```

The `BaseValidator` interface requires:

| Method / Property | Purpose |
|-------------------|---------|
| `name()` | Validator identifier |
| `initial_hint` | Hint text included in the LLM prompt to guide output format |
| `validate_strict(response)` | Strict validation — rejects anything not exactly right |
| `validate_permissive(response)` | Permissive validation — tries to extract valid data from noisy output |

Lamia ships several built-in validators: `FunctionalValidator` (test code against test cases), `AtomicTypeValidator` (int, float, bool, string), `LengthValidator` (min/max length constraints), and format validators for JSON, HTML, CSV, Markdown, YAML, and XML.

## Advanced topics

### Config dictionary

Use `from_config()` when you need per-model parameters like temperature, or when your config comes from a file or service:

```python
import os
from lamia import Lamia

config = {
    "model_chain": [
        {"name": "openai:gpt-4o-mini", "max_retries": 2, "temperature": 0.3},
        {"name": "anthropic:claude-3-5-haiku-latest", "max_retries": 1},
    ],
    "api_keys": {
        "openai": os.environ.get("OPENAI_API_KEY"),
        "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
    },
}

lamia = Lamia.from_config(config)
result = lamia.run("Generate 3 release notes bullets")
print(result)
```

The config dictionary is another way to set per-model parameters like `temperature`, `max_tokens`, `top_p`, `top_k`, `frequency_penalty`, `presence_penalty`, and `seed`. It also supports all constructor options (`web_config`, `extensions_folder`, etc.) in a single dict.

You can also instantiate with the constructor and pass `web_config` and `retry_config` as typed parameters:

```python
from lamia import Lamia, LLMModel
from lamia.types import ExternalOperationRetryConfig

lamia = Lamia(
    LLMModel(name="openai:gpt-4o-mini", temperature=0.3),
    retry_config=ExternalOperationRetryConfig(
        max_attempts=3,
        base_delay=1.0,
        max_delay=60.0,
        exponential_base=2.0,
        max_total_duration=None,
    ),
    web_config={
        "browser_engine": "selenium",
        "browser_options": {"headless": True},
    },
)
```

Using `LLMModel` directly in the constructor gives you typed access to model parameters without needing `from_config()`.

## Common errors and what to do

- **Missing API key**: Set provider keys in `.env` or pass `api_keys` to the constructor.
- **Wrong model name**: Use `provider:model` format (e.g., `openai:gpt-4o-mini`).
- **Validation failures**: Simplify your prompt and improve `Field(description=...)` in your Pydantic model. See the [Pydantic Models Guide](pydantic-models.md).
- **Calling sync inside async**: Use `run_async()` instead of `run()` in async contexts.
- **Ollama not responding**: Make sure `ollama serve` is running before calling Lamia.

## Next steps

- [Pydantic Models Guide](pydantic-models.md) — advanced Pydantic field definitions for better LLM output
- [Guide to the `.lm` Syntax](../user-guide/lm-syntax.md) — write Lamia programs with the hybrid Python syntax
- [Guide to the `.hu` Syntax](../user-guide/hu-syntax.md) — plain-text prompt templates
- [Web Automation](../user-guide/web-automation.md) — browser and HTTP automation