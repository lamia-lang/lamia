"""Agentic tools for lamia interactive/json mode.

These tools are made available to the LLM via the system prompt so it can
request documentation, read project files, list directory contents, and
write files.  The tool-use loop is driven by the caller (json_mode or
interactive_mode) — this module only provides the tool definitions and
execution logic.
"""
import enum
import json
import fnmatch
import os
import logging
import re
import shutil
from pathlib import Path
from typing import Optional

from lamia.actions.http import HttpActions
from lamia.interpreter.commands import WebCommand, WebActionType
from lamia.interpreter.human.parser import parse_hu_file
from lamia.lint.find_usage import UsageReference, find_usage
from lamia.lint import HuLinter, LmLinter


MAX_READ_CHUNK_CHARS = 100_000


class ToolName(str, enum.Enum):
    GET_DOCS = "get_docs"
    READ_FILE = "read_file"
    LIST_FILES = "list_files"
    WRITE_FILE = "write_file"
    PATCH_FILE = "patch_file"
    DELETE_FILE = "delete_file"
    FIND_DEFINITION = "find_definition"
    FIND_REFERENCES = "find_references"
    COPY_FILE = "copy_file"
    MOVE_FILE = "move_file"
    GREP = "grep"
    GLOB = "glob"
    WEB_FETCH = "web_fetch"
    BROWSER_NAVIGATE = "browser_navigate"
    BROWSER_CLICK = "browser_click"
    BROWSER_TYPE = "browser_type"
    BROWSER_GET_TEXT = "browser_get_text"
    BROWSER_SCREENSHOT = "browser_screenshot"
    BROWSER_WAIT = "browser_wait"
    LINT_CODE = "lint_code"


class FileAction(enum.Enum):
    WRITE = "write"
    PATCH = "patch"
    DELETE = "delete"
    MOVE = "move"


FileReference = UsageReference

logger = logging.getLogger(__name__)

TOOL_LABELS: dict[str, tuple[str, str]] = {
    ToolName.GET_DOCS:           ("Reading docs",        "topic"),
    ToolName.READ_FILE:          ("Reading file",        "path"),
    ToolName.LIST_FILES:         ("Listing files",       "directory"),
    ToolName.WRITE_FILE:         ("Writing file",        "path"),
    ToolName.PATCH_FILE:         ("Editing file",        "path"),
    ToolName.DELETE_FILE:        ("Deleting file",       "path"),
    ToolName.COPY_FILE:          ("Copying",             "source"),
    ToolName.MOVE_FILE:          ("Moving",              "source"),
    ToolName.GREP:               ("Searching",           "pattern"),
    ToolName.GLOB:               ("Finding files",       "pattern"),
    ToolName.FIND_DEFINITION:    ("Finding definition",  "symbol"),
    ToolName.FIND_REFERENCES:    ("Finding references",  "symbol"),
    ToolName.WEB_FETCH:          ("Fetching page",       "url"),
    ToolName.BROWSER_NAVIGATE:   ("Navigating to",       "url"),
    ToolName.BROWSER_CLICK:      ("Clicking",            "selector"),
    ToolName.BROWSER_TYPE:       ("Typing into",         "selector"),
    ToolName.BROWSER_GET_TEXT:   ("Reading page text",   "selector"),
    ToolName.BROWSER_SCREENSHOT: ("Taking screenshot",   ""),
    ToolName.BROWSER_WAIT:       ("Waiting for",         "selector"),
    ToolName.LINT_CODE:          ("Linting code",        "file_type"),
}


def tool_progress_label(tool: str, args: dict) -> str:
    entry = TOOL_LABELS.get(tool)
    if not entry:
        return tool.replace("_", " ")
    verb, arg_key = entry
    detail = str(args.get(arg_key, "")) if arg_key else ""
    return f"{verb}: {detail}" if detail else verb

TOPIC_TO_FILE = {
    "lm-syntax": "user-guide/lm-syntax.md",
    ".lm": "user-guide/lm-syntax.md",
    "hu-syntax": "user-guide/hu-syntax.md",
    ".hu": "user-guide/hu-syntax.md",
    "files-context": "user-guide/files-context.md",
    "files": "user-guide/files-context.md",
    "configuration": "getting-started/configuration.md",
    "config.yaml": "getting-started/configuration.md",
    "installation": "getting-started/installation.md",
    "validation": "user-guide/validation.md",
    "web-automation": "user-guide/web-automation.md",
    "model-evaluation": "user-guide/evaluation.md",
    "selector": "validation/selector-usage-guide.md",
    "debugger": "advanced/debugger.md",
    "hu-style-guide": "style-guides/hu-style.md",
    "lm-style-guide": "style-guides/lm-style.md",
    "project-structure": "style-guides/project-structure.md",
    "getting-started": "getting-started/index.md",
    "lamia-as-python-library": "user-guide/python-library.md",
    "pydantic-models": "user-guide/pydantic-models.md",
    "custom-llm-adapters": "user-guide/custom-llm-adapters.md",
    "file-operations": "user-guide/file-operations.md",
    "file.read": "user-guide/file-operations.md",
    "file.write": "user-guide/file-operations.md",
    "file.append": "user-guide/file-operations.md",
}

