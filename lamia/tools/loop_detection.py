"""Repeat-call loop detection for the tool loop.

Flags a tool call once its exact signature (name and arguments) recurs at
least as often as that tool's configured limit within a trailing window
sized off that same limit. Each tool's window is independent: a larger
window some other tool needs never widens a smaller tool's own lookback.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Deque, Mapping, Optional

logger = logging.getLogger(__name__)

# How much further back a tool's repeat window reaches than its own repeat
# limit, so calls from other tools interleaved in between don't push a
# legitimate repeat (e.g. one revert) out of view.
WINDOW_COEFFICIENT = 3


def exceeds_call_limit(
    name: str,
    args: dict,
    max_calls_by_tool: Optional[Mapping[str, int]],
    history: Deque[str],
) -> bool:
    """Flag a call whose exact signature already recurs at its tool's limit.

    Only tools with a configured limit are checked. Each tool's own window
    is ``WINDOW_COEFFICIENT`` times its limit, taken as the trailing slice
    of *history* — regardless of how large *history* itself is, so a
    larger window needed by some other tool never widens this one's.
    """
    if max_calls_by_tool is None or name not in max_calls_by_tool:
        return False

    limit = max_calls_by_tool[name]
    window = WINDOW_COEFFICIENT * limit
    signature = _call_signature(name, args)
    occurrences = list(history)[-window:].count(signature)

    if occurrences >= limit:
        logger.warning(
            "Tool call loop detected: %s repeated %d times within the last %d calls (limit %d)",
            name, occurrences, window, limit,
        )
        return True

    history.append(signature)
    return False


def history_size(max_calls_by_tool: Optional[Mapping[str, int]]) -> int:
    """Shared history capacity: the largest window any configured tool needs."""
    if not max_calls_by_tool:
        return 0
    return WINDOW_COEFFICIENT * max(max_calls_by_tool.values())


def _call_signature(name: str, args: dict) -> str:
    """Exact, order-independent identity of a tool call.

    Hashed rather than kept as the raw canonical string: some tools (e.g.
    file writes) carry whole file contents in *args*, and history holds
    several entries at once, each compared on every subsequent call.
    """
    canonical = f"{name}:{json.dumps(args, sort_keys=True, default=str)}"
    return hashlib.sha256(canonical.encode()).hexdigest()
