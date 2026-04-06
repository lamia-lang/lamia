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
        "description": "List files in a directory. Returns file names and types.",
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
]


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
        return f"File not found: {resolved}"

    try:
        content = resolved.read_text(encoding="utf-8", errors="replace")
        if len(content) > 100_000:
            return content[:100_000] + f"\n\n... (truncated, total {len(content)} chars)"
        return content
    except Exception as exc:
        return f"Error reading file: {exc}"


def _list_files(directory: str, cwd: str) -> str:
    resolved = Path(directory) if os.path.isabs(directory) else Path(cwd) / directory
    if not resolved.is_dir():
        return f"Directory not found: {resolved}"

    entries = []
    try:
        for entry in sorted(resolved.iterdir()):
            if entry.name.startswith("."):
                continue
            kind = "dir" if entry.is_dir() else entry.suffix or "file"
            entries.append(f"  {entry.name}  ({kind})")
    except Exception as exc:
        return f"Error listing directory: {exc}"

    if not entries:
        return f"Empty directory: {resolved}"

    return f"{resolved}/\n" + "\n".join(entries)


def _write_file(filepath: str, content: str, cwd: str) -> str:
    if not filepath:
        return "Error: path is required"

    resolved = Path(filepath) if os.path.isabs(filepath) else Path(cwd) / filepath

    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return f"Written: {resolved} ({len(content)} chars)"
    except Exception as exc:
        return f"Error writing file: {exc}"


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
