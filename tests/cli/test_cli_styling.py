import logging
from unittest.mock import patch

from lamia.cli.cli_styling import Colors, ColoredFormatter


def make_record(level: int, message: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="lamia.cli.test",
        level=level,
        pathname=__file__,
        lineno=10,
        msg=message,
        args=(),
        exc_info=None,
    )


def test_formatter_without_tty_keeps_plain_message():
    formatter = ColoredFormatter("%(levelname)s - %(message)s")
    record = make_record(logging.INFO, "plain message")

    with patch("sys.stdout.isatty", return_value=False):
        output = formatter.format(record)

    assert Colors.RESET not in output


def test_formatter_colors_success_message_in_tty():
    formatter = ColoredFormatter("%(levelname)s - %(message)s")
    record = make_record(logging.INFO, "✅ All good")

    with patch("sys.stdout.isatty", return_value=True):
        output = formatter.format(record)

    assert Colors.GREEN in output
    assert Colors.RESET in output


def test_formatter_greys_prompt_messages_in_tty():
    formatter = ColoredFormatter("%(levelname)s - %(message)s")
    record = make_record(logging.INFO, "[Lamia][Ask] prompt")

    with patch("sys.stdout.isatty", return_value=True):
        output = formatter.format(record)

    assert Colors.GREY in output
    assert Colors.RESET in output
