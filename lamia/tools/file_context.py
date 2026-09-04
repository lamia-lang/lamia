"""Sandboxed read-only tool executor for ``with files()`` contexts.

Only exposes list_files, read_file, and glob — all restricted to
the directories declared in the active files context.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path

from lamia.tools.definitions import (
    ToolName,
    FILE_CONTEXT_TOOL_DEFINITIONS,
    MAX_FILE_CONTEXT_READ_CHARS,
    MAX_FILE_CONTEXT_LIST_DEPTH,
)

_SKIP_DIRS = {"node_modules", "__pycache__", ".git", "venv", ".venv", ".tox", ".mypy_cache"}


def build_file_context_tools_prompt() -> str:
    """Build the system-prompt fragment for file-context scoped tools."""
    tool_desc = []
    for t in FILE_CONTEXT_TOOL_DEFINITIONS:
        params = ", ".join(t["parameters"].get("properties", {}).keys())
        tool_desc.append(f"- {t['name']}({params}): {t['description']}")

    return (
        "You have access to a sandboxed file context. You do NOT know what files "
        "exist in it — you MUST use the tools below to discover and read files. "
        "NEVER guess or assume filenames.\n\n"
        "To call a tool, output a JSON object on its own line in this EXACT format:\n"
        '{"tool": "tool_name", "args": {"param": "value"}}\n\n'
        "Available tools:\n" + "\n".join(tool_desc) + "\n\n"
        "After receiving tool results, continue your response to the user. "
        "Use tools only when you need to discover or read file contents that "
        "were not already provided in the prompt."
    )


class FileContextToolExecutor:
    """Executes read-only file tools restricted to allowed file-context roots."""

    def __init__(self, allowed_paths: tuple[str, ...]):
        self.allowed_roots: list[Path] = []
        for path in allowed_paths:
            self.allowed_roots.append(Path(os.path.expanduser(path)).resolve())

    def execute(self, tool_name: str, args: dict) -> str:
        if tool_name == ToolName.LIST_FILES:
            return self._list_files(args.get("directory", "."))
        if tool_name == ToolName.READ_FILE:
            return self._read_file(args.get("path", ""))
        if tool_name == ToolName.GLOB:
            return self._glob(args.get("pattern", ""))
        return f"Error: unknown tool '{tool_name}'"

    def _validate_path(self, path_str: str) -> Path:
        if not path_str:
            if self.allowed_roots:
                return self.allowed_roots[0]
            raise PermissionError("No allowed paths configured")

        candidate = Path(path_str)

        if not candidate.is_absolute():
            for root in self.allowed_roots:
                resolved = (root / candidate).resolve()
                if resolved.exists() and self._is_under_allowed(resolved):
                    return resolved
            resolved = (self.allowed_roots[0] / candidate).resolve()
            if self._is_under_allowed(resolved):
                return resolved
            raise PermissionError(f"Access denied: '{path_str}' is outside the allowed file context")

        resolved = candidate.resolve()
        if not self._is_under_allowed(resolved):
            raise PermissionError(f"Access denied: '{path_str}' is outside the allowed file context")
        return resolved

    def _is_under_allowed(self, resolved: Path) -> bool:
        for root in self.allowed_roots:
            try:
                resolved.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def _list_files(self, directory: str) -> str:
        try:
            resolved = self._validate_path(directory)
        except PermissionError as exc:
            return str(exc)

        if not resolved.is_dir():
            return f"Not a directory: {directory}"

        lines: list[str] = []

        def _walk(dir_path: Path, prefix: str, depth: int) -> None:
            if depth > MAX_FILE_CONTEXT_LIST_DEPTH:
                return
            try:
                children = sorted(dir_path.iterdir())
            except OSError:
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
            return f"Empty directory: {directory}"
        return f"{resolved.name}/\n" + "\n".join(lines)

    def _read_file(self, filepath: str) -> str:
        if not filepath:
            return "Error: path is required"
        try:
            resolved = self._validate_path(filepath)
        except PermissionError as exc:
            return str(exc)
        if not resolved.is_file():
            return f"File not found: {filepath}"
        try:
            content = resolved.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"Error reading file: {exc}"
        if len(content) > MAX_FILE_CONTEXT_READ_CHARS:
            content = content[:MAX_FILE_CONTEXT_READ_CHARS] + f"\n\n... (truncated, total {len(content)} chars)"
        return content

    def _glob(self, pattern: str) -> str:
        if not pattern:
            return "Error: pattern is required"
        matches: list[str] = []
        for sub_pattern in pattern.split("|"):
            sub_pattern = sub_pattern.strip()
            for root in self.allowed_roots:
                if not root.is_dir():
                    continue
                for match in root.rglob("*"):
                    if not match.is_file():
                        continue
                    rel_parts = match.relative_to(root).parts
                    if any(p in _SKIP_DIRS or p.startswith(".") for p in rel_parts):
                        continue
                    rel_path = str(match.relative_to(root))
                    if fnmatch.fnmatch(rel_path, sub_pattern) or fnmatch.fnmatch(match.name, sub_pattern):
                        if rel_path not in matches:
                            matches.append(rel_path)
        if not matches:
            return f"No files matching '{pattern}'"
        return "\n".join(sorted(matches))