_DOCS_TOPICS = ", ".join(sorted(set(TOPIC_TO_FILE.keys())))

_HU_FILE_HINT = (
    "IMPORTANT for .hu files: use PLAIN TEXT only (no markdown -- "
    "no **bold**, *italic*, # headers, `backticks`, or HTML), "
    "parameters use single braces {param}, NOT double {{param}} which makes them literals, "
    "do NOT include output structure information and example outputs (JSON, YAML, code blocks) -- "
    ".hu files are output agnostic and the caller specifies the return type."
)

TOOL_DEFINITIONS = [
    {
        "name": ToolName.GET_DOCS.value,
        "description": f"Retrieve Lamia language documentation by topic. Topics: {_DOCS_TOPICS}.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Documentation topic to retrieve",
                }
            },
            "required": ["topic"],
        },
    },
    {
        "name": ToolName.READ_FILE.value,
        "description": (
            f"Read the contents of a file. For large files (>{MAX_READ_CHUNK_CHARS} chars), "
            "returns a chunk and reports the total size. Use 'offset' to "
            "read subsequent chunks."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative file path to read",
                },
                "offset": {
                    "type": "integer",
                    "description": "Character offset to start reading from. Defaults to 0.",
                },
                "chunk_size": {
                    "type": "integer",
                    "description": f"Max characters to read. Defaults to and capped at {MAX_READ_CHUNK_CHARS}.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": ToolName.LIST_FILES.value,
        "description": "Recursively list files and subdirectories (up to 4 levels deep).",
        "parameters": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory path to list (default: current directory)",
                }
            },
        },
    },
    {
        "name": ToolName.WRITE_FILE.value,
        "description": (
            "Create or overwrite a file with the given content. " + _HU_FILE_HINT
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to write to",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": ToolName.PATCH_FILE.value,
        "description": (
            "Edit an existing file by replacing old_text with new_text. "
            "Preferred over write_file for modifications -- only express the change, not the whole file. "
            + _HU_FILE_HINT
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to edit",
                },
                "old_text": {
                    "type": "string",
                    "description": "Exact text to find in the file (must match exactly)",
                },
                "new_text": {
                    "type": "string",
                    "description": "Replacement text",
                },
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": ToolName.DELETE_FILE.value,
        "description": "Delete a file at the given path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to delete",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": ToolName.FIND_DEFINITION.value,
        "description": (
            "Find where a function, class, or .hu file is defined. "
            "Returns file path and line number."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Name of the function, class, or .hu file to find",
                },
            },
            "required": ["symbol"],
        },
    },
    {
        "name": ToolName.FIND_REFERENCES.value,
        "description": (
            "Find all files that reference or call a given symbol. "
            "Returns file paths with line numbers and context."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Name of the function, class, or variable to search for",
                },
            },
            "required": ["symbol"],
        },
    },
    {
        "name": ToolName.COPY_FILE.value,
        "description": "Copy a file or directory to a new location. Works recursively for directories.",
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source file or directory path",
                },
                "destination": {
                    "type": "string",
                    "description": "Destination path",
                },
            },
            "required": ["source", "destination"],
        },
    },
    {
        "name": ToolName.MOVE_FILE.value,
        "description": "Move or rename a file or directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source file or directory path",
                },
                "destination": {
                    "type": "string",
                    "description": "Destination path",
                },
            },
            "required": ["source", "destination"],
        },
    },
    {
        "name": ToolName.GREP.value,
        "description": (
            "Search for a pattern in files. Returns matching lines with file paths and line numbers. "
            "Searches recursively in the given directory."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Text or regex pattern to search for",
                },
                "directory": {
                    "type": "string",
                    "description": "Directory to search in (default: current directory)",
                },
                "include": {
                    "type": "string",
                    "description": "Glob pattern to filter files (e.g. '*.py', '*.lm')",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": ToolName.GLOB.value,
        "description": "Find files matching a glob pattern. Returns file paths sorted by modification time.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g. '**/*.py', 'src/**/*.lm', '*.yaml')",
                },
                "directory": {
                    "type": "string",
                    "description": "Directory to search in (default: current directory)",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": ToolName.WEB_FETCH.value,
        "description": (
            "Fetch a web page via Lamia HTTP actions and return response content. "
            "Lightweight -- no browser required. Prefer this over browser tools when you only need page content."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to fetch",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": ToolName.BROWSER_NAVIGATE.value,
        "description": "Navigate to a URL in the browser. Returns the page title and visible text.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to navigate to",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": ToolName.BROWSER_CLICK.value,
        "description": "Click an element on the page. Use CSS selectors or natural language descriptions.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector, XPath, or natural language description (e.g. 'Sign in button')",
                },
            },
            "required": ["selector"],
        },
    },
    {
        "name": ToolName.BROWSER_TYPE.value,
        "description": "Type text into an input element.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector or description of the input field",
                },
                "text": {
                    "type": "string",
                    "description": "Text to type",
                },
            },
            "required": ["selector", "text"],
        },
    },
    {
        "name": ToolName.BROWSER_GET_TEXT.value,
        "description": "Get visible text content from the page or a specific element.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector to get text from (default: body — entire page)",
                },
            },
        },
    },
    {
        "name": ToolName.BROWSER_SCREENSHOT.value,
        "description": "Take a screenshot of the current page. Returns the file path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to save screenshot (default: screenshot.png in cwd)",
                },
            },
        },
    },
    {
        "name": ToolName.BROWSER_WAIT.value,
        "description": "Wait for an element to appear or become visible.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector or description to wait for",
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds (default: 10)",
                },
            },
            "required": ["selector"],
        },
    },
    {
        "name": ToolName.LINT_CODE.value,
        "description": (
            "Lint Lamia code without writing to disk. Use this to validate "
            ".lm or .hu code before presenting it. Returns lint violations "
            "and feedback. Fix any errors before showing the code to the user."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The code content to lint",
                },
                "file_type": {
                    "type": "string",
                    "description": '"lm" for Lamia scripts or "hu" for prompt templates',
                },
            },
            "required": ["content", "file_type"],
        },
    },
]

