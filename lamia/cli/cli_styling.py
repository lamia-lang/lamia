"""CLI logging setup — separates Lamia internal logs from user-facing output.

Default behaviour (no flags):
    Console  → only WARNING and above from Lamia internals
    Log file → everything (DEBUG+), written to .lamia/lamia.log

With --verbose / -v:
    Console  → all Lamia logs (same format as the file)
    Log file → everything

With --log-file <path>:
    Override the default .lamia/lamia.log location.

Script print() statements always go to stdout undecorated.
"""

import logging
import os
import sys
from pathlib import Path

LAMIA_LOG_DIR = ".lamia"
LAMIA_LOG_FILE = "lamia.log"


class Colors:
    GREY = "\033[90m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    RESET = "\033[0m"


class ColoredFormatter(logging.Formatter):
    """Adds ANSI colors when output is a TTY."""

    COLORS = {
        "DEBUG": Colors.GREY,
        "INFO": "",
        "WARNING": Colors.YELLOW,
        "ERROR": Colors.RED,
        "CRITICAL": Colors.RED,
    }

    def format(self, record: logging.LogRecord) -> str:
        if sys.stderr.isatty():
            color = self.COLORS.get(record.levelname, "")
            if color:
                record.levelname = f"{color}{record.levelname}{Colors.RESET}"
                record.msg = f"{color}{record.msg}{Colors.RESET}"
        return super().format(record)


def setup_cli_logging(
    level: str = "INFO",
    verbose: bool = False,
    log_file: str | None = None,
) -> None:
    """Configure logging for CLI execution.

    Args:
        level: Minimum level for the *file* handler (always captures everything
               at this level and above).  Defaults to INFO.
        verbose: When True, the console also shows all log levels.
        log_file: Custom path for the log file.  Defaults to .lamia/lamia.log.
    """
    file_level = getattr(logging, level.upper(), logging.INFO)

    # Silence all third-party loggers at the root — any library that propagates
    # to root is covered without hardcoding package names.
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)
    for hdlr in root_logger.handlers[:]:
        root_logger.removeHandler(hdlr)

    lamia_logger = logging.getLogger("lamia")
    lamia_logger.setLevel(logging.DEBUG)
    lamia_logger.propagate = False  # set early so handlers below are the only path

    for hdlr in lamia_logger.handlers[:]:
        lamia_logger.removeHandler(hdlr)

    # --- File handler: captures everything ----------------------------------
    log_path = Path(log_file) if log_file else Path(LAMIA_LOG_DIR) / LAMIA_LOG_FILE
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(str(log_path), encoding="utf-8")
    file_handler.setLevel(file_level)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    lamia_logger.addHandler(file_handler)

    # --- Console (stderr) handler -------------------------------------------
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(file_level if verbose else logging.WARNING)
    console_handler.setFormatter(
        ColoredFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    lamia_logger.addHandler(console_handler)
