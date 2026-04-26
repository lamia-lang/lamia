# Lamia Debugger

Lamia includes a built-in debugger for `.lm` files:

```bash
lamia debug path/to/file.lm
```

This page covers both interactive terminal debugging and IDE integration.

## CLI Usage

### Basic command

```bash
lamia debug orchestrator.lm
```

### Options

- `--break`, `-b <line>`: Set one or more breakpoints before execution starts.
- `--stop-on-entry`: Pause on the first executable line.
- `--json`: Machine-readable mode used by IDE integrations.

Examples:

```bash
# Run until line 51
lamia debug orchestrator.lm --break 51

# Pause immediately, then step manually
lamia debug orchestrator.lm --stop-on-entry

# Multiple breakpoints
lamia debug orchestrator.lm --break 51 --break 87
```

## Interactive Commands

When running `lamia debug` in terminal mode, use:

- `continue` / `c`: Resume execution
- `next` / `n`: Step over
- `step` / `s`: Step into
- `stepout` / `out`: Step out
- `break <line>` / `b <line>`: Add a breakpoint
- `break`: List breakpoints
- `print <expr>` / `p <expr>`: Evaluate expression
- `locals` / `l`: Show local variables
- `backtrace` / `bt`: Show call stack
- `quit` / `q`: Stop debugging
- `help` / `h`: Show help

## Config Discovery

If `--config` is not provided, Lamia automatically searches for `config.yaml` or `config.yml` by walking up parent directories from the target file path.

This means debugging works from nested folders without manually changing directories.

If no config file is found, Lamia shows an error with the search starting point and how to fix it.

## Variable Inspection

The debugger supports structured variable inspection for:

- lists / tuples / sets
- dictionaries
- Pydantic models (via `model_dump()` when available)
- regular Python objects (`vars(...)`)

In IDE debug views, expandable values appear as tree nodes so nested items can be inspected individually.

## IDE Integration Notes

The IDE integration uses:

- `lamia debug <file> --json` as the debug runtime process
- a JSON-lines protocol for debugger commands/events
- source-map aware line mapping from transformed Python back to original `.lm` lines

Breakpoints can be passed at process start and are also synchronized after initialization for robust startup behavior.

