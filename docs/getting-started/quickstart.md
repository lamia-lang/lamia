# Quick Start Guide

This guide will help you get up and running with Lamia in minutes.

... what goes here, lol ?

maybe those?

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

## Next Steps

Now that you've seen the basics, explore these areas:

- **[Configuration Guide](configuration.md)**: Learn about advanced configuration options
- **[API Reference](../reference/)**: Complete API documentation
- **[Examples](../examples/basic.md)**: More comprehensive examples

## Getting Help

- Check the [API Reference](../reference/) for detailed documentation
- Browse [Examples](../examples/basic.md) for more use cases
- Visit our [GitHub Issues](https://github.com/lamia-lang/lamia/issues) for support
- Read the [User Guide](../user-guide/cli.md) for in-depth tutorials