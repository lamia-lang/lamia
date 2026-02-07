                    ╭──────────────────────╮
                    │        LAMIA         │
                    │    ⚡ LLM Engine ⚡    │
                    ╰──────────────────────╯
           🔮 Human centric AI-enabled programming language

---

**[Documentation](https://your-username.github.io/lamia/)** · **[Contributing](CONTRIBUTING.md)** · **[DeepWiki](https://deepwiki.com/your-username/lamia)**

---

A language and framework for interpreting and interacting with various Large Language Models (LLMs) and other external systems through a unified interface. Lamia provides a consistent way to work with different LLM providers (OpenAI, Anthropic, Ollama) while ensuring output quality through customizable validation.

## Features

- 🤖 Multi-model support (OpenAI, Anthropic, Ollama)
- 🔄 Automatic fallback to alternative models
- ✅ Built-in and extensible validation system
- 🛠 Highly configurable
- 🔌 Extensible adapter architecture
- 💻 Can be used though CLI interface and by Python scripts 

## Installation

```bash
# For users
pip install .

# For developers
pip install -e ".[dev]"
```

## Quick Start

### Running .hu Files

Create a `.hu` file and run it with `lamia your_script.hu`:

```python
# LLM command
def generate_webpage() -> HTML:
    "Create a responsive landing page with a contact form"

# Read a file
def read_config() -> JSON:
    "./config.json"

# Write LLM output to file
def generate_report() -> File(HTML, "report.html"):
    "Generate an HTML report about quarterly results"

# Web request
def fetch_data() -> JSON:
    "https://api.example.com/data"
```

### Running from Python

```python
from lamia import Lamia

lamia = Lamia()

ai_response = lamia.run(
    "Generate an HTML file about neural networks",
    "openai:gpt4o",
    "anthropic:claude",
)
```

### Interactive CLI

```bash
lamia
```

## Module Documentation

| Module | Description |
|--------|-------------|
| **[Hybrid Syntax](lamia/interpreter/README.md)** | `.hu` file syntax: LLM commands, file operations, web actions, sessions, `-> File(...)` write syntax |
| **[Validation](lamia/validation/README.md)** | Validators for HTML, JSON, YAML, XML, Markdown, CSV, Pydantic models |
| **[Web Adapters](lamia/adapters/web/README.md)** | Browser automation (Selenium, Playwright) and HTTP clients |
| **[LLM Adapters](lamia/adapters/llm/README.md)** | Implementing new LLM provider adapters |
| **[Engine](lamia/engine/README.md)** | Core engine, LLM manager, configuration |
| **[Selector Resolution](lamia/engine/managers/web/selector_resolution/README.md)** | CSS/XPath and AI-powered natural language selectors |
| **[Evaluation](lamia/eval/README.md)** | Model evaluation to find cost-effective models |

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, doc building, and code style guidelines.