"""Tests for lamia.triggers.event_sources.email_poller — EmailEventSource."""

import email.mime.base
import email.mime.multipart
import email.mime.text
import imaplib
from unittest.mock import MagicMock, patch

import pytest

from lamia.triggers.local import registry
from lamia.triggers.local.event_sources.email_poller import (
    EmailEventSource,
    _build_imap_search,
)


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


def _multipart_message(
    message_id: str,
    subject: str = "multi",
    sender: str = "a@b.com",
    plain_body: str = "plain part",
    html_body: str = "<p>html part</p>",
) -> bytes:
    msg = email.mime.multipart.MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = "me@here.com"
    msg["Subject"] = subject
    msg["Message-ID"] = message_id
    msg["Date"] = "Fri, 21 Nov 2025 09:00:00 +0000"
    msg.attach(email.mime.text.MIMEText(plain_body, "plain"))
    msg.attach(email.mime.text.MIMEText(html_body, "html"))
    return msg.as_bytes()


def _message_with_attachment(
    message_id: str,
    subject: str = "with attachment",
    sender: str = "a@b.com",
    body: str = "see attached",
    filename: str = "report.pdf",
    attachment_data: bytes = b"fake pdf data",
) -> bytes:
    msg = email.mime.multipart.MIMEMultipart("mixed")
    msg["From"] = sender
    msg["To"] = "me@here.com"
    msg["Subject"] = subject
    msg["Message-ID"] = message_id
    msg["Date"] = "Fri, 21 Nov 2025 09:00:00 +0000"
    msg.attach(email.mime.text.MIMEText(body, "plain"))
    att = email.mime.base.MIMEBase("application", "octet-stream")
    att.set_payload(attachment_data)
    att.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(att)
    return msg.as_bytes()


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


# ---------------------------------------------------------------------------
# IMAP search filter construction
# ---------------------------------------------------------------------------

class TestBuildImapSearch:
    def test_unseen_only_by_default(self):
        assert _build_imap_search({}) == "UNSEEN"

    def test_to_filter(self):
        result = _build_imap_search({"to": "pricing@co.com"})
        assert result == 'UNSEEN TO "pricing@co.com"'

    def test_from_domain_filter(self):
        result = _build_imap_search({"from_domain": "bigcorp.com"})
        assert result == 'UNSEEN FROM "@bigcorp.com"'

    def test_subject_contains_filter(self):
        result = _build_imap_search({"subject_contains": "invoice"})
        assert result == 'UNSEEN SUBJECT "invoice"'

    def test_combined_filters(self):
        result = _build_imap_search({
            "to": "sales@co.com",
            "from_domain": "enterprise.com",
            "subject_contains": "quote",
        })
        assert 'TO "sales@co.com"' in result
        assert 'FROM "@enterprise.com"' in result
        assert 'SUBJECT "quote"' in result
        assert result.startswith("UNSEEN")

    def test_ignores_unknown_keys(self):
        result = _build_imap_search({"to": "x@y.com", "bogus": "ignored"})
        assert "bogus" not in result
        assert 'TO "x@y.com"' in result


# ---------------------------------------------------------------------------
# Connection configuration
# ---------------------------------------------------------------------------

