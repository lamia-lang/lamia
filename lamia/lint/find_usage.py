"""Cross-file usage lookup helpers for lint rules and tools."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_SKIP_DIRS = {
    "node_modules",
    "__pycache__",
    ".git",
    "venv",
    ".venv",
    ".tox",
    ".mypy_cache",
    "dist",
    "build",
    ".lamia_sessions",
}


@dataclass(frozen=True)
class UsageReference:
    file: str
    line: int
    text: str


def find_usage(
    symbol: str,
    cwd: str,
    extensions: Iterable[str] = ("*.lm", "*.hu", "*.py"),
) -> list[UsageReference]:
    """Return symbol usages under cwd for the given extension globs."""
    if not symbol:
        return []
    pat = re.compile(r"(?<![a-zA-Z_])" + re.escape(symbol) + r"(?![a-zA-Z_\d])")
    results: list[UsageReference] = []
    search_root = Path(cwd)
    for ext in extensions:
        for fpath in search_root.rglob(ext):
            if not fpath.is_file() or any(part in _SKIP_DIRS for part in fpath.parts):
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = os.path.relpath(str(fpath), cwd)
            for lineno, line in enumerate(text.splitlines(), 1):
                if pat.search(line):
                    results.append(UsageReference(file=rel, line=lineno, text=line.rstrip()))
    return results
