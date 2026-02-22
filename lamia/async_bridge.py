"""Persistent background event loop for sync-to-async bridges.

All sync code that needs to call async coroutines (Lamia.run(), WebActions,
session context, etc.) dispatches work to a single long-lived event loop
running in a daemon thread.  This guarantees that cached async resources
(aiohttp sessions, SDK clients) are never orphaned by a closed loop.
"""

import asyncio
import threading
from typing import TypeVar, Coroutine, Any

T = TypeVar("T")


class EventLoopManager:
    """Manages a persistent background event loop shared by all sync-to-async bridges."""

    _loop: asyncio.AbstractEventLoop | None = None
    _thread: threading.Thread | None = None
    _lock = threading.Lock()

    @classmethod
    def get_loop(cls) -> asyncio.AbstractEventLoop:
        """Return the shared event loop, creating it on first call."""
        with cls._lock:
            if cls._loop is None or cls._loop.is_closed():
                cls._loop = asyncio.new_event_loop()
                cls._thread = threading.Thread(
                    target=cls._loop.run_forever,
                    daemon=True,
                    name="lamia-event-loop",
                )
                cls._thread.start()
            return cls._loop

    @classmethod
    def run_coroutine(cls, coro: Coroutine[Any, Any, T]) -> T:
        """Submit *coro* to the persistent loop and block until it completes.

        Safe to call from any synchronous thread.  Raises whatever the
        coroutine raises.
        """
        loop = cls.get_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()

    @classmethod
    def shutdown(cls) -> None:
        """Stop the background loop and join the thread.

        Idempotent — safe to call multiple times or if never started.
        """
        with cls._lock:
            if cls._loop is not None and not cls._loop.is_closed():
                cls._loop.call_soon_threadsafe(cls._loop.stop)
                if cls._thread is not None:
                    cls._thread.join(timeout=5)
                cls._loop.close()
            cls._loop = None
            cls._thread = None