# Module-level accumulator for file writes during a single request.
# The caller (json_mode) calls reset_file_writes() before the tool loop
# and get_file_writes() after to include them in the response.
_file_writes: list = []


def reset_file_writes() -> None:
    """Clear tracked file writes (call before each request's tool loop)."""
    _file_writes.clear()


def get_file_writes() -> list:
    """Return a copy of file writes accumulated during the current request."""
    return list(_file_writes)


def _find_docs_dir() -> Optional[Path]:
    """Find the bundled docs/ directory shipped with the lamia package."""
    pkg_root = Path(__file__).resolve().parent.parent.parent
    docs_dir = pkg_root / "docs"
    if docs_dir.is_dir():
        return docs_dir

    src_root = Path(__file__).resolve().parent.parent.parent.parent
    docs_dir = src_root / "docs"
    if docs_dir.is_dir():
        return docs_dir

    return None


def execute_tool(name: str, args: dict, cwd: str = ".", lamia=None) -> tuple[str, bool]:
    """Execute a tool by name and return (result_text, success)."""
    result = _execute_tool(name, args, cwd, lamia)
    success = not (
        result.startswith("Error")
        or result.startswith("File not found")
        or result.startswith("Unknown tool")
    )
    return result, success


def _execute_tool(name: str, args: dict, cwd: str = ".", lamia=None) -> str:
    """Internal: execute a tool and return raw result string."""
    if name == ToolName.GET_DOCS:
        return _get_docs(args.get("topic", ""))
    elif name == ToolName.READ_FILE:
        return _read_file(
            args.get("path", ""), cwd,
            offset=int(args.get("offset", 0)),
            chunk_size=int(args.get("chunk_size", 0)),
        )
    elif name == ToolName.LIST_FILES:
        return _list_files(args.get("directory", "."), cwd)
    elif name == ToolName.WRITE_FILE:
        return _write_file(args.get("path", ""), args.get("content", ""), cwd)
    elif name == ToolName.PATCH_FILE:
        return _patch_file(
            args.get("path", ""),
            args.get("old_text", ""),
            args.get("new_text", ""),
            cwd,
        )
    elif name == ToolName.DELETE_FILE:
        return _delete_file(args.get("path", ""), cwd)
    elif name == ToolName.FIND_DEFINITION:
        return _find_definition(args.get("symbol", ""), cwd)
    elif name == ToolName.FIND_REFERENCES:
        return _find_references(args.get("symbol", ""), cwd)
    elif name == ToolName.COPY_FILE:
        return _copy_file(args.get("source", ""), args.get("destination", ""), cwd)
    elif name == ToolName.MOVE_FILE:
        return _move_file(args.get("source", ""), args.get("destination", ""), cwd)
    elif name == ToolName.GREP:
        return _grep(args.get("pattern", ""), args.get("directory", "."), args.get("include", ""), cwd)
    elif name == ToolName.GLOB:
        return _glob(args.get("pattern", ""), args.get("directory", "."), cwd)
    elif name == ToolName.WEB_FETCH:
        return _web_fetch(args.get("url", ""), lamia)
    elif name == ToolName.LINT_CODE:
        result = lint_code(args.get("content", ""), args.get("file_type", ""), cwd)
        import json as _json
        return _json.dumps(result, ensure_ascii=False)
    elif name.startswith("browser_"):
        return _browser_tool(name, args, cwd, lamia)
    else:
        return f"Unknown tool: {name}"


def _get_docs(topic: str) -> str:
    topic_lower = topic.strip().lower()
    filename = TOPIC_TO_FILE.get(topic_lower)

    if not filename:
        for key, val in TOPIC_TO_FILE.items():
            if topic_lower in key or key in topic_lower:
                filename = val
                break

    if not filename:
        available = ", ".join(sorted(set(TOPIC_TO_FILE.values())))
        return f"Topic '{topic}' not found. Available docs: {available}"

    docs_dir = _find_docs_dir()
    if not docs_dir:
        return "Documentation files not found in this lamia installation."

    doc_path = docs_dir / filename
    if not doc_path.is_file():
        return f"Documentation file not found: {filename}"

    try:
        return doc_path.read_text(encoding="utf-8")
    except Exception as exc:
        return f"Error reading docs: {exc}"


