"""Agentic tools for lamia interactive/json mode.

These tools are made available to the LLM via the system prompt so it can
request documentation, read project files, list directory contents, and
write files.  The tool-use loop is driven by the caller (json_mode or
interactive_mode) — this module only provides the tool definitions and
execution logic.
"""
import os
import logging
from pathlib import Path
from typing import Optional

from lamia.lint import HuLinter

logger = logging.getLogger(__name__)

TOPIC_TO_FILE = {
    "lm-syntax": "user-guide/lm-syntax.md",
    "lm": "user-guide/lm-syntax.md",
    ".lm": "user-guide/lm-syntax.md",
    "hu-syntax": "user-guide/hu-syntax.md",
    "hu": "user-guide/hu-syntax.md",
    ".hu": "user-guide/hu-syntax.md",
    "files-context": "user-guide/files-context.md",
    "files": "user-guide/files-context.md",
    "file-context": "user-guide/files-context.md",
    "configuration": "getting-started/configuration.md",
    "config": "getting-started/configuration.md",
    "config.yaml": "getting-started/configuration.md",
    "installation": "getting-started/installation.md",
    "install": "getting-started/installation.md",
    "validation": "user-guide/validation.md",
    "web-automation": "user-guide/web-automation.md",
    "web": "user-guide/web-automation.md",
    "evaluation": "user-guide/evaluation.md",
    "eval": "user-guide/evaluation.md",
    "selector": "validation/selector-usage-guide.md",
}

_DOCS_TOPICS = ", ".join(sorted(set(TOPIC_TO_FILE.keys())))

TOOL_DEFINITIONS = [
    {
        "name": "get_docs",
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
        "name": "read_file",
        "description": "Read the contents of a file at the given path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative file path to read",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_files",
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
        "name": "write_file",
        "description": "Create or overwrite a file with the given content.",
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
        "name": "patch_file",
        "description": (
            "Edit an existing file by replacing old_text with new_text. "
            "Preferred over write_file for modifications — only express the change, not the whole file."
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
        "name": "delete_file",
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


def execute_tool(name: str, args: dict, cwd: str = ".") -> str:
    """Execute a tool by name and return the result as a string."""
    if name == "get_docs":
        return _get_docs(args.get("topic", ""))
    elif name == "read_file":
        return _read_file(args.get("path", ""), cwd)
    elif name == "list_files":
        return _list_files(args.get("directory", "."), cwd)
    elif name == "write_file":
        return _write_file(args.get("path", ""), args.get("content", ""), cwd)
    elif name == "patch_file":
        return _patch_file(
            args.get("path", ""),
            args.get("old_text", ""),
            args.get("new_text", ""),
            cwd,
        )
    elif name == "delete_file":
        return _delete_file(args.get("path", ""), cwd)
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


def _read_file(filepath: str, cwd: str) -> str:
    if not filepath:
        return "Error: path is required"

    resolved = Path(filepath) if os.path.isabs(filepath) else Path(cwd) / filepath
    if not resolved.is_file():
        basename = resolved.name
        candidates = []
        search_root = Path(cwd)
        for match in search_root.rglob(basename):
            if match.is_file() and not any(p in _SKIP_DIRS for p in match.parts):
                candidates.append(str(match))
                if len(candidates) >= 5:
                    break
        msg = f"File not found: {resolved}"
        if candidates:
            msg += "\n\nDid you mean:\n" + "\n".join(f"  - {c}" for c in candidates)
        msg += "\n\nUse list_files to explore the directory structure."
        return msg

    try:
        content = resolved.read_text(encoding="utf-8", errors="replace")
        if len(content) > 100_000:
            return content[:100_000] + f"\n\n... (truncated, total {len(content)} chars)"
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

_LINTERS = {
    ".hu": _hu_linter,
}


def _lint_feedback(resolved: Path, content: str, original: Optional[str]) -> str:
    """Post-write lint feedback. Returns empty string if clean or no linter."""
    linter = _LINTERS.get(resolved.suffix)
    if not linter:
        return ""
    result = linter.lint(content, original)
    feedback = result.feedback_message()
    if feedback:
        logger.debug("Lint feedback for %s: %d issues", resolved, len(result.violations))
    return feedback


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

    feedback = _lint_feedback(resolved, content, original)
    if feedback:
        msg += "\n" + feedback

    return msg


def _patch_file(filepath: str, old_text: str, new_text: str, cwd: str) -> str:
    if not filepath:
        return "Error: path is required"
    if not old_text:
        return "Error: old_text is required"

    resolved = Path(filepath) if os.path.isabs(filepath) else Path(cwd) / filepath
    if not resolved.is_file():
        return f"File not found: {resolved}"

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
            f"old_text not found in {resolved}. "
            f"Make sure it matches the file content exactly (whitespace matters).{hint}"
        )

    if count > 1:
        return (
            f"old_text matches {count} locations in {resolved}. "
            "Provide more surrounding context in old_text to make it unique."
        )

    patched = original.replace(old_text, new_text, 1)

    err = _commit_write(resolved, patched, original)
    if err:
        return err

    msg = f"Patched: {resolved} ({len(old_text)} chars \u2192 {len(new_text)} chars)"

    feedback = _lint_feedback(resolved, patched, original)
    if feedback:
        msg += "\n" + feedback

    return msg


def _delete_file(filepath: str, cwd: str) -> str:
    if not filepath:
        return "Error: path is required"

    resolved = Path(filepath) if os.path.isabs(filepath) else Path(cwd) / filepath
    if not resolved.is_file():
        return f"File not found: {resolved}"

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

    return f"Deleted: {resolved}"


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
