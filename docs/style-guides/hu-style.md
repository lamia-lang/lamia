# LSG-1: .hu File Style Guide

This guide defines conventions for writing `.hu` (human prompt template) files.
`.hu` files are the interface between humans and LLMs in Lamia projects --
clean, focused prompts that produce reliable results.

## Core principle

`.hu` files are **plain text**. No markdown, no HTML, no YAML front matter, no emojis.
The LLM consumes the raw text; visual formatting adds noise without value.

## File structure

A well-structured `.hu` file follows this order:

1. **Role / context** -- who the LLM should act as and what it knows
2. **Task** -- what to do, stated directly (no fluff)
3. **Input parameters** -- parameters and file references
4. **Constraints** -- boundaries, tone, length limits (Note that output constraints should be specified in the -> Type[Model] Model's contraints with Pydantic syntax if possible)

```
You are a senior code reviewer specializing in {language}.

Review the following code and identify bugs, security issues,
and style violations. Be concise.

Limit your response to the {max_findings:10} most critical issues.

Code to review:
{@source_file}
```

Avoid burying the task deep in the prompt. Lead with context, then
state the task clearly.

## Parameter naming

Use `snake_case` for all parameter names:

```
Good:  {user_name}  {max_retries}  {output_format}
Bad:   {userName}   {MaxRetries}   {OutputFormat}
```

Keep names descriptive but not verbose:

```
Good:  {prd_content}  {review_criteria}
Bad:   {the_product_requirements_document_content}
Bad:   {x}  {data}  {input}
```

### Defaults

Use defaults for parameters that have a meaningful fallback value but never for values that must be filled by the caller:

```
Write a {tone:professional} email to {recipient} about {topic}.
Keep it under {max_words:200} words.
```

Use `{param:None}` for truly optional parameters that should be empty
when omitted, not for parameters that need a fallback value. When the parameter is not provided, an empty string will be used as the value.

## File context references

Use `{@filepath}` to inject file contents. Prefer this over large
inline parameters:

```
Good:
  Review the code in {@main.py} and suggest improvements.

Bad:
  Review the following code and suggest improvements:
  {source_code_that_is_500_lines_long}
```

When a `.hu` file needs more than 10 parameters, it is a sign that
content should be moved to separate `.hu` files and orchestrated from a `.lm` file.

### Variable file references

When the file to include depends on the caller, name the parameter
clearly:

```
Analyze the test results in {@test_report}.
Compare against the baseline in {@baseline_report}.
```

The caller provides the paths:
```python
analyze(test_report="results/latest.json", baseline_report="results/v1.json")
```

## Return types

`.hu` files are **return-type agnostic**. Never embed output format
instructions in the prompt:

```
Bad:
  Output JSON:
  {
    "summary": "...",
    "score": 0
  }

Good:
  (no format instructions -- the caller specifies -> JSON[Model])
```

Lamia validates output format and structure at the call site using
`-> Type[Model]`. Currently supported types: JSON, HTML, YAML, XML, CSV, Markdown.
The caller declares the return type, and Lamia handles validation
and extraction automatically:

```python
result = review_code(language="python") -> JSON[ReviewResult] # where review_code is the `.hu` file name
```

## Character Escaping

When the prompt text itself needs curly braces (e.g., showing JSON
examples to the LLM), double them:

```
The config file uses this format: {{key: value}}.
```

## What not to include

| Anti-pattern | Why | Rule |
|---|---|---|
| `# Heading` | Markdown formatting | HUW002 |
| `**bold**` | Markdown formatting | HUW003 |
| `` `code` `` | Markdown formatting | HUW014 |
| `---` front matter | Not valid in .hu | HUE001 |
| HTML tags | Not appropriate | HUW012 |
| Emojis | Decorative noise | HUW013 |
| Output JSON: {...} | Use -> Type[Model] | HUR018 |

## Naming the file

The filename (without `.hu`) becomes the callable function name.
Use `snake_case`:

### Verb-based Naming Conventions:

```
Good:  review_code.hu  generate_report.hu  analyze_data.hu
Bad:   ReviewCode.hu   generate-report.hu  ANALYZE_DATA.hu
```

Keep names verb-first when the file performs an action:

```
Good:  summarize_article.hu  extract_entities.hu  draft_email.hu
Bad:   article_summary.hu    entity_extraction.hu  email_draft.hu
```

### Noun-based Naming Conventions:

```
Good:  groomer.hu  .hu  product_manager.hu
Bad:   Groomer.hu   Product-manager.hu
```