def _read_file(filepath: str, cwd: str, offset: int = 0, chunk_size: int = 0) -> str:
    if not filepath:
        return "Error: path is required"

    resolved = Path(filepath) if os.path.isabs(filepath) else Path(cwd) / filepath
    if resolved.exists() and resolved.is_dir():
        return (
            f"Error: path is a directory, not a file: {resolved}\n\n"
            "Use list_files to inspect directory contents."
        )
    if not resolved.is_file():
        basename = resolved.name
        candidates = []
        search_root = Path(cwd)
        for match in search_root.rglob(basename):
            if match.is_file() and not any(p in _SKIP_DIRS for p in match.parts):
                candidates.append(str(match))
                if len(candidates) >= 5:
                    break
        msg = f"Error: file not found: {resolved}"
        if candidates:
            msg += "\n\nDid you mean:\n" + "\n".join(f"  - {c}" for c in candidates)
        msg += "\n\nUse list_files to explore the directory structure."
        return msg

    effective_chunk = min(chunk_size, MAX_READ_CHUNK_CHARS) if chunk_size > 0 else MAX_READ_CHUNK_CHARS
    offset = max(offset, 0)

    try:
        total_chars = resolved.stat().st_size
        with resolved.open(encoding="utf-8", errors="replace") as f:
            if offset:
                f.seek(offset)
            content = f.read(effective_chunk)

        end_offset = offset + len(content)
        remaining = total_chars - end_offset

        if remaining > 0:
            content += (
                f"\n\n--- CHUNKED READ: returned chars {offset}–{end_offset - 1} "
                f"of {total_chars} total. "
                f"Call read_file with offset={end_offset} to continue. ---"
            )

        footer = entity_references_footer(resolved, cwd)
        if footer:
            content += footer
        return content
    except Exception as exc:
        return f"Error reading file: {exc}"


_SKIP_DIRS = {"node_modules", "__pycache__", ".git", "venv", ".venv", ".tox", ".mypy_cache"}


def _list_files(directory: str, cwd: str) -> str:
    resolved = Path(directory) if os.path.isabs(directory) else Path(cwd) / directory
    if not resolved.is_dir():
        return f"Directory not found: {resolved}"

    MAX_DEPTH = 4
    lines: list = []

    def _walk(dir_path: Path, prefix: str, depth: int) -> None:
        if depth > MAX_DEPTH:
            return
        try:
            children = sorted(dir_path.iterdir())
        except Exception:
            return
        for entry in children:
            if entry.name.startswith(".") or entry.name in _SKIP_DIRS:
                continue
            if entry.is_dir():
                lines.append(f"{prefix}{entry.name}/")
                _walk(entry, prefix + "  ", depth + 1)
            else:
                lines.append(f"{prefix}{entry.name}")

    _walk(resolved, "  ", 0)

    if not lines:
        return f"Empty directory: {resolved}"

    return f"{resolved}/\n" + "\n".join(lines)


_hu_linter = HuLinter()
_lm_linter = LmLinter()

_LINTERS = {
    ".hu": _hu_linter,
    ".lm": _lm_linter,
}


def lint_code(content: str, file_type: str, cwd: str = ".") -> dict:
    """Lint code content without writing to disk.

    Returns a dict with violations list, blocking flag, and feedback string.
    Used by the IDE to validate code blocks in LLM chat responses.
    """
    from lamia.lint.base import Severity

    linter = _LINTERS.get(f".{file_type}")
    if not linter:
        return {"violations": [], "blocking": False, "feedback": ""}

    result = linter.lint(content, cwd=cwd)
    violations = []
    for v in result.violations:
        violations.append({
            "code": v.rule.code,
            "line": v.line,
            "message": v.message,
            "severity": v.rule.severity.name.lower(),
        })

    blocking = any(v.rule.severity == Severity.Error for v in result.violations)
    return {
        "violations": violations,
        "blocking": blocking,
        "feedback": result.feedback_message(),
    }


def _blocking_lint_suffix(violations: list) -> str:
    """Build a blocking suffix if violations warrant it.

    Centralises the policy for what counts as a blocking error so it can be
    adjusted in one place (e.g. treat warnings as blocking too).
    """
    from lamia.lint.base import Severity

    blocking = [v for v in violations if v.rule.severity == Severity.Error]
    if not blocking:
        return ""
    return (
        f"\n\nThe file was saved, but it has {len(blocking)} ERROR(s) that MUST be "
        "fixed now with patch_file before you do anything else."
    )


def _linter_feedback(
    resolved: Path, content: str, original: Optional[str], cwd: str = "."
) -> tuple[str, list]:
    """Post-write lint feedback.

    Returns (feedback_message, violations).  Callers inspect violations to
    decide blocking policy (e.g. count errors, treat warnings as errors, etc.).
    """
    linter = _LINTERS.get(resolved.suffix)
    if not linter:
        return "", []
    result = linter.lint(content, original, cwd=cwd, filepath=str(resolved))
    feedback = result.feedback_message()
    if feedback:
        logger.debug("Lint feedback for %s: %d issues", resolved, len(result.violations))
    return feedback, result.violations


