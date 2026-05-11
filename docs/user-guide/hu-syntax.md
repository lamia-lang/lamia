# .hu File Syntax

`.hu` (human) files are plain-text prompt templates. They contain just the text you want to send to an LLM, with optional parameter placeholders and file-context references.

Each `.hu` file is automatically a callable function whose name matches the filename. You call `.hu` functions from `.lm` files -- `.lm` files are the orchestration layer that ties everything together.

## Quick example

**summarize.hu**
```
Summarize the following article: {@article_path}
Focus on {aspect} and keep it under {max_words} words.
```

**pipeline.lm**
```python
result = summarize(article_path="article.txt", aspect="key findings", max_words=200) -> HTML
print(result)
```

Run with:
```bash
lamia pipeline.lm
```

## Parameter placeholders

Use `{name}` to define parameters. They are auto-detected -- no declaration needed.

```
Write a {tone} email to {recipient} about {topic}.
```

Defaults are inline with `:`:

```
Write a {tone:friendly} email to {recipient} about {topic:today's update}.
```

Call with keyword arguments; override only what you need:

```python
email = draft_email(recipient="the team")
# tone -> "friendly", topic -> "today's update"
email = draft_email(recipient="the team", tone="formal", topic="Q3 results")
```

`{name:None}` means "optional, empty when omitted".

Only missing required parameters raise an error:
```
draft_email() missing required keyword arguments: recipient
```

To include a literal brace in the text, double it:
```
The result is in the format {{key: value}}.
```

## File context references

Use `{@filename}` to inject the contents of a local file into the prompt. The file is resolved by exact name matching. If same filename exists in multiple directories, the error message will suggest the minimal path suffix to disambiguate. If file does not exist, an error will be raised and files with similar name will be suggested in case user forgot the corrent filename.

```
Review the code in {@main.py} and suggest improvements.
Also check {@utils.py} for any issues.
```

### Variable file references

Use `{@identifier}` where the identifier matches a kwarg name. If the caller provides the file path as an argument -- **no `files()` context needed**:

**analyze.hu**
```
Analyze the document: {@doc_path}
Focus on: {aspect}
```

If no kwarg matches the identifier, it is treated as a literal filename.

### Literal file names

**caller.lm**
```python
# Absolute path -- resolves directly
result = analyze(doc_path="/Users/me/report.pdf", aspect="financials") -> JSON

# Relative path -- resolves relative to the .hu file location
result = analyze(doc_path="./data/report.pdf", aspect="financials") -> JSON

# Bare filename -- resolves relative to the .hu file location
result = analyze(doc_path="report.pdf", aspect="financials") -> JSON
```

### When to use `files()` vs variable paths

- **`files("~/Documents/", "~/projects/")`** -- use when you want directory-based discovery: "search for files across these folders"
- **`{@doc_path}` with kwarg** -- use when you have a specific file to pass: "use this exact file"

Passing a single file to `files()` is an anti-pattern. Instead, pass the file path without files() syntax:

```python
# Anti-pattern:
with files("~/Documents/resume.pdf"):
    result = extract(aspect="skills") -> JSON

# Better:
result = extract(doc_path="~/Documents/resume.pdf", aspect="skills") -> JSON
```

See the [File Context](files-context.md) documentation for details on directory-based resolution and error handling.

## Return types

`.hu` files are **return-type agnostic**. The return type is specified by the caller in the `.lm` file using the `->` syntax:

```python
# Returns validated HTML
page = generate_landing_page(product="Lamia") -> HTML

# Returns a Pydantic model extracted from HTML
quote = get_stock_data(ticker="AAPL") -> HTML[StockQuote]

# Writes output to a file
generate_docs(project="lamia") -> File(Markdown, "docs.md")
```

If called without a return type, the raw LLM response text is returned.

## Calling conventions

- `.hu` functions are called from `.lm` files like regular functions
- All parameters must be keyword arguments
- `.hu` files **cannot** call other `.hu` files -- use `.lm` files as the glue
- Filename (without `.hu` extension) must be unique across the project

## Standalone execution

You can run a `.hu` file directly from the CLI:

```bash
lamia hello.hu
```

This sends the prompt (with no parameters) to the default model and prints the response. Parameterized `.hu` files require a `.lm` wrapper to pass arguments.

## Comparison with .lm files

| Feature | `.hu` files | `.lm` files |
|---------|------------|-------------|
| Content | Plain text prompt | Python + Lamia syntax |
| Parameters | `{name}`, `{@name}` file refs | Python function arguments |
| Return type | Set by caller | Declared with `-> Type` |
| Python code | Not supported | Full Python support |
| Imports | Not needed | Implicit Lamia imports |
| Can call `.hu` | No | Yes |
| Can call `.lm` | No | Yes |
| Filename = function | Yes | No (uses `def` names) |