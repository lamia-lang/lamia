"""Trigger interface — event-driven script execution with automatic param injection.

Usage in .lm scripts:
    trigger.email_received(sender, subject, body, to="pricing@company.com")
    print(f"From {sender}: {subject}")

    trigger.file_created(name, size, path="my-bucket")
    print(f"New file: {name} ({size} bytes)")

    # Reject an event that doesn't match runtime expectations:
    if not name.startswith(expected_prefix):
        trigger.reject()

The AST transformer rewrites trigger calls into variable assignments.
The function signatures exist for IDE autocomplete — showing all available fields.
String keyword arguments are infrastructure-level filters (prevent script launch).
"""

import json
import os
from typing import Optional

# Process exit code used when a script calls trigger.reject(). This is a
# cross-repo contract with lamia-cloud's GCP Workflow ACK/NACK logic
# (see lamia-cloud/src/gcp/README.md) — don't repurpose this value for
# unrelated errors, and don't change it without updating lamia-cloud too.
TRIGGER_REJECT_EXIT_CODE = 2


class TriggerRejectError(Exception):
    """Raised by trigger.reject() to signal that the current event should be
    skipped and the script should continue waiting for the next event.

    The workflow layer catches this (via TRIGGER_REJECT_EXIT_CODE) and acks
    the current message without processing, then loops back to pull the next.
    """


class TriggerActions:
    """Event-driven trigger interface. Singleton injected as `trigger` in scripts.

    Methods define available event fields via their signatures (for autocomplete).
    At runtime, _resolve() reads event data from LAMIA_TRIGGER_EVENT env var.
    String kwargs with values are infrastructure-level filters (not injected as variables).
    """

    def _resolve(self, method: str) -> dict:
        """Read event data from environment. Called by AST-transformed code."""
        raw = os.environ.get("LAMIA_TRIGGER_EVENT", "{}")
        return json.loads(raw)

    def reject(self) -> None:
        """Reject the most recent trigger event and keep waiting for the next one.

        Use when runtime logic determines this event doesn't belong to this
        execution. The event is acknowledged (won't return to this listener)
        and the script continues waiting for a matching event.
        """
        raise TriggerRejectError("Event rejected by script — waiting for next event")

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
        *,
        to: Optional[str] = None,
        from_domain: Optional[str] = None,
        subject_contains: Optional[str] = None,
        label: Optional[str] = None,
    ) -> None:
        """Trigger on email received.

        Positional params become local variables via AST transform.
        Keyword-only params (to, from_domain, etc.) are infra-level filters.
        """

    def file_created(
        self,
        name: Optional[str] = None,
        size: Optional[int] = None,
        content_type: Optional[str] = None,
        timestamp: Optional[str] = None,
        metadata: Optional[dict] = None,
        *,
        path: Optional[str] = None,
    ) -> None:
        """Trigger on file created. `path` is a filter (folder to watch)."""

    def file_modified(
        self,
        name: Optional[str] = None,
        size: Optional[int] = None,
        content_type: Optional[str] = None,
        timestamp: Optional[str] = None,
        metadata: Optional[dict] = None,
        *,
        path: Optional[str] = None,
    ) -> None:
        """Trigger on file modified. `path` is a filter (folder to watch)."""

    def file_deleted(
        self,
        name: Optional[str] = None,
        timestamp: Optional[str] = None,
        metadata: Optional[dict] = None,
        *,
        path: Optional[str] = None,
    ) -> None:
        """Trigger on file deleted. `path` is a filter (folder to watch)."""
