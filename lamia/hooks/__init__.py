"""Lamia hooks infrastructure.

Hooks are .lm functions with -> Hook(event, filter) return annotations.
They provide deterministic post-processing that runs before validation.

Currently supported events:
    post_llm — transforms LLM output (str -> str) before validation
"""

from dataclasses import dataclass
from typing import Callable, Optional, Set


class HookEvent:
    """Extensible hook event registry. New events are added via register()."""

    _registry: Set[str] = set()

    @classmethod
    def register(cls, event_name: str) -> str:
        cls._registry.add(event_name)
        return event_name

    @classmethod
    def is_valid(cls, event_name: str) -> bool:
        return event_name in cls._registry


POST_LLM = HookEvent.register("post_llm")


class Hook:
    """Return type marker for hook functions in .lm files.

    Usage:
        def normalize(content) -> Hook(post_llm):
            return content.replace('\\u2014', '-')

        def only_text(content) -> Hook(post_llm, TEXT):
            return content.strip()

        def for_func(content) -> Hook(post_llm, function='generate_description'):
            return content.replace('#', '')
    """

    def __init__(self, event: str, return_type=None, *, function: Optional[str] = None):
        self.event = event
        self.return_type = return_type
        self.function = function

    def __repr__(self):
        parts = [self.event]
        if self.return_type:
            parts.append(str(self.return_type))
        if self.function:
            parts.append(f"function={self.function!r}")
        return f"Hook({', '.join(parts)})"


@dataclass
class HookDefinition:
    """A discovered hook ready for execution."""
    event: str
    function: Callable
    name: str
    source_file: str
    filter_return_type: Optional[str] = None
    filter_function: Optional[str] = None
