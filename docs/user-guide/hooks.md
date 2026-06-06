# Hooks

Hooks are `.lm` functions that post-process LLM responses before validation runs. They let you write deterministic transformations — character cleanup, stripping unwanted patterns, reformatting — without touching each function individually.

## Quick start

Create a file anywhere in your project (e.g. `hooks.lm`) with a hook function:

```python
def normalize_chars(content) -> Hook(post_llm):
    return (content
        .replace('\u2014', '-')
        .replace('\u2013', '-')
        .replace('\u201c', '"')
        .replace('\u201d', '"')
    )
```

That's it. Every LLM response in your project will pass through `normalize_chars` before validation.

## How it works

1. Lamia discovers all `.lm` files in your project directory
2. Functions with `-> Hook(event, ...)` return annotations are registered as hooks
3. After an LLM generates a response (and before the validator checks it), matching hooks run in order
4. Each hook receives the response string and returns a transformed string

```
LLM response → hook chain → validator → result
```

Hooks run **before** validation. This is intentional — if your LLM returns em-dashes but your validator rejects non-ASCII, the hook fixes it before the validator sees it.

## The contract

A `post_llm` hook is a function that takes a string and returns a string:

```python
def my_hook(content) -> Hook(post_llm):
    # content is the raw LLM response text
    # return the transformed text
    return content.replace('—', '-')
```

If a hook raises an exception or returns a non-string value, it is skipped and the original content passes through unchanged.

## Filtering hooks

### By return type

Only run this hook when the function's return type matches:

```python
def strip_fences(content) -> Hook(post_llm, JSON):
    """Only runs for -> JSON functions. Strips markdown code fences."""
    if content.startswith('```'):
        lines = content.split('\n')
        return '\n'.join(lines[1:-1])
    return content

def strip_headers(content) -> Hook(post_llm, TEXT):
    """Only runs for -> TEXT functions."""
    return '\n'.join(
        line.lstrip('#').strip() if line.startswith('#') else line
        for line in content.split('\n')
    )
```

### By function name

Only run when a specific function (or glob pattern) produced the LLM call:

```python
def pinterest_cleanup(content) -> Hook(post_llm, function='generate_description'):
    """Only runs for the generate_description function."""
    return content.replace('#', '').strip()

def all_generators(content) -> Hook(post_llm, function='generate_*'):
    """Runs for any function matching generate_*."""
    return content.strip()
```

### Combining filters

```python
def csv_cleanup(content) -> Hook(post_llm, CSV, function='log_*'):
    """Only for CSV-returning functions named log_*."""
    return content.strip() + '\n'
```

## Multiple hooks

If multiple hooks match, they run in discovery order (file system order). Each hook receives the output of the previous one:

```python
def step_one(content) -> Hook(post_llm):
    return content.strip()

def step_two(content) -> Hook(post_llm):
    return content.replace('—', '-')
```

Result: `strip()` runs first, then dash replacement.

## Project layout

Hooks are discovered from **any `.lm` file** in the project. Common patterns:

```
my_project/
├── config.yaml
├── main.lm           # your main script
├── hooks.lm          # project-wide hooks
└── helpers/
    └── cleanup.lm    # more hooks (also discovered)
```

Hidden directories (`.git`, `.venv`, etc.) and `node_modules` are skipped.

## When to use hooks vs inline code

| Approach | Use when |
|----------|----------|
| Hook | The fix applies broadly (all LLM responses, or all of a type) |
| Hook with `function=` | You need to transform one function's LLM output but can't do it inline (because it happens between LLM response and validation) |
| Inline Python | The fix is specific to one function's result and happens after validation (e.g. post-processing a validated object) |

The `function=` parameter exists because `post_llm` hooks sit between the LLM response and the validator — there is no other way to inject logic at that point. If you need to strip markdown fences from JSON before the JSON validator sees it, a hook with `function='my_json_func'` is the only option.

## Error handling

Hooks are fail-safe:

- If a hook **raises an exception**, it is logged as a warning and skipped. The content passes through unchanged to the validator.
- If a hook **returns a non-string value**, it is logged and skipped.
- In both cases, the script continues normally — the validator will see the original LLM response.

Check your script output or logs for `WARNING` lines mentioning hook names to diagnose broken hooks.

## Validation boundary (important)

`post_llm` hooks run **before** validation. This means:

- Hook input is raw model output (`str`), not validated JSON/YAML/CSV/etc.
- For typed hooks (for example `Hook(post_llm, JSON)`), the content may still be invalid for that type.
- If you need logic that depends on validated typed data, do it in normal function code after validation, not in a hook.

Pattern for typed pre-validation hooks:

```python
def strip_json_fences(content) -> Hook(post_llm, JSON):
    # pre-validation cleanup only
    if content.startswith("```"):
        lines = content.split("\n")
        return "\n".join(lines[1:-1])
    return content
```

If you perform extra parsing inside a hook and parsing fails, prefer returning original content instead of raising. The validator will then produce the retry signal.

## Retries, ordering, and idempotency

Hook execution follows normal LLM retry flow:

- Hook runs on every LLM attempt (attempt 1, attempt 2, ...).
- If hook logic raises, Lamia logs and skips that hook for that attempt; execution continues.
- Retries are triggered by validation failure, not by hook exceptions themselves.

Because a hook may run multiple times, write hooks to be idempotent and side-effect free:

- Prefer pure text transforms (`str -> str`).
- Avoid external side effects (network calls, file writes, counters).
- Keep transformations stable when applied repeatedly (for example, replacing em-dash with `-` is idempotent).

## Do and don't

- **Do** keep hooks small, deterministic, and focused on cleanup before validation.
- **Do** use `function=` filter when only one generator needs the transform.
- **Do** return original content when optional internal parsing fails.
- **Don't** assume content is already valid typed data inside hooks.
- **Don't** raise intentionally for validation control; let validators decide validity/retries.
- **Don't** put business-side effects into hooks.

## Extensibility

The hook event system is extensible. Currently only `post_llm` is supported. Future events will each have their own typed contract designed per-event (not a generic payload).

Custom events can be registered for advanced use cases:

```python
from lamia.hooks import HookEvent
MY_EVENT = HookEvent.register("my_custom_event")
```
