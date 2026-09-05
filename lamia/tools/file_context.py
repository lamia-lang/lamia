"""File discovery for ``with files()`` contexts.

Runs LLM calls made inside a files context.  Exploration uses the ordinary
read-only tools — list_files, read_file and glob — scoped to the paths the
context declares and refused anywhere outside them.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, TYPE_CHECKING

from lamia.async_bridge import EventLoopManager
from lamia.engine.managers.llm.files_context_manager import get_active_files_context
from lamia.tools.definitions import (
    FILE_CONTEXT_TOOL_MAX_ROUNDS,
    FILE_CONTEXT_TOOL_NAMES,
)
from lamia.tools.loop import run_tool_loop

if TYPE_CHECKING:
    from lamia.facade.lamia import Lamia


def build_file_context_tools_prompt() -> str:
    """Build the file-context-specific framing prepended to the tool loop's prompt.

    The tool listing and call-format instructions come from
    :func:`lamia.tools.loop.run_tool_loop` itself; this only adds what's
    specific to a sandboxed file context.
    """
    return (
        "You have access to a sandboxed file context. You do NOT know what files "
        "exist in it — you MUST use the tools below to discover and read files. "
        "NEVER guess or assume filenames.\n\n"
        "Use tools only when you need to discover or read file contents that "
        "were not already provided in the prompt."
    )


async def run_with_file_tools(lamia: "Lamia", prompt: str, **run_kwargs: Any) -> Any:
    """Run one LLM call made inside a ``with files()`` block.

    A context that names only files has nothing to discover, so their content
    is appended to the prompt and the call runs normally.  A context holding a
    directory runs a tool loop instead, letting the model list and read its way
    through the files it needs.

    *run_kwargs* are forwarded to :meth:`Lamia.run_async` — the tool rounds
    themselves run untyped, and a requested ``return_type`` is applied by a
    final call over the prompt the loop accumulated.
    """
    context = get_active_files_context()
    if context is None or not context.indexed_files:
        return await lamia.run_async(prompt, **run_kwargs)

    if context.has_only_explicit_files:
        return await lamia.run_async(context.append_indexed_files(prompt), **run_kwargs)

    loop_result = await run_tool_loop(
        lamia,
        build_file_context_tools_prompt() + "\n\n" + prompt,
        allowed_tools=FILE_CONTEXT_TOOL_NAMES,
        allowed_dirs=[Path(os.path.expanduser(path)) for path in context.paths],
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
