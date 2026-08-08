"""Shared file-persistence helpers for registry modules.

Both the trigger registry and the scheduling registry need atomic JSON writes
and safe JSON reads. This module provides those primitives so neither registry
re-implements them.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional


def atomic_write(path: Path, content: str) -> None:
    """Write content to *path* via temp-file + rename for crash safety."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    closed = False
    try:
        os.write(fd, content.encode())
        os.fsync(fd)
        os.close(fd)
        closed = True
        os.replace(tmp, str(path))
    except BaseException:
        if not closed:
            os.close(fd)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_json(path: Path, default: Optional[Any] = None) -> Any:
    """Read and parse a JSON file, returning *default* on missing/corrupt files."""
    if default is None:
        default = []
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return default
