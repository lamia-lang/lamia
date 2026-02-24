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
    record = make_record(logging.WARNING, "plain message")

    with patch("sys.stderr.isatty", return_value=False):
        output = formatter.format(record)

    assert Colors.RESET not in output


def test_formatter_colors_warning_in_tty():
    formatter = ColoredFormatter("%(levelname)s - %(message)s")
    record = make_record(logging.WARNING, "something went wrong")

    with patch("sys.stderr.isatty", return_value=True):
        output = formatter.format(record)

    assert Colors.YELLOW in output
    assert Colors.RESET in output


def test_formatter_colors_error_in_tty():
    formatter = ColoredFormatter("%(levelname)s - %(message)s")
    record = make_record(logging.ERROR, "fatal error")

    with patch("sys.stderr.isatty", return_value=True):
        output = formatter.format(record)

    assert Colors.RED in output
    assert Colors.RESET in output


def test_formatter_info_has_no_color_in_tty():
    """INFO level is intentionally uncolored — only level-based coloring."""
    formatter = ColoredFormatter("%(levelname)s - %(message)s")
    record = make_record(logging.INFO, "✅ All good")

    with patch("sys.stderr.isatty", return_value=True):
        output = formatter.format(record)

    assert Colors.GREEN not in output


def test_formatter_debug_gets_grey_in_tty():
    formatter = ColoredFormatter("%(levelname)s - %(message)s")
    record = make_record(logging.DEBUG, "[Lamia][Ask] prompt")

    with patch("sys.stderr.isatty", return_value=True):
        output = formatter.format(record)

    assert Colors.GREY in output
    assert Colors.RESET in output
