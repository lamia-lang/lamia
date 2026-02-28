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
git clone https://github.com/lamia-lang/lamia.git
cd lamia
pip install -e .
```

## Verification

Verify your installation by running:


```bash
lamia -h
```

## Configuration

After installation, create a basic configuration file with

```bash
lamia init
```

or copy an existing config.yaml file to your project directory.

## Environment Variables

lamia init will ask you to install the LLM API keys. But you can set up your environment variables with the following command:

```bash
export OPENAI_API_KEY="your-openai-api-key"
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```

Or create a `.env` file in your project directory:

```bash
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
```

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

For more help, check our [GitHub Issues](https://github.com/lamia-lang/lamia/issues) or create a new issue.