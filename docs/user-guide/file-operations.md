# File Operations

Lamia provides a `file` namespace for direct filesystem operations: reading, writing, appending, checking existence, and finding files by pattern — all without involving an LLM.

## Overview

```python
# Find files by pattern
csv_files = file.glob("./data/*.csv")

# Check if a file exists
if file.exists("./config.json"):
    content = file.read("./config.json")

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

### `file.glob(pattern)`

Find files matching a glob pattern. Returns a sorted list of matching file paths.

```python
csv_files = file.glob("./data/*.csv")
all_configs = file.glob("./**/*.json")
logs = file.glob("/var/log/app-*.log")
```

**Parameters:**

| Parameter  | Type  | Default   | Description              |
|-----------|-------|-----------|--------------------------|
| `pattern` | str   | required  | Glob pattern (`*`, `**`, `?` supported) |

**Returns:** Sorted list of matching file paths (empty list if no matches).

**Pattern syntax:**
- `*` — matches any characters within a single directory
- `**` — matches across directories (recursive)
- `?` — matches a single character

### `file.exists(path)`

Check if a file exists. Returns `True` if the file exists, `False` otherwise.

```python
if file.exists("./data.csv"):
    data = file.read("./data.csv")
else:
    file.write("./data.csv", "header1,header2\n")
```

**Parameters:**

| Parameter  | Type  | Default   | Description              |
|-----------|-------|-----------|--------------------------|
| `path`    | str   | required  | File path to check       |

**Returns:** `True` if the file exists, `False` otherwise.

## Patterns

### Batch file processing

Use `file.glob()` to find and process multiple files at once:

```python
# Process all CSV files in a directory
for path in file.glob("./reports/*.csv"):
    content = file.read(path)
    # process each file...

# Find all JSON configs recursively
configs = file.glob("./**/*.json")

# Check if any matching files exist
if file.glob("./inbox/*.txt"):
    # process inbox...
```

### Conditional file operations

Use `file.exists()` to branch logic based on whether a file is already present:

```python
if file.exists("./output.csv"):
    file.append("./output.csv", f"{name},{score}\n")
else:
    file.write("./output.csv", "name,score\n")
    file.append("./output.csv", f"{name},{score}\n")
```

### CSV operations

```python
csv_path = "./results.csv"

# Initialize CSV with headers if it doesn't exist
if not file.exists(csv_path):
    file.write(csv_path, "timestamp,status,message\n")

# Append rows
file.append(csv_path, f"{timestamp},success,Completed\n")
```

### Safe config loading

```python
config_path = "./config.json"

if file.exists(config_path):
    raw = file.read(config_path)
    # parse and use config
else:
    # use defaults or create initial config
    file.write(config_path, '{"retries": 3}')
```

## Common Mistakes

**Do NOT use Python's built-in `open()` or `with open()`** — Lamia scripts use the `file.*` API:

```python
# ❌ NOT RECOMMENDED — Lamia syntax is preferred
with open("data.txt", "r") as f:
    content = f.read()

# ❌ NOT RECOMMENDED — Lamia syntax is preferred
try:
    content = file.read("data.txt")
except FileNotFoundError:
    content = ""

# ✅ CORRECT
if file.exists("data.txt"):
    content = file.read("data.txt")
else:
    content = ""

# ✅ CORRECT — simple read
content = file.read("data.txt")

# ✅ CORRECT — write
file.write("data.txt", "hello")
```

## Comparison with Other File Mechanisms

Lamia has three ways to work with files, each for a different purpose:

| Mechanism | Purpose | Example |
|-----------|---------|---------|
| `file.glob/exists/read/write/append` | Direct filesystem I/O | `file.write("out.txt", data)` |
| `-> File(...)` | LLM-generated content saved to disk | `def report() -> File(HTML, "report.html")` |
| `with files(...)` | Inject file content into LLM prompts | `{@resume.pdf}` |

### When to use `file.*`

Use `file.glob()`, `file.exists()`, `file.read()`, `file.write()`, `file.append()` when you have content already and want to perform straightforward filesystem operations — no LLM involved.

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
