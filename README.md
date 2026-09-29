# Lamia - AI Native language
<div align="center">
  <p><strong>Write AI-powered scripts in plain English.</strong></p>
  <img src="assets/lamia_banner.png" alt="Lamia" width="360">
</div>

---

Lamia extends Python with human-readable syntax for AI commands, web automation, and file operations. Write what you want in plain English - Lamia handles the LLM calls, validates the output, and returns structured data.

How it guarantees results: every command runs through a built-in validator. If the output doesn't match the expected format or schema, Lamia retries automatically across a configurable model chain — escalating to the next model until it passes or the chain is exhausted. You define the contract once; Lamia enforces it on every run.

- Get your expected results in HTML, JSON, CSV, XML, YAML Markdown formats back
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

A minimal real-world example - extract stock quotes from Yahoo Finance into a CSV:

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

For more real-world examples, you can check the [Lamia Examples](https://github.com/lamia-lang/lamia-examples) repository.

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

### Using Lamia with a Claude Pro or Max Subscription

Lamia supports OpenAI, Anthropic, and Ollama out of the box. You can add other providers by creating a Python adapter that extends `BaseLLMAdapter` and placing it in the `extensions/adapters/` directory of your project.

A good example is running Lamia on your Claude Pro or Max subscription instead of pay-per-token API billing: see the [ready-to-use Claude subscription adapter](https://lamia-lang.github.io/lamia/user-guide/custom-llm-adapters/#claude-subscription). The [Custom LLM Adapters](https://lamia-lang.github.io/lamia/user-guide/custom-llm-adapters/) guide covers the full adapter API.

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

## Documentation

Full documentation: **[lamia-lang.github.io/lamia](https://lamia-lang.github.io/lamia/)**

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, doc building, and code style guidelines.

## License

[MIT](LICENSE)