def _external_refs(resolved: Path, cwd: str) -> list[FileReference]:
    """Return references to resolved's stem from *other* files."""
    refs = _find_references_raw(resolved.stem, cwd)
    if refs is None:
        return []
    resolved_rel = os.path.relpath(str(resolved), cwd)
    return [r for r in refs if r.file != resolved_rel]


def _read_line_from_file(cwd: str, relpath: str, lineno: int) -> Optional[str]:
    """Read a single line from a file. Returns None on failure."""
    full = Path(cwd) / relpath
    try:
        lines = full.read_text(encoding="utf-8", errors="replace").splitlines()
        if 1 <= lineno <= len(lines):
            return lines[lineno - 1]
    except OSError:
        pass
    return None


def _find_matching_rparen(text: str, open_idx: int) -> int:
    """Return index of matching ')' for '(' at open_idx, or -1."""
    depth = 1
    in_str: Optional[str] = None
    escaped = False
    for i in range(open_idx + 1, len(text)):
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == in_str:
                in_str = None
            continue

        if ch in {'"', "'"}:
            in_str = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _split_top_level_args(args_text: str) -> list[str]:
    """Split argument list by commas while respecting nesting and strings."""
    args: list[str] = []
    current: list[str] = []
    in_str: Optional[str] = None
    escaped = False
    depth = 0

    for ch in args_text:
        if in_str:
            current.append(ch)
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == in_str:
                in_str = None
            continue

        if ch in {'"', "'"}:
            in_str = ch
            current.append(ch)
        elif ch in "([{":
            depth += 1
            current.append(ch)
        elif ch in ")]}":
            depth = max(0, depth - 1)
            current.append(ch)
        elif ch == "," and depth == 0:
            args.append("".join(current).strip())
            current = []
        else:
            current.append(ch)

    tail = "".join(current).strip()
    if tail:
        args.append(tail)
    return args


def _check_caller_params(stem: str, required: frozenset[str], ref: FileReference, cwd: str) -> Optional[str]:
    """Check if a .lm caller passes all required params. Returns warning or None."""
    if not ref.file.endswith(".lm"):
        return None
    line = _read_line_from_file(cwd, ref.file, ref.line)
    if line is None:
        return None
    marker = stem + "("
    start = line.find(marker)
    if start == -1:
        return None
    open_idx = start + len(stem)
    args_end = _find_matching_rparen(line, open_idx)
    if args_end < 0:
        return None

    args = line[open_idx + 1:args_end]
    passed: set[str] = set()
    for part in _split_top_level_args(args):
        part = part.strip()
        if "=" not in part:
            continue
        key = part.split("=", 1)[0].strip()
        if key.isidentifier():
            passed.add(key)

    missing = required - passed
    if not missing:
        return None
    return (
        f"  {ref.file}:{ref.line}: {stem}() missing required params: "
        f"{', '.join(sorted(missing))}"
    )


def entity_reference_feedback(resolved: Path, cwd: str, action: FileAction) -> str:
    """Cross-file reference feedback after a file mutation.

    Uses _find_references_raw to locate callers/importers, then for .hu files
    checks whether callers pass all required params.
    """
    if action == FileAction.MOVE and resolved.suffix != ".py":
        return ""
    if action != FileAction.MOVE and resolved.suffix not in {".hu", ".lm"}:
        return ""

    stem = resolved.stem
    ext_refs = _external_refs(resolved, cwd)
    if not ext_refs:
        return ""

    if action == FileAction.DELETE:
        header = f"USAGE WARNING: The following files still reference '{stem}' which was just deleted:"
        items = [f"  {r.file}:{r.line}: {r.text}" for r in ext_refs]
        return header + "\n" + "\n".join(items)

    if action == FileAction.MOVE:
        header = f"USAGE WARNING: The following files reference '{stem}' at the old location — update them:"
        items = [f"  {r.file}:{r.line}: {r.text}" for r in ext_refs]
        return header + "\n" + "\n".join(items)

    if resolved.suffix == ".hu" and action in (FileAction.WRITE, FileAction.PATCH):
        try:
            fn = parse_hu_file(str(resolved))
        except Exception:
            return ""
        required = fn.params - set(fn.defaults)
        if not required:
            return ""

        warnings: list[str] = []
        for ref in ext_refs:
            warning = _check_caller_params(stem, required, ref, cwd)
            if warning:
                warnings.append(warning)

        if warnings:
            header = f"USAGE WARNING: Callers of {stem}() may need updating:"
            return header + "\n" + "\n".join(warnings)

    return ""


def entity_references_footer(resolved: Path, cwd: str) -> str:
    """'Referenced by' footer for read_file on .hu/.lm files."""
    if resolved.suffix not in {".hu", ".lm"}:
        return ""
    ext_refs = _external_refs(resolved, cwd)
    if not ext_refs:
        return ""

    lines = [f"  {r.file}:{r.line}" for r in ext_refs]
    return "\n---\nReferenced by:\n" + "\n".join(lines)


