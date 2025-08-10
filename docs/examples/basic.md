# Basic Examples

This section contains basic examples of using Lamia for common automation tasks.

## Simple Validation Example

```python
from lamia.validation import validate
from lamia.validation.validators import JSONValidator

# Data to validate
data = {
    "name": "John Doe",
    "age": 30,
    "email": "john@example.com"
}

# JSON schema
schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer", "minimum": 0},
        "email": {"type": "string", "format": "email"}
    },
    "required": ["name", "age", "email"]
}

# Validate
validator = JSONValidator(schema)
result = validate(data, validator)

if result.is_valid:
    print("✅ Data is valid!")
else:
    print(f"❌ Validation errors: {result.errors}")
```

## File Operations Example

```python
from lamia.adapters.filesystem import LocalFSAdapter
from lamia.actions.file import ReadAction, WriteAction

# Initialize filesystem adapter
fs = LocalFSAdapter()

# Write a file
write_action = WriteAction(
    path="example.txt",
    content="Hello from Lamia!"
)
write_action.execute(fs)

# Read the file
read_action = ReadAction(path="example.txt")
content = read_action.execute(fs)
print(f"File content: {content}")
```

## HTTP Request Example

```python
from lamia.adapters.http import HTTPAdapter
from lamia.actions.http import HTTPRequestAction

# Initialize HTTP adapter
http = HTTPAdapter()

# Make a GET request
request_action = HTTPRequestAction(
    url="https://jsonplaceholder.typicode.com/posts/1",
    method="GET"
)

response = request_action.execute(http)
print(f"Response: {response.json()}")
```

## Basic Workflow File

Create a file called `basic-workflow.hu`:

```yaml
name: "Basic Example Workflow"
description: "Demonstrates basic Lamia functionality"

variables:
  message: "Hello, World!"
  output_file: "output.txt"

steps:
  - name: "validate_message"
    action: "validate"
    params:
      data: "${message}"
      validator:
        type: "string"
        min_length: 1

  - name: "write_file"
    action: "file.write"
    params:
      path: "${output_file}"
      content: "${message}"

  - name: "read_file"
    action: "file.read"
    params:
      path: "${output_file}"

  - name: "log_result"
    action: "log"
    params:
      message: "File content: ${read_file.result}"
```

Run it with:

```bash
lamia run basic-workflow.hu
```

## More Examples

Check out these additional examples:

- [Custom Validators](custom-validators.md)
- [Web Automation Examples](../user-guide/web-automation.md)
- [LLM Integration Examples](../user-guide/llm-integration.md)