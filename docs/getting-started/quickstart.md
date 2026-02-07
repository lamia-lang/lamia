# Quick Start Guide

This guide will help you get up and running with Lamia in minutes.

## Basic Setup

### 1. Create a Configuration File

Create a `config.yaml` file in your project directory:

```yaml
engine:
  default_timeout: 30
  max_retries: 3

validation:
  strict_mode: true

llm:
  default_provider: "openai"
  openai:
    api_key: "${OPENAI_API_KEY}"
    model: "gpt-3.5-turbo"
```

### 2. Set Environment Variables

```bash
export OPENAI_API_KEY="your-api-key-here"
```

## Your First Lamia Script

### Example 1: Basic Validation

```python
from lamia.validation import validate
from lamia.validation.validators import JSONValidator

# Sample data to validate
data = {
    "name": "John Doe",
    "age": 30,
    "email": "john@example.com"
}

# Define validation schema
schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer", "minimum": 0},
        "email": {"type": "string", "format": "email"}
    },
    "required": ["name", "age", "email"]
}

# Validate the data
validator = JSONValidator(schema)
result = validate(data, validator)

if result.is_valid:
    print("Data is valid!")
else:
    print(f"Validation errors: {result.errors}")
```

### Example 2: Web Automation

```python
from lamia.adapters.web.browser import PlaywrightAdapter
from lamia.actions.web import NavigateAction, ExtractAction

# Initialize browser adapter
browser = PlaywrightAdapter()

# Navigate to a webpage
navigate = NavigateAction("https://example.com")
result = navigate.execute(browser)

# Extract data from the page
extract = ExtractAction({
    "title": "h1",
    "paragraphs": "p"
})
data = extract.execute(browser)

print(f"Page title: {data['title']}")
print(f"Found {len(data['paragraphs'])} paragraphs")

# Clean up
browser.close()
```

### Example 3: LLM Integration

```python
from lamia.adapters.llm import OpenAIAdapter
from lamia.actions.llm import ChatAction

# Initialize LLM adapter
llm = OpenAIAdapter(api_key="your-api-key")

# Create a chat action
chat = ChatAction(
    prompt="Explain what Python decorators are in simple terms",
    model="gpt-3.5-turbo"
)

# Execute the action
response = chat.execute(llm)
print(response.content)
```

## Using the CLI

Lamia provides a powerful command-line interface for automation workflows.

### 1. Create a Workflow File

Create a `hello_world.hu` file:

```yaml
name: "Hello World Workflow"
description: "A simple example workflow"

steps:
  - name: "validate_data"
    action: "validate"
    params:
      data:
        message: "Hello, World!"
        timestamp: "2024-01-01T00:00:00Z"
      validator:
        type: "json"
        schema:
          type: "object"
          properties:
            message: 
              type: "string"
            timestamp:
              type: "string"
              format: "date-time"
          required: ["message", "timestamp"]

  - name: "output_result"
    action: "log"
    params:
      message: "Validation completed successfully!"
```

### 2. Run the Workflow

```bash
lamia run hello_world.hu --config config.yaml
```

## File Operations

### Reading and Writing Files

```python
from lamia.adapters.filesystem import LocalFSAdapter
from lamia.actions.file import ReadAction, WriteAction

# Initialize filesystem adapter
fs = LocalFSAdapter()

# Write a file
write_action = WriteAction(
    path="output.txt",
    content="Hello from Lamia!"
)
write_action.execute(fs)

# Read the file back
read_action = ReadAction(path="output.txt")
content = read_action.execute(fs)
print(content)
```

### Working with Cloud Storage

```python
from lamia.adapters.filesystem import S3Adapter
from lamia.actions.file import UploadAction

# Initialize S3 adapter
s3 = S3Adapter(
    bucket="my-bucket",
    region="us-east-1"
)

# Upload a file
upload = UploadAction(
    local_path="local_file.txt",
    remote_path="uploads/remote_file.txt"
)
upload.execute(s3)
```

## Advanced Features

### Custom Validators

```python
from lamia.validation.base import BaseValidator
from lamia.validation.result_types import ValidationResult

class EmailValidator(BaseValidator):
    def validate(self, value):
        if "@" in value and "." in value:
            return ValidationResult(is_valid=True)
        else:
            return ValidationResult(
                is_valid=False,
                errors=["Invalid email format"]
            )

# Use custom validator
email_validator = EmailValidator()
result = email_validator.validate("test@example.com")
```

### Error Handling and Retries

```python
from lamia.adapters.retry import RetryAdapter
from lamia.actions.http import HTTPRequestAction

# Configure retry behavior
retry_adapter = RetryAdapter(
    max_attempts=3,
    backoff_strategy="exponential",
    base_delay=1.0
)

# Create HTTP action with retry
http_action = HTTPRequestAction(
    url="https://api.example.com/data",
    method="GET"
)

# Execute with automatic retries
result = retry_adapter.execute(http_action)
```

## Next Steps

Now that you've seen the basics, explore these areas:

- **[Configuration Guide](configuration.md)**: Learn about advanced configuration options
- **[User Guide](../user-guide/cli.md)**: Detailed guides for specific features
- **[API Reference](../reference/)**: Complete API documentation
- **[Examples](../examples/basic.md)**: More comprehensive examples

## Getting Help

- Check the [API Reference](../reference/) for detailed documentation
- Browse [Examples](../examples/basic.md) for more use cases
- Visit our [GitHub Issues](https://github.com/lamia-lang/lamia/issues) for support
- Read the [User Guide](../user-guide/cli.md) for in-depth tutorials