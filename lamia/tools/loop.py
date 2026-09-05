"""Unified tool loop.

Single implementation used by both the CLI JSON-mode tool loop and the
file-context tool loop generated for ``with files()`` blocks.  Callers differ
only in which tools they allow, which directories those tools may touch, and
what they do with the messages the loop emits.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional, Sequence, TYPE_CHECKING

from lamia.tools.definitions import (
    tool_progress_label,
)
from lamia.tools.dispatch import execute_tool
from lamia.tools.parsing import (
    extract_tool_calls,
    detect_malformed_tool_call,
    strip_tool_calls,
    build_tool_result_entry,
    TOOL_FORMAT_CORRECTION,
)

if TYPE_CHECKING:
    from lamia.facade.lamia import Lamia
    from lamia.facade.result_types import LamiaResult
    from lamia.validation.base import TrackingContext

logger = logging.getLogger(__name__)


@dataclass
class AssistantMessage:
    """Text the model produced in one round, with tool calls stripped out."""
    text: str


@dataclass
class ToolCallMessage:
    """A tool the model asked for, about to run."""
    tool: str
    args: dict
    label: str


@dataclass
class ToolResultMessage:
    """The outcome of one tool call."""
    tool: str
    success: bool
    result: str


@dataclass
class ToolLoopResult:
    """Outcome of a tool loop.

    Attributes:
        result: Result of the final LLM call, with token counts from every
            round accumulated into its tracking context.
        prompt: The prompt as the loop left it — the original prompt plus
            every assistant turn and tool result.  Send this, not the
            original prompt, to ask a follow-up question about the same
            material.
    """
    result: "LamiaResult"
    prompt: str


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


# TODO: Instead of text-based loop processing use structured user-assistant loops
async def run_tool_loop(
    lamia: "Lamia",
    prompt: str,
    *,
    allowed_tools: Optional[set] = None,
    allowed_dirs: Sequence[Path] = (),
    restrict_to_allowed_dirs: bool = False,
    max_rounds: int = 10,
    max_calls_by_tool: Optional[Mapping[str, int]] = None,
    on_message: Optional[Callable] = None,
) -> ToolLoopResult:
    """Run a text-based tool loop.

    Each round sends the prompt to *lamia*, parses the response for tool-call
    JSON, runs the requested tools, appends the results to the prompt, and
    sends it again — until the model answers without calling a tool or
    *max_rounds* is reached.

    Args:
        lamia: Facade instance the rounds are run through.
        prompt: Initial prompt.  Tool descriptions must already be prepended
            by the caller.
        allowed_tools: Tool names the model may call; ``None`` allows all.
        allowed_dirs: Directories path arguments resolve against. Defaults to
            the process working directory.
        restrict_to_allowed_dirs: Refuse path access outside *allowed_dirs*.
            Keep this enabled for untrusted or multi-tenant file contexts.
        max_rounds: Maximum number of LLM calls.
        max_calls_by_tool: Per-tool call caps. Tools absent from this map are
            unlimited (apart from *max_rounds*); ``None`` applies no caps.
        on_message: Called with each :class:`AssistantMessage`,
            :class:`ToolCallMessage` and :class:`ToolResultMessage` as it
            happens, for callers that report progress.

    Returns:
        A :class:`ToolLoopResult` holding the final result and the prompt the
        loop accumulated.
    """
    totals: dict = {}
    model_name = None
    result = None
    repeats: dict = {}

    for _round in range(max_rounds + 1):
        is_last = _round >= max_rounds
        result = await lamia.run_async(prompt, _full_result=True)

        ctx = result.tracking_context
        if ctx and ctx.data_provider_name:
            model_name = ctx.data_provider_name
        _accumulate_usage(ctx, totals)

        text = result.result_text or ""
        tool_calls, is_malformed, clean_text = process_response(text)

        if not tool_calls:
            if is_malformed and not is_last:
                logger.debug("Malformed tool call detected, sending correction")
                prompt = _build_correction_prompt(prompt, text)
                continue
            result.result_text = clean_text
            break

        _emit(on_message, AssistantMessage(text=clean_text))
        entries, looping = _run_tool_calls(
            tool_calls,
            lamia=lamia,
            allowed_tools=allowed_tools,
            allowed_dirs=allowed_dirs,
            restrict_to_allowed_dirs=restrict_to_allowed_dirs,
            max_calls_by_tool=max_calls_by_tool,
            call_counts=repeats,
            on_message=on_message,
        )

        if looping or is_last:
            result.result_text = clean_text
            break

        prompt = _build_continuation_prompt(prompt, text, entries)

    _stamp_totals(result, totals, model_name)
    return ToolLoopResult(result=result, prompt=prompt)


# ── Tool calls ──────────────────────────────────────────────────────────────

def _run_tool_calls(
    tool_calls: list[dict],
    *,
    lamia: "Lamia",
    allowed_tools: Optional[set],
    allowed_dirs: Sequence[Path],
    restrict_to_allowed_dirs: bool,
    max_calls_by_tool: Optional[Mapping[str, int]],
    call_counts: dict[str, int],
    on_message: Optional[Callable],
) -> tuple[list[dict], bool]:
    """Run one round's tool calls.

    Returns result entries and whether a configured tool call cap was reached.
    """
    entries: list[dict] = []
    for tool_call in tool_calls:
        name = tool_call.get("tool", "")
        args = tool_call.get("args", {})
        logger.debug("Tool call: %s(%s)", name, args)

        if _exceeds_call_limit(name, max_calls_by_tool, call_counts):
            return entries, True

        _emit(on_message, ToolCallMessage(tool=name, args=args, label=tool_progress_label(name, args)))

        if allowed_tools is not None and name not in allowed_tools:
            result, success = f"Unknown tool: {name}", False
        else:
            result, success = execute_tool(
                name,
                args,
                allowed_dirs,
                lamia=lamia,
                restrict_to_allowed_dirs=restrict_to_allowed_dirs,
            )

        _emit(on_message, ToolResultMessage(tool=name, success=success, result=result))
        entries.append(build_tool_result_entry(name, args, result))
    return entries, False


def _exceeds_call_limit(
    name: str,
    max_calls_by_tool: Optional[Mapping[str, int]],
    call_counts: dict[str, int],
) -> bool:
    """Count a call only when its tool has an explicit configured cap."""
    if max_calls_by_tool is None or name not in max_calls_by_tool:
        return False

    call_counts[name] = call_counts.get(name, 0) + 1
    limit = max_calls_by_tool[name]
    if call_counts[name] <= limit:
        return False

    logger.warning("Tool call cap reached: %s called %d times (limit %d)", name, call_counts[name], limit)
    return True


def _emit(on_message: Optional[Callable], message) -> None:
    """Hand one message to the caller's reporter, if it wants them."""
    if on_message is not None:
        on_message(message)


