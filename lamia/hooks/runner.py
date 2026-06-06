"""HookRunner: matches and executes post_llm hooks by event, return type, and function name."""

import fnmatch
import logging
from typing import List, Optional, Dict

from lamia.hooks import HookDefinition

logger = logging.getLogger(__name__)


class HookRunner:
    """Executes registered hooks filtered by event type and optional matchers.

    post_llm hooks have contract: str -> str
    (receive LLM response content, return transformed content)

    The runner maintains execution context (current function name and return type)
    which is set before each execution and used internally for hook matching.
    """

    def __init__(self, hooks: Optional[List[HookDefinition]] = None):
        self._hooks_by_event: Dict[str, List[HookDefinition]] = {}
        self._current_function: Optional[str] = None
        self._current_return_type: Optional[str] = None

        for hook in (hooks or []):
            self.register(hook)

    def register(self, hook: HookDefinition) -> None:
        """Register a hook definition. Can be called during discovery."""
        self._hooks_by_event.setdefault(hook.event, []).append(hook)

    @property
    def has_hooks(self) -> bool:
        return bool(self._hooks_by_event)

    def set_context(self, function_name: Optional[str] = None, return_type: Optional[str] = None) -> None:
        """Set execution context for hook matching. Called before each command execution."""
        self._current_function = function_name
        self._current_return_type = return_type

    def apply_transform(self, event: str, content: str) -> str:
        """Run matching hooks in order, each receiving and returning a string.

        Uses internal context (current_function, current_return_type) for matching.
        Contract: str -> str. If a hook returns non-str or raises, it is skipped.
        """
        for hook in self._matching_hooks(event):
            try:
                result = hook.function(content)
                if isinstance(result, str):
                    content = result
                else:
                    logger.warning(
                        f"Hook '{hook.name}' returned {type(result).__name__} instead of str, skipping"
                    )
            except Exception as e:
                logger.warning(f"Hook '{hook.name}' raised {type(e).__name__}: {e}")
        return content

    def _matching_hooks(self, event: str) -> List[HookDefinition]:
        """Return hooks that match the given event and current context."""
        matches = []
        for hook in self._hooks_by_event.get(event, []):
            if hook.filter_return_type and self._current_return_type:
                if hook.filter_return_type != self._current_return_type:
                    continue
            elif hook.filter_return_type and not self._current_return_type:
                continue

            if hook.filter_function and self._current_function:
                if not fnmatch.fnmatch(self._current_function, hook.filter_function):
                    continue
            elif hook.filter_function and not self._current_function:
                continue

            matches.append(hook)
        return matches
