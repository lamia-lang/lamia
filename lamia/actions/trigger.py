"""Trigger interface — event-driven script execution with automatic param injection.

Usage in .lm scripts:
    trigger.email_received(sender, subject, body)
    print(f"From {sender}: {subject}")

    trigger.file_created(path="my-bucket", name, size)
    print(f"New file: {name} ({size} bytes)")

The AST transformer rewrites trigger calls into variable assignments.
The function signatures exist for IDE autocomplete — showing all available fields.
"""

import json
import os
from typing import Optional


class TriggerActions:
    """Event-driven trigger interface. Singleton injected as `trigger` in scripts.

    Methods define available event fields via their signatures (for autocomplete).
    At runtime, _resolve() reads event data from LAMIA_TRIGGER_EVENT env var.
    """

    def _resolve(self, method: str) -> dict:
        """Read event data from environment. Called by AST-transformed code."""
        raw = os.environ.get("LAMIA_TRIGGER_EVENT", "{}")
        return json.loads(raw)

    def email_received(
        self,
        sender: Optional[str] = None,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        html_body: Optional[str] = None,
        message_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        timestamp: Optional[str] = None,
        attachments: Optional[list] = None,
        labels: Optional[list] = None,
    ) -> None:
        """Trigger on email received. Params become local variables via AST transform."""

    def file_created(
        self,
        path: Optional[str] = None,
        name: Optional[str] = None,
        size: Optional[int] = None,
        content_type: Optional[str] = None,
        timestamp: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """Trigger on file created. `path` is a config param (bucket/directory filter)."""

    def file_modified(
        self,
        path: Optional[str] = None,
        name: Optional[str] = None,
        size: Optional[int] = None,
        content_type: Optional[str] = None,
        timestamp: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """Trigger on file modified. `path` is a config param (bucket/directory filter)."""

    def file_deleted(
        self,
        path: Optional[str] = None,
        name: Optional[str] = None,
        timestamp: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """Trigger on file deleted. `path` is a config param (bucket/directory filter)."""
