"""File discovery for ``with files()`` contexts.

Runs LLM calls made inside a files context.  Exploration uses the ordinary
read-only tools — list_files, read_file and glob — scoped to the paths the
context declares and refused anywhere outside them.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Sequence, TYPE_CHECKING

from lamia.async_bridge import EventLoopManager
from lamia.engine.managers.llm.files_context_manager import get_active_files_context
from lamia.engine.managers.llm.prompt_formatter import format_available_paths
from lamia.tools.definitions import (
    FILE_CONTEXT_TOOL_MAX_ROUNDS,
    FILE_CONTEXT_TOOL_NAMES,
)
from lamia.tools.loop import run_tool_loop

if TYPE_CHECKING:
    from lamia.facade.lamia import Lamia


def build_file_context_tools_prompt(paths: Sequence[Path]) -> str:
    """Build the file-context framing placed between the tool listing and the prompt.

    The tool listing and call-format instructions come from
    :func:`lamia.tools.loop.run_tool_loop` itself; this adds the paths the
    context declares.
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


async def run_with_file_tools(lamia: "Lamia", prompt: str, **run_kwargs: Any) -> Any:
    """Run one LLM call made inside a ``with files()`` block.

    The model gets the context's existing paths and reads what it needs
    through a tool loop restricted to those same paths.  Files referenced
    with ``{@filename}`` are inserted into the prompt by the LLM manager.

    *run_kwargs* are forwarded to :meth:`Lamia.run_async` — the tool rounds
    themselves run untyped, and a requested ``return_type`` is applied by a
    final call over the prompt the loop accumulated.
    """
    context = get_active_files_context()
    paths = existing_context_paths(context.paths) if context is not None else []
    if not paths or not context.indexed_files:
        return await lamia.run_async(prompt, **run_kwargs)

    loop_result = await run_tool_loop(
        lamia,
        build_file_context_tools_prompt(paths) + prompt,
        allowed_tools=FILE_CONTEXT_TOOL_NAMES,
        allowed_dirs=paths,
        restrict_to_allowed_dirs=True,
        max_rounds=FILE_CONTEXT_TOOL_MAX_ROUNDS,
    )

    if run_kwargs.get("return_type") is None:
        if run_kwargs.get("_full_result"):
            return loop_result.result
        return loop_result.result.result_text
    return await lamia.run_async(loop_result.prompt, **run_kwargs)


def run_with_file_tools_sync(lamia: "Lamia", prompt: str, **run_kwargs: Any) -> Any:
    """Synchronous entry point for :func:`run_with_file_tools`."""
    return EventLoopManager.run_coroutine(run_with_file_tools(lamia, prompt, **run_kwargs))