def _commit_write(resolved: Path, content: str, original: Optional[str]) -> str:
    """Write content to disk and track the change."""
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
    except Exception as exc:
        return f"Error writing file: {exc}"

    entry: dict = {
        "path": str(resolved),
        "action": "modify" if original is not None else "create",
        "content": content,
    }
    if original is not None:
        entry["original"] = original
    _file_writes.append(entry)
    return ""


def _write_file(filepath: str, content: str, cwd: str) -> str:
    if not filepath:
        return "Error: path is required"

    resolved = Path(filepath) if os.path.isabs(filepath) else Path(cwd) / filepath

    original: Optional[str] = None
    if resolved.is_file():
        try:
            original = resolved.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass

    err = _commit_write(resolved, content, original)
    if err:
        return err

    msg = f"Written: {resolved} ({len(content)} chars)"
    if original is not None:
        msg += " (Tip: prefer patch_file for edits — it's safer and uses fewer tokens.)"

    lint, violations = _linter_feedback(resolved, content, original, cwd)
    if lint:
        msg += "\n" + lint

    refs = entity_reference_feedback(resolved, cwd, FileAction.WRITE)
    if refs:
        msg += "\n" + refs

    msg += _blocking_lint_suffix(violations)
    return msg


def _patch_file(filepath: str, old_text: str, new_text: str, cwd: str) -> str:
    if not filepath:
        return "Error: path is required"
    if not old_text:
        return "Error: old_text is required"

    resolved = Path(filepath) if os.path.isabs(filepath) else Path(cwd) / filepath
    if resolved.exists() and resolved.is_dir():
        return (
            f"Error: path is a directory, not a file: {resolved}\n\n"
            "Use list_files to inspect directory contents."
        )
    if not resolved.is_file():
        return f"Error: file not found: {resolved}"

    try:
        original = resolved.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"Error reading file: {exc}"

    count = original.count(old_text)
    if count == 0:
        lines = original.splitlines()
        search_lower = old_text.strip().lower()
        near: list[str] = []
        for i, line in enumerate(lines, 1):
            if search_lower[:40] in line.lower():
                near.append(f"  line {i}: {line[:80]}")
                if len(near) >= 3:
                    break
        hint = ""
        if near:
            hint = "\nSimilar lines found:\n" + "\n".join(near)
        return (
            f"Error: old_text not found in {resolved}. "
            f"Make sure it matches the file content exactly (whitespace matters).{hint}"
        )

    if count > 1:
        return (
            f"Error: old_text matches {count} locations in {resolved}. "
            "Provide more surrounding context in old_text to make it unique."
        )

    patched = original.replace(old_text, new_text, 1)

    err = _commit_write(resolved, patched, original)
    if err:
        return err

    msg = f"Patched: {resolved} ({len(old_text)} chars \u2192 {len(new_text)} chars)"

    lint, violations = _linter_feedback(resolved, patched, original, cwd)
    if lint:
        msg += "\n" + lint

    refs = entity_reference_feedback(resolved, cwd, FileAction.PATCH)
    if refs:
        msg += "\n" + refs

    msg += _blocking_lint_suffix(violations)
    return msg


def _delete_file(filepath: str, cwd: str) -> str:
    if not filepath:
        return "Error: path is required"

    resolved = Path(filepath) if os.path.isabs(filepath) else Path(cwd) / filepath
    if not resolved.is_file():
        return f"File not found: {resolved}"

    refs = entity_reference_feedback(resolved, cwd, FileAction.DELETE)

    original: Optional[str] = None
    try:
        original = resolved.read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass

    try:
        resolved.unlink()
    except Exception as exc:
        return f"Error deleting file: {exc}"

    entry: dict = {
        "path": str(resolved),
        "action": "delete",
    }
    if original is not None:
        entry["original"] = original
    _file_writes.append(entry)

    msg = f"Deleted: {resolved}"
    if refs:
        msg += "\n" + refs
    return msg


_DEF_RE_TEMPLATE = r'^[ \t]*(?:async\s+)?def\s+{}\s*\('
_CLASS_RE_TEMPLATE = r'^[ \t]*class\s+{}\s*[\(:]'


def _find_definition(symbol: str, cwd: str) -> str:
    if not symbol:
        return "Error: symbol is required"

    results: list[str] = []
    search_root = Path(cwd)

    for match in search_root.rglob("*.hu"):
        if match.stem == symbol and match.is_file():
            rel = os.path.relpath(str(match), cwd)
            results.append(f"{rel}:1: .hu file (function '{symbol}')")

    esc = re.escape(symbol)
    patterns = [
        re.compile(_DEF_RE_TEMPLATE.format(esc), re.MULTILINE),
        re.compile(_CLASS_RE_TEMPLATE.format(esc), re.MULTILINE),
    ]

    for ext in ("*.lm", "*.py"):
        for fpath in search_root.rglob(ext):
            if not fpath.is_file() or any(p in fpath.parts for p in _SKIP_DIRS):
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for pat in patterns:
                for m in pat.finditer(text):
                    lineno = text[:m.start()].count("\n") + 1
                    line = text[m.start():].split("\n", 1)[0].rstrip()
                    rel = os.path.relpath(str(fpath), cwd)
                    results.append(f"{rel}:{lineno}: {line}")

    if not results:
        return f"No definition found for '{symbol}'"
    return "\n".join(results)


