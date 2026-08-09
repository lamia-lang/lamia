"""Tests for lamia.triggers.event_sources.email_poller — EmailEventSource."""

from unittest.mock import MagicMock, patch

import pytest

from lamia.triggers.local import registry
from lamia.triggers.local.event_sources.email_poller import EmailEventSource


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    """Point registry at a temp directory so seen_messages persistence is isolated."""
    monkeypatch.setattr(registry, "TRIGGERS_DIR", tmp_path)


def _raw_message(message_id: str, subject: str = "hi", sender: str = "x@y.com") -> bytes:
    return (
        f"From: {sender}\r\n"
        f"To: me@here.com\r\n"
        f"Subject: {subject}\r\n"
        f"Message-ID: {message_id}\r\n"
        f"Date: Fri, 21 Nov 2025 09:00:00 +0000\r\n"
        f"\r\n"
        f"body text\r\n"
    ).encode()


def _fake_imap(messages: list[tuple[bytes, bytes]]) -> MagicMock:
    """Build a fake IMAP connection.

    messages: list of (msg_num, raw_bytes) tuples the SEARCH should surface,
    fetched in order.
    """
    conn = MagicMock()
    conn.login.return_value = ("OK", [b""])
    conn.select.return_value = ("OK", [b""])
    nums = b" ".join(num for num, _ in messages)
    conn.search.return_value = ("OK", [nums])
    fetches = {num: raw for num, raw in messages}

    def fetch_side_effect(num, _spec):
        return ("OK", [(num, fetches[num])])

    conn.fetch.side_effect = fetch_side_effect
    return conn


class TestEmailDedupPersistence:
    """Issue #1: dedup must survive orchestrator restarts via registry."""

    def test_dedup_persists_across_source_restarts(self):
        """A second EmailEventSource with the same trigger_id must skip already-processed messages."""
        trigger_id = "test-trigger-1"
        raw = _raw_message("<msg-A@host>")
        config = {"host": "imap.test", "username": "u", "password_env": "NO_ENV"}

        conn = _fake_imap([(b"1", raw)])
        with patch("imaplib.IMAP4_SSL", return_value=conn):
            src1 = EmailEventSource(trigger_id)
            src1.start(config)
            first = src1._poll_once()
            src1.stop()

        assert first is not None
        assert first["message_id"] == "<msg-A@host>"

        # New source (as if orchestrator restarted). Same message must be skipped.
        conn2 = _fake_imap([(b"1", raw)])
        with patch("imaplib.IMAP4_SSL", return_value=conn2):
            src2 = EmailEventSource(trigger_id)
            src2.start(config)
            second = src2._poll_once()
            src2.stop()

        assert second is None, "restart must not re-fire an already-processed message"

    def test_seen_message_ids_are_written_to_registry(self):
        """After processing a message, the registry must record its message-id."""
        trigger_id = "test-trigger-2"
        raw = _raw_message("<msg-B@host>")
        config = {"host": "imap.test", "username": "u", "password_env": "NO_ENV"}

        conn = _fake_imap([(b"1", raw)])
        with patch("imaplib.IMAP4_SSL", return_value=conn):
            src = EmailEventSource(trigger_id)
            src.start(config)
            src._poll_once()
            src.stop()

        seen = registry.get_seen_message_ids(trigger_id)
        assert "<msg-B@host>" in seen


class TestEmailBurstPoll:
    """Issue #6: a single poll must drain all matching messages, not just one."""

    def test_burst_of_three_messages_all_returned_across_calls(self):
        """Three matching messages present at poll time — must all be surfaced without waiting for the next poll cycle."""
        trigger_id = "test-trigger-3"
        raws = [
            (b"1", _raw_message("<a@h>", subject="one")),
            (b"2", _raw_message("<b@h>", subject="two")),
            (b"3", _raw_message("<c@h>", subject="three")),
        ]
        config = {"host": "imap.test", "username": "u", "password_env": "NO_ENV"}

        conn = _fake_imap(raws)
        with patch("imaplib.IMAP4_SSL", return_value=conn):
            src = EmailEventSource(trigger_id)
            src.start(config)
            results = [src.wait_for_event(timeout_seconds=1) for _ in range(3)]
            src.stop()

        # SEARCH should have been called ONCE — burst drain, not one-per-poll-interval.
        assert conn.search.call_count == 1, (
            f"burst of 3 messages triggered {conn.search.call_count} SEARCH "
            "calls; a single poll should have drained them all"
        )
        ids = [r["message_id"] for r in results if r is not None]
        assert ids == ["<a@h>", "<b@h>", "<c@h>"]
