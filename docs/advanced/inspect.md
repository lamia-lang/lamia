# Inspect and Lint

`lamia inspect` analyzes `.lm` and `.hu` files for syntax errors, semantic issues, and style violations. It powers IDE diagnostics (Lamia IDE extension) and can be run standalone for CI or manual checks.

## Usage

```bash
lamia inspect script.lm
lamia inspect script.lm --json
lamia inspect *.lm
```

Single file output:

```
daily_report.lm: executable
  steps at lines: [3, 7, 12]
  warning: line 5: [LMW005] 2 line(s) use tab indentation
  error: line 9: [LME020] web.click() called without a selector
```

Batch mode (`lamia inspect *.lm`) reports each file with its status and diagnostics.

### JSON output

Use `--json` for machine-readable output (IDE integration, CI pipelines):

```bash
lamia inspect script.lm --json
```

```json
{
  "executable": true,
  "steps": [3, 7, 12],
  "diagnostics": [
    {
      "severity": "warning",
      "message": "[LMW005] 2 line(s) use tab indentation",
      "line": 5,
      "col": 0,
      "source": "lamia-lint"
    }
  ]
}
```

Batch JSON returns `{"results": {"path": {...}, ...}}`.

## What inspect checks

Inspect runs three analysis passes:

1. **Syntax** -- Parses via the Lamia parser pipeline, reports syntax errors with line numbers mapped back to the original source.
2. **Semantic** -- Validates function calls against `.hu` definitions, flags duplicate functions, checks cross-file name collisions, validates inline template placeholders.
3. **Lint** -- Applies all lint rules (listed below) for style, conventions, and common mistakes.

## Executable vs definitions-only

Inspect reports whether a file has top-level executable statements (steps) or only contains definitions and imports. This distinction matters for IDE run buttons and scheduling -- a file with no steps has nothing to execute on its own.

---

## Lint Rules

Lamia has two linters: one for `.lm` files and one for `.hu` files. Each rule has a code, severity, and description.

Severities:

| Level | Meaning |
|-------|---------|
| **Error (E)** | Must fix. The script will fail or produce wrong results. |
| **Warning (W)** | Should fix. Likely a bug or bad practice. |
| **Convention (C)** | Style convention. Follow unless you have a reason not to. |
| **Refactor (R)** | Structural suggestion. Consider for maintainability. |

### .lm rules

`.lm` files are Python + Lamia syntax. The linter enforces PEP 8 basics plus Lamia-specific patterns.

#### Errors

| Code | Name | Description |
|------|------|-------------|
| LME002 | missing-required-params | `.hu` call is missing required parameters. Every required parameter in the `.hu` file must be passed as a keyword argument. |
| LME014 | unknown-hu-kwargs | `.hu` call passes keyword arguments that the `.hu` file does not accept. Check parameter names against the `.hu` definition. |
| LME016 | unknown-namespace | Uses a namespace that is not part of Lamia. Valid namespaces: `web`, `http`, `file`, `db`, `email`. |
| LME017 | unknown-namespace-method | Calls a method that does not exist on a Lamia namespace. Check available methods with `lamia inspect --json`. |
| LME020 | global-web-no-selector | `web.action()` called without a selector on the global `web` object. Provide a selector: `web.click("button.submit")`. |

#### Warnings

| Code | Name | Description |
|------|------|-------------|
| LMW001 | excessive-growth | Content grew more than 2x the original file size. Make minimal, targeted changes. |
| LMW005 | tab-indentation | Use 4 spaces for indentation, not tabs (PEP 8). |
| LMW006 | positional-hu-args | `.hu` calls must use keyword arguments. Positional arguments are not allowed. |
| LMW007 | empty-file | `.lm` file has no meaningful content. |
| LMW008 | trailing-whitespace | Lines have trailing whitespace. |
| LMW018 | single-file-in-files-ctx | `files()` with a single file path is an anti-pattern. `files()` is for directory-based discovery; pass the file path directly as a kwarg to the `.hu` function instead. |
| LMW019 | prefer-atomic-web-action | Prefer `web.click("selector")` over `el = web.get_element("selector")` followed by `el.click()` when the variable is only used once. Atomic calls are more readable and less error-prone. |
| LMW024 | session-no-target-url | `session("name")` without a target URL. Adding a target URL enables reliable session-skip detection: `session("name", "https://...")`. |

#### Convention

| Code | Name | Description |
|------|------|-------------|
| LMC009 | variable-naming | Variables should use `snake_case` (PEP 8). PascalCase is reserved for Pydantic model classes. |
| LMC010 | filename-naming | `.lm` filenames should be `snake_case` (e.g. `daily_report.lm`, not `DailyReport.lm`). |
| LMC011 | leading-blank-lines | File starts with blank lines. Code should begin on line 1. |
| LMC015 | generic-filename | Generic names like `process.lm`, `main.lm`, `task.lm` say nothing about what the script does. Use a descriptive name. |