class TestEmailConnection:
    def test_default_host_and_port(self):
        conn = _fake_imap([])
        with patch("imaplib.IMAP4_SSL", return_value=conn) as imap_cls:
            src = EmailEventSource("t-1")
            src.start({"username": "u@gmail.com", "password_env": "NO_ENV"})
            src.stop()

        imap_cls.assert_called_once_with("imap.gmail.com", 993)

    def test_custom_host_and_port(self):
        conn = _fake_imap([])
        with patch("imaplib.IMAP4_SSL", return_value=conn) as imap_cls:
            src = EmailEventSource("t-2")
            src.start({"host": "mail.company.com", "port": "995", "username": "u", "password_env": "NO_ENV"})
            src.stop()

        imap_cls.assert_called_once_with("mail.company.com", 995)

    def test_login_called_with_username_and_password(self, monkeypatch):
        monkeypatch.setenv("MY_PASS", "s3cret")
        conn = _fake_imap([])
        with patch("imaplib.IMAP4_SSL", return_value=conn):
            src = EmailEventSource("t-3")
            src.start({"username": "user@co.com", "password_env": "MY_PASS"})
            src.stop()

        conn.login.assert_called_once_with("user@co.com", "s3cret")

    def test_custom_label_selects_folder(self):
        conn = _fake_imap([])
        with patch("imaplib.IMAP4_SSL", return_value=conn):
            src = EmailEventSource("t-4")
            src.start({"username": "u", "password_env": "NO_ENV", "label": "Invoices"})
            src.stop()

        conn.select.assert_called_once_with("Invoices")

    def test_default_label_is_inbox(self):
        conn = _fake_imap([])
        with patch("imaplib.IMAP4_SSL", return_value=conn):
            src = EmailEventSource("t-5")
            src.start({"username": "u", "password_env": "NO_ENV"})
            src.stop()

        conn.select.assert_called_once_with("INBOX")


# ---------------------------------------------------------------------------
# Message parsing
# ---------------------------------------------------------------------------

class TestMessageParsing:
    def test_plain_text_message(self):
        raw = _raw_message("<plain@host>", subject="Hello", sender="alice@co.com")
        conn = _fake_imap([(b"1", raw)])
        with patch("imaplib.IMAP4_SSL", return_value=conn):
            src = EmailEventSource("t-parse-1")
            src.start({"username": "u", "password_env": "NO_ENV"})
            event = src._poll_once()
            src.stop()

        assert event is not None
        assert event["sender"] == "alice@co.com"
        assert event["subject"] == "Hello"
        assert event["body"] == "body text\r\n"
        assert event["message_id"] == "<plain@host>"
        assert event["html_body"] == ""
        assert event["attachments"] == []
        assert "timestamp" in event

    def test_multipart_message_extracts_both_parts(self):
        raw = _multipart_message(
            "<multi@host>",
            plain_body="plain version",
            html_body="<b>bold</b>",
        )
        conn = _fake_imap([(b"1", raw)])
        with patch("imaplib.IMAP4_SSL", return_value=conn):
            src = EmailEventSource("t-parse-2")
            src.start({"username": "u", "password_env": "NO_ENV"})
            event = src._poll_once()
            src.stop()

        assert event["body"] == "plain version"
        assert event["html_body"] == "<b>bold</b>"

    def test_attachment_extraction(self):
        raw = _message_with_attachment(
            "<att@host>",
            filename="report.pdf",
            attachment_data=b"x" * 1024,
        )
        conn = _fake_imap([(b"1", raw)])
        with patch("imaplib.IMAP4_SSL", return_value=conn):
            src = EmailEventSource("t-parse-3")
            src.start({"username": "u", "password_env": "NO_ENV"})
            event = src._poll_once()
            src.stop()

        assert len(event["attachments"]) == 1
        assert event["attachments"][0]["name"] == "report.pdf"
        assert event["attachments"][0]["size"] == 1024


# ---------------------------------------------------------------------------
# Mark-as-read behavior
# ---------------------------------------------------------------------------

class TestMarkAsRead:
    def test_messages_marked_seen_after_fetch(self):
        raw = _raw_message("<mark@host>")
        conn = _fake_imap([(b"1", raw)])
        with patch("imaplib.IMAP4_SSL", return_value=conn):
            src = EmailEventSource("t-mark-1")
            src.start({"username": "u", "password_env": "NO_ENV"})
            src._poll_once()
            src.stop()

        conn.store.assert_called_once_with(b"1", "+FLAGS", "\\Seen")


# ---------------------------------------------------------------------------
# Reconnection on IMAP errors
# ---------------------------------------------------------------------------

