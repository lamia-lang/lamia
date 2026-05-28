# File Operations

Lamia provides a `file` namespace for direct filesystem operations: reading, writing, and appending files programmatically without involving an LLM.

## Overview

```python
# Read a file
content = file.read("./config.json")

# Write to a file
file.write("./output.txt", "Hello, World!")

# Append to a file
file.append("./log.txt", "New entry\n")
```

## API

### `file.read(path, encoding="utf-8")`

Read file contents and return as a string.

```python
content = file.read("./data.csv")
settings = file.read("./config.yaml", encoding="utf-8")
legacy = file.read("./old_data.txt", encoding="latin-1")
```

**Parameters:**

| Parameter  | Type  | Default   | Description              |
|-----------|-------|-----------|--------------------------|
| `path`    | str   | required  | File path to read        |
| `encoding`| str   | `"utf-8"` | File encoding            |

**Returns:** File content as a string.

### `file.write(path, content, encoding="utf-8")`

Write content to a file. Creates the file if it doesn't exist, overwrites if it does.

```python
file.write("./output.txt", "Hello, World!")
file.write("./data.json", json.dumps({"key": "value"}))
file.write("./legacy.csv", csv_content, encoding="latin-1")
```

**Parameters:**

| Parameter  | Type  | Default   | Description              |
|-----------|-------|-----------|--------------------------|
| `path`    | str   | required  | File path to write       |
| `content` | str   | required  | Content to write         |
| `encoding`| str   | `"utf-8"` | File encoding            |

### `file.append(path, content, encoding="utf-8")`

Append content to an existing file. Creates the file if it doesn't exist.

```python
file.append("./log.txt", f"[{timestamp}] Event occurred\n")
file.append("./results.csv", "new_row,data,here\n")
```

**Parameters:**

| Parameter  | Type  | Default   | Description              |
|-----------|-------|-----------|--------------------------|
| `path`    | str   | required  | File path to append to   |
| `content` | str   | required  | Content to append        |
| `encoding`| str   | `"utf-8"` | File encoding            |

## Comparison with Other File Mechanisms

Lamia has three ways to work with files, each for a different purpose:

| Mechanism | Purpose | Example |
|-----------|---------|---------|
| `file.read/write/append` | Direct filesystem I/O | `file.write("out.txt", data)` |
| `-> File(...)` | LLM-generated content saved to disk | `def report() -> File(HTML, "report.html")` |
| `with files(...)` | Inject file content into LLM prompts | `{@resume.pdf}` |

### When to use `file.*`

Use `file.read()`, `file.write()`, `file.append()` when you have content already and want to perform straightforward filesystem operations — no LLM involved.

```python
# Read a queue, modify it, write it back
content = file.read("./queue.txt")
lines = content.strip().split('\n')
lines.append("new_item")
file.write("./queue.txt", '\n'.join(lines) + '\n')
```

### When to use `-> File(...)`

Use `-> File(Type, path)` when you want the LLM to **generate** content and save it directly to a file with optional type validation.

```python
def generate_report() -> File(HTML, "report.html"):
    "Create a quarterly sales report"
```

### When to use `with files(...)`

Use `with files(...)` when you want to **inject file content into LLM prompts** via `{@filename}` syntax.

```python
with files("~/Documents/"):
    def summarize():
        "Summarize {@report.pdf}"
```

## Reading Files with Type Conversion

To read a file and parse it into a typed Python object, use the `-> Type` syntax:

```python
data = "./config.json" -> JSON       # Returns a dict
config = "./settings.yaml" -> YAML   # Returns a dict
```

This is different from `file.read()` which always returns a raw string.
