"""Shared tool-loop utilities.

Both the CLI JSON-mode tool loop and the LLM manager's file-context tool
loop follow the same pattern:

    call LLM → extract tool calls → execute → build results → append → repeat

This module provides the shared building blocks so neither loop reinvents
them.  Each caller keeps its own outer loop (the CLI loop manages JSON
protocol events and token tracking; the LLM manager loop manages validators
and ValidationResult) but delegates the duplicated inner logic here.
"""

from __future__ import annotations

import json
import logging
from typing import Callable

from lamia.tools.parsing import (
    extract_tool_calls,
    detect_malformed_tool_call,
    strip_tool_calls,
    build_tool_result_entry,
    TOOL_FORMAT_CORRECTION,
)

logger = logging.getLogger(__name__)


def process_response(text: str) -> tuple[list[dict], bool, str]:
    """Process one LLM response: extract tool calls, detect malformed, strip.

    Returns:
        tool_calls: extracted valid tool calls (empty list if none)
        is_malformed: True if the model *tried* to call tools in a wrong format
        clean_text: response text with all tool-call artifacts removed
    """
    tool_calls = extract_tool_calls(text)
    if tool_calls:
        return tool_calls, False, strip_tool_calls(text)
    is_malformed = detect_malformed_tool_call(text)
    clean_text = strip_tool_calls(text)
    return [], is_malformed, clean_text


def execute_tool_calls(
    tool_calls: list[dict],
    executor: Callable[[str, dict], str],
) -> list[dict]:
    """Execute a batch of tool calls and return result entries.

    *executor* is called as ``executor(tool_name, tool_args) -> result_str``.
    """
    entries: list[dict] = []
    for tc in tool_calls:
        name = tc.get("tool", "")
        args = tc.get("args", {})
        logger.debug("Tool call: %s(%s)", name, args)
        result = executor(name, args)
        entries.append(build_tool_result_entry(name, args, result))
    return entries


def build_continuation_prompt(
    current_prompt: str,
    assistant_text: str,
    tool_result_entries: list[dict],
) -> str:
    """Build next-round prompt by appending assistant text and tool results."""
    tool_results_json = json.dumps(
        {"tool_results": tool_result_entries},
        ensure_ascii=False,
    )
    return (
        f"{current_prompt}\n\n"
        f"Assistant: {assistant_text}\n\n"
        f"Tool results JSON:\n{tool_results_json}\n\n"
        f"Continue your response to the user based on these tool results."
    )


def build_correction_prompt(
    current_prompt: str,
    assistant_text: str,
) -> str:
    """Build a correction prompt when the model used the wrong tool-call format."""
    return (
        f"{current_prompt}\n\nAssistant: {assistant_text}\n\n"
        f"System: {TOOL_FORMAT_CORRECTION}"
    )