def _find_references_raw(symbol: str, cwd: str) -> Optional[list[FileReference]]:
    """Return structured references for *symbol* under *cwd*, or None if none found."""
    results = find_usage(symbol, cwd, extensions=("*.lm", "*.hu", "*.py"))
    return results if results else None


def _find_references(symbol: str, cwd: str) -> str:
    """LLM-facing wrapper around _find_references_raw."""
    if not symbol:
        return "Error: symbol is required"
    refs = _find_references_raw(symbol, cwd)
    if refs is None:
        return f"No references found for '{symbol}'"
    output = "\n".join(f"{r.file}:{r.line}: {r.text}" for r in refs)
    return output


def _copy_file(source: str, destination: str, cwd: str) -> str:
    if not source or not destination:
        return "Error: source and destination are required"

    src = Path(source) if os.path.isabs(source) else Path(cwd) / source
    dst = Path(destination) if os.path.isabs(destination) else Path(cwd) / destination

    if not src.exists():
        return f"Source not found: {src}"

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            if dst.exists():
                dst = dst / src.name
            shutil.copytree(str(src), str(dst))
            count = sum(1 for _ in dst.rglob("*") if _.is_file())
            return f"Copied directory: {src} → {dst} ({count} files)"
        else:
            shutil.copy2(str(src), str(dst))
            msg = f"Copied: {src} → {dst}"
            if dst.suffix == ".hu" and src.stem == dst.stem:
                msg += (
                    f"\nNOTE: Copied .hu file has the same function name "
                    f"'{src.stem}' as the source. Rename it to a meaningful "
                    f"name to avoid ambiguity at runtime."
                )
            return msg
    except Exception as exc:
        return f"Error copying: {exc}"


def _move_file(source: str, destination: str, cwd: str) -> str:
    if not source or not destination:
        return "Error: source and destination are required"

    src = Path(source) if os.path.isabs(source) else Path(cwd) / source
    dst = Path(destination) if os.path.isabs(destination) else Path(cwd) / destination

    if not src.exists():
        return f"Source not found: {src}"

    refs = entity_reference_feedback(src, cwd, FileAction.MOVE)

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        msg = f"Moved: {src} → {dst}"
        if refs:
            msg += "\n" + refs
        return msg
    except Exception as exc:
        return f"Error moving: {exc}"


def _grep(pattern: str, directory: str, include: str, cwd: str) -> str:
    if not pattern:
        return "Error: pattern is required"

    search_dir = Path(directory) if os.path.isabs(directory) else Path(cwd) / directory
    if not search_dir.is_dir():
        return f"Directory not found: {search_dir}"

    try:
        regex = re.compile(pattern)
    except re.error:
        regex = re.compile(re.escape(pattern))

    MAX_RESULTS = 100
    results: list[str] = []

    for root, dirs, files in os.walk(search_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in _SKIP_DIRS]
        for fname in files:
            if fname.startswith("."):
                continue
            if include and not fnmatch.fnmatch(fname, include):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    for lineno, line in enumerate(f, 1):
                        if regex.search(line):
                            rel = os.path.relpath(fpath, cwd)
                            results.append(f"{rel}:{lineno}: {line.rstrip()}")
                            if len(results) >= MAX_RESULTS:
                                break
            except (OSError, UnicodeDecodeError):
                continue
            if len(results) >= MAX_RESULTS:
                break
        if len(results) >= MAX_RESULTS:
            break

    if not results:
        return f"No matches for '{pattern}' in {search_dir}"

    output = "\n".join(results)
    if len(results) >= MAX_RESULTS:
        output += f"\n\n... (truncated at {MAX_RESULTS} results)"
    return output


def _glob(pattern: str, directory: str, cwd: str) -> str:
    if not pattern:
        return "Error: pattern is required"

    search_dir = Path(directory) if os.path.isabs(directory) else Path(cwd) / directory
    if not search_dir.is_dir():
        return f"Directory not found: {search_dir}"

    MAX_RESULTS = 200
    matches: list[tuple[float, str]] = []

    for path in search_dir.rglob(pattern.lstrip("*/")):
        if path.is_file() and not any(p in _SKIP_DIRS or p.startswith(".") for p in path.parts):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0
            matches.append((mtime, str(path.relative_to(cwd if os.path.isabs(cwd) else Path.cwd()))))
            if len(matches) >= MAX_RESULTS:
                break

    if not matches:
        return f"No files matching '{pattern}' in {search_dir}"

    matches.sort(key=lambda x: x[0], reverse=True)
    output = "\n".join(p for _, p in matches)
    if len(matches) >= MAX_RESULTS:
        output += f"\n\n... (truncated at {MAX_RESULTS} results)"
    return output


