"""File system event source using watchdog.

Cross-platform: uses inotify (Linux), FSEvents (macOS), ReadDirectoryChangesW (Windows).
Supports file_created, file_modified, file_deleted trigger methods.
"""

import mimetypes
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Queue
from typing import Optional

from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from lamia.triggers.constants import FILE_DEBOUNCE_MS
from lamia.triggers.local.event_sources.base import BaseEventSource

TRIGGER_METHOD_TO_EVENT_CLASS = {
    "file_created": FileCreatedEvent,
    "file_modified": FileModifiedEvent,
    "file_deleted": FileDeletedEvent,
}


class _DebouncedHandler(FileSystemEventHandler):
    """Filters and debounces filesystem events before pushing to queue."""

    def __init__(self, event_class: type, queue: Queue):
        super().__init__()
        self._event_class = event_class
        self._queue = queue
        self._last_seen: dict[str, float] = {}
        self._debounce_seconds = FILE_DEBOUNCE_MS / 1000.0
        self._lock = threading.Lock()

    def on_any_event(self, event):
        if event.is_directory:
            return
        if not isinstance(event, self._event_class):
            return
        now = time.time()
        with self._lock:
            last = self._last_seen.get(event.src_path, 0.0)
            if now - last < self._debounce_seconds:
                return
            self._last_seen[event.src_path] = now
        self._queue.put(event)


class FileEventSource(BaseEventSource):
    """Watches a local directory for file system events."""

    def __init__(self, trigger_method: str):
        if trigger_method not in TRIGGER_METHOD_TO_EVENT_CLASS:
            raise ValueError(f"Unsupported file trigger method: {trigger_method}")
        self._trigger_method = trigger_method
        self._event_class = TRIGGER_METHOD_TO_EVENT_CLASS[trigger_method]
        self._observer: Optional[Observer] = None
        self._queue: Queue = Queue()
        self._watch_path: Optional[str] = None

    def start(self, trigger_config: dict) -> None:
        watch_path = trigger_config.get("path", ".")
        self._watch_path = str(Path(watch_path).expanduser().resolve())

        if not os.path.exists(self._watch_path):
            raise FileNotFoundError(
                f"Trigger path does not exist: {self._watch_path}"
            )
        if not os.path.isdir(self._watch_path):
            raise NotADirectoryError(
                f"Trigger path is not a directory: {self._watch_path}"
            )

        handler = _DebouncedHandler(self._event_class, self._queue)
        self._observer = Observer()
        self._observer.schedule(handler, self._watch_path, recursive=True)
        self._observer.start()

    def wait_for_event(self, timeout_seconds: int) -> Optional[dict]:
        try:
            event = self._queue.get(timeout=timeout_seconds)
        except Empty:
            return None
        return self._event_to_payload(event)

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None

    def _event_to_payload(self, event) -> dict:
        file_path = Path(event.src_path)
        try:
            stat = file_path.stat()
            size = stat.st_size
        except OSError:
            size = 0

        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"

        return {
            "name": file_path.name,
            "size": size,
            "content_type": content_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {"path": str(file_path)},
        }
