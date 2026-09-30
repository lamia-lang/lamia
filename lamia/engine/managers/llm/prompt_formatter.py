"""Formatting of file content for LLM prompts."""

import os
from pathlib import Path
from typing import List, Sequence, Tuple


def format_files(files: List[Tuple[str, str]]) -> str:
    """Render ``(filepath, content)`` pairs as a ``<files>`` block, or an empty string when there are none."""
    if not files:
        return ""
    parts = ["<files>\n"]
    for filepath, content in files:
        parts.append(f'<file path="{display_path(filepath)}">\n{content}\n</file>\n')
    parts.append("</files>\n\n")
    return "".join(parts)


def format_available_paths(paths: Sequence[Path]) -> str:
    """Render resolved *paths* as an ``<available_paths>`` block, directories ending with ``/``."""
    lines = [f"{path}/" if path.is_dir() else str(path) for path in paths]
    return "<available_paths>\n" + "\n".join(lines) + "\n</available_paths>\n\n"


def display_path(filepath: str) -> str:
    """Path relative to the working directory, or absolute when the file lies outside it."""
    absolute = os.path.abspath(filepath)
    relative = os.path.relpath(absolute)
    return absolute if relative.startswith("..") else relative
