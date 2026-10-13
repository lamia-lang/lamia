"""Prompt framing and paths for tool loops that read files.

The facade runs such a loop for a prompt made inside a ``with files()``
context, or one whose referenced file was cut when inlined.  Exploration
uses the read-only tools — list_files, read_file and glob — scoped to those
paths and refused anywhere outside them.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from lamia.engine.managers.llm.prompt_formatter import format_available_paths


def build_file_context_tools_prompt(paths: Sequence[Path]) -> str:
    """Build the file-context framing placed between the tool listing and the prompt.

    The tool listing and call-format instructions come from
    :func:`lamia.tools.loop.run_tool_loop` itself; this adds the paths the
    model may read.
    """
    return (
        "You can read the files and directories listed below with the tools. "
        "Directories end with '/'. Use tools only when you need file contents "
        "that were not already provided in the prompt.\n\n"
        + format_available_paths(paths)
    )


def existing_context_paths(paths: Sequence[str]) -> list[Path]:
    """Resolve the paths a files context declares, dropping those that do not exist."""
    resolved = [Path(os.path.expanduser(path)).resolve() for path in paths]
    return [path for path in resolved if path.exists()]
