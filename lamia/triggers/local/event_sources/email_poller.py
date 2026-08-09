"""Email event source using IMAP polling.

Polls an IMAP mailbox at regular intervals for new messages matching
the trigger's filter configuration (to, from_domain, subject_contains, label).

Dedup is persisted via ``lamia.triggers.registry`` so a restart doesn't
re-fire messages that were already processed.
"""

import email
import email.utils
import imaplib
import os
import time
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from lamia.triggers.constants import EMAIL_POLL_INTERVAL_SECONDS
from lamia.triggers.local.event_sources.base import BaseEventSource
from lamia.triggers.local.registry import add_seen_message_id, get_seen_message_ids

FILTER_KEY_TO_IMAP_SEARCH = {
    "to": lambda v: f'TO "{v}"',
    "from_domain": lambda v: f'FROM "@{v}"',
    "subject_contains": lambda v: f'SUBJECT "{v}"',
}


def _build_imap_search(trigger_config: dict) -> str:
    """Build IMAP SEARCH criteria from trigger config kwargs."""
    criteria = ["UNSEEN"]
    for key, builder in FILTER_KEY_TO_IMAP_SEARCH.items():
        value = trigger_config.get(key)
        if value:
            criteria.append(builder(value))
    return " ".join(criteria)


class EmailEventSource(BaseEventSource):
    """Polls IMAP mailbox for new emails matching trigger filters.

    ``trigger_id`` is required so we can persist processed message-ids across
    orchestrator restarts.
    """

    def __init__(self, trigger_id: str):
        self._trigger_id = trigger_id
        self._config: dict = {}
        self._search_criteria: str = ""
        self._connection: Optional[imaplib.IMAP4_SSL] = None
        self._stopped = False
        self._seen_ids: set[str] = set()
        self._pending: deque[dict] = deque()

    def start(self, trigger_config: dict) -> None:
        self._config = trigger_config
        self._search_criteria = _build_imap_search(trigger_config)
        self._seen_ids = get_seen_message_ids(self._trigger_id)
        self._connect()

    def wait_for_event(self, timeout_seconds: int) -> Optional[dict]:
        # Drain anything already queued from a prior burst poll before hitting the network.
        if self._pending:
            return self._pending.popleft()

        deadline = time.time() + timeout_seconds
        poll_interval = self._config.get("poll_interval", EMAIL_POLL_INTERVAL_SECONDS)

        while time.time() < deadline and not self._stopped:
            self._poll_once()
            if self._pending:
                return self._pending.popleft()
            remaining = deadline - time.time()
            sleep_time = min(poll_interval, max(0, remaining))
            if sleep_time > 0:
                time.sleep(sleep_time)
        return None

    def stop(self) -> None:
        self._stopped = True
        self._disconnect()

    def _connect(self) -> None:
        host = self._config.get("host", "imap.gmail.com")
        port = int(self._config.get("port", 993))
        username = self._config.get("username", "")
        password_env = self._config.get("password_env", "IMAP_PASSWORD")
        password = os.environ.get(password_env, "")

        self._connection = imaplib.IMAP4_SSL(host, port)
        self._connection.login(username, password)

        folder = self._config.get("label", "INBOX")
        self._connection.select(folder)

    def _disconnect(self) -> None:
        if self._connection is not None:
            try:
                self._connection.logout()
            except Exception:
                pass
            self._connection = None

    def _poll_once(self) -> Optional[dict]:
        """Drain all matching messages into ``self._pending``.

        Returns the first newly-queued payload (mostly for tests / single-shot use),
        or ``None`` if nothing new was found. The remaining messages sit in
        ``self._pending`` and are served by subsequent ``wait_for_event`` calls
        without paying another poll interval.
        """
        if self._connection is None:
            try:
                self._connect()
            except Exception:
                return None

        try:
            _, data = self._connection.search(None, self._search_criteria)
        except (imaplib.IMAP4.error, OSError):
            self._disconnect()
            return None

        message_nums = data[0].split()
        if not message_nums:
            return None

        first_new: Optional[dict] = None
        for msg_num in message_nums:
            try:
                _, msg_data = self._connection.fetch(msg_num, "(RFC822)")
            except (imaplib.IMAP4.error, OSError):
                self._disconnect()
                break

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            message_id = msg.get("Message-ID", "")

            try:
                self._connection.store(msg_num, "+FLAGS", "\\Seen")
            except (imaplib.IMAP4.error, OSError):
                pass

            if message_id and message_id in self._seen_ids:
                continue

            payload = self._message_to_payload(msg)
            if message_id:
                self._seen_ids.add(message_id)
                add_seen_message_id(self._trigger_id, message_id)

            self._pending.append(payload)
            if first_new is None:
                first_new = payload

        return first_new

    def _message_to_payload(self, msg: email.message.Message) -> dict:
        body = ""
        html_body = ""
        attachments = []

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                disposition = str(part.get("Content-Disposition", ""))
                if "attachment" in disposition:
                    filename = part.get_filename() or "unnamed"
                    payload_bytes = part.get_payload(decode=True) or b""
                    attachments.append({"name": filename, "size": len(payload_bytes)})
                elif content_type == "text/plain" and not body:
                    body = (part.get_payload(decode=True) or b"").decode("utf-8", errors="replace")
                elif content_type == "text/html" and not html_body:
                    html_body = (part.get_payload(decode=True) or b"").decode("utf-8", errors="replace")
        else:
            body = (msg.get_payload(decode=True) or b"").decode("utf-8", errors="replace")

        date_str = msg.get("Date", "")
        parsed_date = email.utils.parsedate_to_datetime(date_str) if date_str else datetime.now(timezone.utc)
        timestamp = parsed_date.astimezone(timezone.utc).isoformat()

        return {
            "sender": msg.get("From", ""),
            "subject": msg.get("Subject", ""),
            "body": body,
            "html_body": html_body,
            "message_id": msg.get("Message-ID", ""),
            "thread_id": msg.get("In-Reply-To", ""),
            "timestamp": timestamp,
            "attachments": attachments,
            "labels": [],
        }
