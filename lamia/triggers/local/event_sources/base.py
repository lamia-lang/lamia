"""Abstract base for trigger event sources."""

from abc import ABC, abstractmethod
from typing import Optional


class BaseEventSource(ABC):
    """Interface for event sources that supply trigger events.

    Implementations watch for specific event types (file changes, emails, etc.)
    and block until a matching event occurs or timeout is reached.
    """

    @abstractmethod
    def start(self, trigger_config: dict) -> None:
        """Begin watching for events matching the given trigger configuration.

        trigger_config contains the keyword arguments from the trigger call
        (e.g. path="/some/folder" for file triggers, to="x@co.com" for email).
        """
        ...

    @abstractmethod
    def wait_for_event(self, timeout_seconds: int) -> Optional[dict]:
        """Block until an event arrives or timeout expires.

        Returns the event payload dict if an event was received,
        or None if the timeout was reached without an event.
        """
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop watching and release resources."""
        ...