#### Refactor

| Code | Name | Description |
|------|------|-------------|
| LMR003 | output-format-hint | Don't embed output schema in comments or strings. Define a Pydantic model and use `-> Type[Model]` return type annotation. |
| LMR012 | inline-pydantic-model | More than 2 Pydantic models defined inline in a single `.lm` file. For larger projects, extract shared models to a `models/` directory. |
| LMR013 | long-script | Script exceeds 5000 characters. Consider splitting into focused sub-scripts or moving orchestration to separate pipeline `.lm` files. |

### .hu rules

`.hu` files are plain-text prompt templates. The linter enforces plain-text purity and parameter conventions.

#### Errors

| Code | Name | Description |
|------|------|-------------|
| HUE001 | yaml-front-matter | YAML front matter (`---...---`) is not valid in `.hu` files. `.hu` files are plain text, not markdown. |
| HUE019 | escaped-param | `{{param}}` escapes the braces, making it a literal string, but an `.lm` caller passes `param=` as an argument. Use `{param}` instead. |

#### Warnings

| Code | Name | Description |
|------|------|-------------|
| HUW002 | markdown-header | `# headings` are markdown formatting. `.hu` files are plain text. |
| HUW003 | markdown-bold | `**bold**` or `__bold__` is markdown formatting. |
| HUW004 | markdown-italic | `*italic*` or `_italic_` is markdown formatting. |
| HUW005 | markdown-strikethrough | `~~strike~~` is markdown formatting. |
| HUW006 | markdown-link | `[text](url)` is markdown formatting. Use plain URLs. |
| HUW007 | markdown-image | `![alt](url)` is not useful in prompt templates. |
| HUW008 | markdown-code-fence | Code fences (`` ``` ``) are markdown formatting. |
| HUW009 | markdown-blockquote | `> quotes` are markdown formatting. |
| HUW010 | markdown-table | Pipe tables (`| col | col |`) are markdown formatting. |
| HUW011 | markdown-horizontal-rule | `---` / `***` / `___` are markdown formatting. |
| HUW012 | html-tag | HTML tags don't belong in prompt templates. |
| HUW013 | emoji | Emojis are decorative noise. `.hu` files should be clean text. |
| HUW014 | markdown-inline-code | Inline code (`` `code` ``) is markdown formatting. |
| HUW015 | markdown-task-list | `- [ ]` / `- [x]` task lists are markdown formatting. |
| HUW016 | excessive-growth | Content grew more than 2x the original file size. |
| HUW017 | too-many-params | More than 10 `{param}` placeholders. Consider using `{@file}` references to include large content. |
| HUW021 | empty-file | `.hu` file has no meaningful content. |
| HUW022 | trailing-whitespace | Lines have trailing whitespace. |
| HUW029 | example-output-block | Embedded example outputs (JSON objects, YAML blocks, XML fragments) belong in Lamia types, not in the prompt. Use `-> Type[Model]` on the call site. |

#### Convention

| Code | Name | Description |
|------|------|-------------|
| HUC020 | param-naming | Parameters should use `snake_case` (e.g. `{user_name}`, not `{userName}`). |
| HUC023 | short-param-name | Single-character parameter names are unclear. Use descriptive names. |
| HUC024 | verbose-param-name | Parameter name exceeds 30 characters. Consider a shorter name. |
| HUC025 | filename-naming | `.hu` filenames should be `snake_case`. The filename becomes the callable function name. |
| HUC026 | leading-blank-lines | File starts with blank lines. Content should begin on line 1. |
| HUC028 | generic-filename | Generic names like `agent.hu`, `prompt.hu`, `template.hu` say nothing. Use a role-based name (`reviewer.hu`) or action-based name (`summarize.hu`). |

#### Refactor

| Code | Name | Description |
|------|------|-------------|
| HUR018 | output-format-hint | Don't embed output format instructions in the prompt. Lamia handles output format validation via `-> Type[Model]` on the call site. |
| HUR027 | long-prompt | Prompt exceeds 3000 characters. Consider splitting into focused sub-prompts or moving large content to `{@file}` references. |

## CI integration

Run inspect as a CI step to catch issues before deployment:

```yaml
- run: lamia inspect **/*.lm --json
```

Non-zero exit code on syntax errors makes it usable as a gate.

## IDE integration

The Lamia IDE extension calls `lamia inspect <file> --json` on save and maps diagnostics to editor squiggles. No configuration needed -- the extension discovers `lamia` from `PATH` or the active virtual environment.
