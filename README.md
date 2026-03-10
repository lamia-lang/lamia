<div align="center">
  <h1>Lamia</h1>
  <p><strong>Write AI-powered scripts in plain English.</strong></p>
  <img src="assets/lamia_banner.png" alt="Lamia" width="360">
</div>

---

Lamia extends Python with human-readable syntax for AI commands, web automation, and file operations. Write what you want in plain English - Lamia handles the LLM calls, validates the output, and returns structured data.

- Write AI prompts as Python functions - no SDK boilerplate
- Built-in validators: get your expected results in HTML, JSON, CSV, XML, Markdown formats back - guaranteed
- Web automation with automatic data extraction into Pydantic models
- Multi-model support: OpenAI, Anthropic, Ollama (and extensible)
- Model evaluation to find the cheapest model that still passes validation

## Installation

```bash
pip install lamia-lang
```

## Quick Start

Create a `.lm` file and run it with `lamia your_script.lm`:

```python
# Ask AI and create a login from using our model
page = "Create a login form" -> HTML[LoginForm]

# Read a local file as typed JSON
config = "./config.json" -> JSON[OnlyTheConfigsWeNeed]

# Scrape a website into a Pydantic model
quote = "https://finance.yahoo.com/quote/AAPL" -> HTML[StockQuote]
```

A real-world example - extract stock quotes from Yahoo Finance into a CSV:

```python
class StockQuote(BaseModel):
    ticker: str = Field(description="Stock ticker symbol, e.g. AAPL")
    open: float = Field(description="Open price from the Quote Summary section")
    bid: str = Field(description="Bid price from the Quote Summary section")
    ask: str = Field(description="Ask price from the Quote Summary section")
    bid_size: int = Field(description="Bid size (number of lots) from the Quote Summary")
    ask_size: int = Field(description="Ask size (number of lots) from the Quote Summary")

for ticker in ["QQQ", "VOO", "VGT"]:
    "extract the stock quote data from https://finance.yahoo.com/quote/{ticker}" -> File(CSV[StockQuote], "stocks.csv", append=True)
```
### Running from Python

Lamia can be used as a Python library as well.

```python
from lamia import Lamia

lamia = Lamia()

ai_response = lamia.run(
    "Create a login form",
    "openai:gpt4o",
    "anthropic:claude",
    return_type=HTML[LoginForm]
)
```

### Using Lamia Claude Pro or Max Subscription

Currently, Lamia supports only 3 LLM providers: OpenAI, Anthropic, and Ollama (local models). But you can easily extend it to support other providers by creating a new adapter by extending the `BaseLLMAdapter` class and placing it in the `extensions/adapters/llm` directory in the root of the project.

For more information see the Implementing a New Adapter section of the [Lamia LLM Adapters](lamia/adapters/llm/README.md) documentation.

Here is a ready to use adapter for Claude Pro or Max subscription. Just place it in the `extensions/adapters/llm` directory in the root of the project. IMPORTANT: Using this llm adapter might result your account being banned by Anthropic.  This is just to show you what can be an example having own (not supported by Lamia) llm adapter.


and add the following to your config.yaml file:
```yaml
model_chain:
  - name: "claude-max:claude-sonnet-4"
    max_retries: 3
```

```python
"""
Adapter for anthropic-max-router local proxy.

Routes requests through anthropic-max-router
(https://github.com/nsxdavid/anthropic-max-router) — an OpenAI-compatible
endpoint backed by Anthropic's Claude API via OAuth.
Works with Claude Pro ($20/mo) and Max ($100/$200/mo) subscriptions
for flat-rate billing instead of pay-per-token.

The router stores its OAuth tokens in .oauth-tokens.json relative to the
working directory, so all commands below use ~ as a stable anchor.
"""

import logging
from typing import Optional

import aiohttp

from lamia.adapters.llm.base import BaseLLMAdapter, LLMResponse
from lamia import LLMModel

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://127.0.0.1:3000"


class ClaudeMaxAdapter(BaseLLMAdapter):
    """Adapter for a local claude-max-api proxy (OpenAI-compatible, no streaming)."""

    @classmethod
    def name(cls) -> str:
        return "claude-max"

    @classmethod
    def env_var_names(cls) -> list[str]:
        return [] # No env variables like API key names needed

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

    async def generate(self, prompt: str, model: LLMModel) -> LLMResponse:
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

        url = f"{self.base_url}/v1/chat/completions"
        logger.debug("Requesting %s with model=%s", url, model_name)

        async with self.session.post(url, json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(
                    f"claude-max-api error (status {response.status}): {error_text}"
                )

            data = await response.json()

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

## Module Documentation

| Module | Description |
|--------|-------------|
| **[Hybrid Syntax](lamia/interpreter/README.md)** | `.lm` file syntax: LLM commands, file operations, web actions, sessions, `-> File(...)` write syntax |
| **[Validation](lamia/validation/README.md)** | Validators for HTML, JSON, YAML, XML, Markdown, CSV, Pydantic models |
| **[Web Adapters](lamia/adapters/web/README.md)** | Browser automation (Selenium, Playwright) and HTTP clients |
| **[LLM Adapters](lamia/adapters/llm/README.md)** | Implementing new LLM provider adapters |
| **[Engine](lamia/engine/README.md)** | Core engine, LLM manager, configuration |
| **[Selector Resolution](lamia/engine/managers/web/selector_resolution/README.md)** | CSS/XPath and AI-powered natural language selectors |
| **[Evaluation](lamia/eval/README.md)** | Model evaluation to find cost-effective models |

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, doc building, and code style guidelines.