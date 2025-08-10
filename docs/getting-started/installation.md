# Installation

This guide will help you install Lamia and set up your development environment.

## Requirements

- Python 3.8 or higher
- pip (Python package installer)

## Installation Methods

### Using pip (Recommended)

Install Lamia directly from PyPI:

```bash
pip install lamia
```

### Development Installation

For development or to get the latest features, install from source:

```bash
git clone https://github.com/your-username/lamia.git
cd lamia
pip install -e .
```

## Dependencies

Lamia comes with several optional dependencies for different features:

### Core Dependencies
These are installed automatically:
- `pydantic>=2.0.0` - For data validation
- `pyyaml>=6.0.0` - For YAML configuration
- `python-dotenv>=0.19.0` - For environment variable management

### LLM Dependencies
For language model integration:
```bash
pip install openai>=1.12.0      # For OpenAI GPT models
pip install anthropic>=0.18.1   # For Anthropic Claude models
pip install aiohttp>=3.9.0      # For async HTTP (Ollama)
```

### Web Automation Dependencies
For web scraping and automation:
```bash
pip install playwright          # For browser automation
pip install selenium            # Alternative browser automation
pip install beautifulsoup4>=4.12.0  # For HTML parsing
```

### File Processing Dependencies
For advanced file operations:
```bash
pip install boto3               # For AWS S3 integration
pip install google-cloud-storage  # For Google Cloud Storage
```

## Verification

Verify your installation by running:

```bash
python -c "import lamia; print(lamia.__version__)"
```

Or use the CLI:

```bash
lamia --version
```

## Configuration

After installation, create a basic configuration file:

```yaml
# config.yaml
engine:
  default_timeout: 30
  retry_attempts: 3

validation:
  strict_mode: true

llm:
  default_provider: "openai"
  openai:
    api_key: "${OPENAI_API_KEY}"
    model: "gpt-3.5-turbo"
```

## Environment Variables

Set up your environment variables for API access:

```bash
export OPENAI_API_KEY="your-openai-api-key"
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```

Or create a `.env` file in your project directory:

```bash
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
```

## Next Steps

Now that Lamia is installed, head over to the [Quick Start Guide](quickstart.md) to begin using it in your projects.

## Troubleshooting

### Common Issues

#### Import Error
If you encounter import errors, ensure you have the correct Python version:
```bash
python --version  # Should be 3.8+
```

#### Permission Error
On some systems, you might need to use `sudo` or install in a virtual environment:
```bash
python -m venv lamia-env
source lamia-env/bin/activate  # On Windows: lamia-env\Scripts\activate
pip install lamia
```

#### Dependency Conflicts
If you have dependency conflicts, try creating a fresh virtual environment:
```bash
python -m venv fresh-env
source fresh-env/bin/activate
pip install lamia
```

For more help, check our [GitHub Issues](https://github.com/your-username/lamia/issues) or create a new issue.