class TestReconnection:
    def test_reconnects_after_search_error(self):
        conn = _fake_imap([])
        conn.search.side_effect = [
            imaplib.IMAP4.error("connection reset"),
            ("OK", [b""]),
        ]
        with patch("imaplib.IMAP4_SSL", return_value=conn):
            src = EmailEventSource("t-recon-1")
            src.start({"username": "u", "password_env": "NO_ENV"})

            result1 = src._poll_once()
            assert result1 is None
            assert src._connection is None

            result2 = src._poll_once()
            assert result2 is None
            src.stop()

    def test_reconnects_after_fetch_error(self):
        raw = _raw_message("<fetch-err@host>")
        conn = _fake_imap([(b"1", raw)])
        conn.fetch.side_effect = OSError("broken pipe")

        with patch("imaplib.IMAP4_SSL", return_value=conn):
            src = EmailEventSource("t-recon-2")
            src.start({"username": "u", "password_env": "NO_ENV"})
            result = src._poll_once()
            src.stop()

        assert result is None
        conn.logout.assert_called()


# ---------------------------------------------------------------------------
# Dedup persistence (carried from original tests)
# ---------------------------------------------------------------------------

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

    def test_different_trigger_ids_have_separate_dedup(self):
        raw = _raw_message("<shared@host>")
        config = {"host": "imap.test", "username": "u", "password_env": "NO_ENV"}

        conn1 = _fake_imap([(b"1", raw)])
        with patch("imaplib.IMAP4_SSL", return_value=conn1):
            src1 = EmailEventSource("trigger-A")
            src1.start(config)
            result1 = src1._poll_once()
            src1.stop()

        conn2 = _fake_imap([(b"1", raw)])
        with patch("imaplib.IMAP4_SSL", return_value=conn2):
            src2 = EmailEventSource("trigger-B")
            src2.start(config)
            result2 = src2._poll_once()
            src2.stop()

        assert result1 is not None
        assert result2 is not None, "different trigger_id must not share dedup state"


# ---------------------------------------------------------------------------
# Burst polling (carried from original tests)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Timeout / empty mailbox
# ---------------------------------------------------------------------------

class TestWaitForEventTimeout:
    def test_returns_none_on_empty_mailbox(self):
        conn = _fake_imap([])
        with patch("imaplib.IMAP4_SSL", return_value=conn):
            src = EmailEventSource("t-timeout-1")
            src.start({"username": "u", "password_env": "NO_ENV"})
            result = src.wait_for_event(timeout_seconds=1)
            src.stop()

        assert result is None

    def test_stop_is_idempotent(self):
        conn = _fake_imap([])
        with patch("imaplib.IMAP4_SSL", return_value=conn):
            src = EmailEventSource("t-timeout-2")
            src.start({"username": "u", "password_env": "NO_ENV"})
            src.stop()
            src.stop()


# ---------------------------------------------------------------------------
# Config merging (orchestrator reads config.yaml, merges into trigger_config)
# ---------------------------------------------------------------------------

class TestConfigMerge:
    """Verify that _get_email_config loads the triggers.email section from config.yaml."""

    def test_loads_email_config_from_yaml(self, tmp_path):
        from lamia.triggers.local.orchestrator import _get_email_config

        config_yaml = tmp_path / "config.yaml"
        config_yaml.write_text(
            "triggers:\n"
            "  email:\n"
            "    host: imap.outlook.com\n"
            "    username: me@outlook.com\n"
            "    password_env: OUTLOOK_PASS\n"
            "    poll_interval: 60\n"
        )
        result = _get_email_config(project_root=tmp_path)
        assert result["host"] == "imap.outlook.com"
        assert result["username"] == "me@outlook.com"
        assert result["password_env"] == "OUTLOOK_PASS"
        assert result["poll_interval"] == 60

    def test_returns_empty_when_no_config(self, tmp_path):
        from lamia.triggers.local.orchestrator import _get_email_config

        result = _get_email_config(project_root=tmp_path)
        assert result == {}

    def test_returns_empty_when_no_triggers_section(self, tmp_path):
        from lamia.triggers.local.orchestrator import _get_email_config

        config_yaml = tmp_path / "config.yaml"
        config_yaml.write_text("model_chain:\n  - name: anthropic:claude\n")
        result = _get_email_config(project_root=tmp_path)
        assert result == {}