# ── Web fetch (lightweight Lamia HTTP) ───────────────────────────────────────

_http_actions = HttpActions()
_WEB_FETCH_MAX_CHARS = 80_000


def _http_to_web_command(http_action) -> WebCommand:
    """Convert HttpActions output to the existing WebCommand HTTP format."""
    return WebCommand(
        action=WebActionType.HTTP_REQUEST,
        url=http_action.params.url,
        method=str(http_action.action).upper(),
        headers=http_action.params.headers,
        data=http_action.params.data,
    )


def _web_fetch(url: str, lamia) -> str:
    """Fetch URL content using Lamia's existing HTTP action flow."""
    if not url:
        return "Error: url is required"
    if lamia is None:
        return "Error: web_fetch not available (no lamia instance)"

    normalized_url = url if url.startswith(("http://", "https://")) else f"https://{url}"
    http_action = _http_actions.get(normalized_url)
    web_command = _http_to_web_command(http_action)
    result = _run_web(web_command, lamia)
    if isinstance(result, str) and result.startswith("Browser error"):
        return result.replace("Browser error", "Error fetching", 1)

    if isinstance(result, (dict, list)):
        text = json.dumps(result, ensure_ascii=False, indent=2)
    else:
        text = str(result) if result is not None else ""

    if len(text) > _WEB_FETCH_MAX_CHARS:
        text = text[:_WEB_FETCH_MAX_CHARS] + f"\n\n... (truncated, total {len(text)} chars)"
    return text or "(empty)"


# ── Browser tools ────────────────────────────────────────────────────────────


def _run_web(command, lamia):
    """Execute a WebCommand via lamia.run() (sync, handles browser lifecycle)."""
    if lamia is None:
        return "Error: browser not available (no lamia instance)"
    try:
        return lamia.run(command) or ""
    except Exception as exc:
        return f"Browser error: {exc}"


def _browser_tool(name: str, args: dict, cwd: str, lamia) -> str:
    if name == ToolName.BROWSER_NAVIGATE:
        url = args.get("url", "")
        if not url:
            return "Error: url is required"
        _run_web(WebCommand(action=WebActionType.NAVIGATE, url=url), lamia)
        title = _run_web(WebCommand(action=WebActionType.GET_TEXT, selector="title"), lamia)
        return f"Navigated to {url}\nPage title: {title}"

    elif name == ToolName.BROWSER_CLICK:
        selector = args.get("selector", "")
        if not selector:
            return "Error: selector is required"
        result = _run_web(WebCommand(action=WebActionType.CLICK, selector=selector), lamia)
        if isinstance(result, str) and result.startswith("Browser error"):
            return result
        return f"Clicked: {selector}"

    elif name == ToolName.BROWSER_TYPE:
        selector = args.get("selector", "")
        text = args.get("text", "")
        if not selector:
            return "Error: selector is required"
        result = _run_web(WebCommand(action=WebActionType.TYPE, selector=selector, value=text), lamia)
        if isinstance(result, str) and result.startswith("Browser error"):
            return result
        return f"Typed into {selector}"

    elif name == ToolName.BROWSER_GET_TEXT:
        selector = args.get("selector", "body")
        result = _run_web(WebCommand(action=WebActionType.GET_TEXT, selector=selector), lamia)
        text = str(result) if result else ""
        if len(text) > 50_000:
            text = text[:50_000] + f"\n\n... (truncated, total {len(text)} chars)"
        return text or "(empty)"

    elif name == ToolName.BROWSER_SCREENSHOT:
        filepath = args.get("path", "")
        if not filepath:
            filepath = str(Path(cwd) / "screenshot.png")
        elif not os.path.isabs(filepath):
            filepath = str(Path(cwd) / filepath)
        result = _run_web(WebCommand(action=WebActionType.SCREENSHOT, value=filepath), lamia)
        if isinstance(result, str) and result.startswith("Browser error"):
            return result
        return f"Screenshot saved: {filepath}"

    elif name == ToolName.BROWSER_WAIT:
        selector = args.get("selector", "")
        timeout = args.get("timeout", 10)
        if not selector:
            return "Error: selector is required"
        result = _run_web(WebCommand(action=WebActionType.WAIT, selector=selector, timeout=float(timeout)), lamia)
        if isinstance(result, str) and result.startswith("Browser error"):
            return result
        return f"Element found: {selector}"

    return f"Unknown browser tool: {name}"


def get_tools_system_prompt() -> str:
    """Return a system prompt fragment describing available tools."""
    tool_desc = []
    for t in TOOL_DEFINITIONS:
        params = ", ".join(
            f"{p}" for p in t["parameters"].get("properties", {}).keys()
        )
        tool_desc.append(f"- {t['name']}({params}): {t['description']}")

    return (
        "You have the following tools available. To use a tool, respond with a JSON object "
        "on its own line in this exact format: {\"tool\": \"tool_name\", \"args\": {\"param\": \"value\"}}\n"
        "After receiving the tool result, continue your response.\n\n"
        "Available tools:\n" + "\n".join(tool_desc)
    )