# ── Token accounting ────────────────────────────────────────────────────────

def _accumulate_usage(ctx: Optional["TrackingContext"], totals: dict) -> None:
    """Add token counts from a tracking context into running totals."""
    if not ctx or not ctx.metadata or "usage" not in ctx.metadata:
        return
    usage = ctx.metadata["usage"]
    inp = usage.get("prompt_tokens") or usage.get("input_tokens", 0)
    out = usage.get("completion_tokens") or usage.get("output_tokens", 0)
    totals["input"] = totals.get("input", 0) + inp
    totals["output"] = totals.get("output", 0) + out
    totals["total"] = totals["input"] + totals["output"]


def _stamp_totals(
    result: "LamiaResult",
    totals: dict,
    model_name: Optional[str],
) -> None:
    """Write accumulated token totals back into the final result's tracking context."""
    ctx = result.tracking_context if result is not None else None
    if ctx and totals:
        if ctx.metadata is None:
            ctx.metadata = {}
        ctx.metadata["usage"] = {
            "prompt_tokens": totals.get("input", 0),
            "completion_tokens": totals.get("output", 0),
            "total_tokens": totals.get("total", 0),
        }
    if ctx and model_name:
        ctx.data_provider_name = model_name


# ── Prompt building ─────────────────────────────────────────────────────────

def _build_continuation_prompt(
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


def _build_correction_prompt(
    current_prompt: str,
    assistant_text: str,
) -> str:
    """Build a correction prompt when the model used the wrong tool-call format."""
    return (
        f"{current_prompt}\n\nAssistant: {assistant_text}\n\n"
        f"System: {TOOL_FORMAT_CORRECTION}"
    )
