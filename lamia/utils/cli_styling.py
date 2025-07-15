import sys
import logging
from typing import Optional

# ANSI color codes
class Colors:
    GREY = "\033[90m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    RESET = "\033[0m"

class ColoredFormatter(logging.Formatter):
    """Custom formatter adding colors to log records when running in TTY mode."""
    
    COLORS = {
        'DEBUG': Colors.BLUE,
        'INFO': Colors.WHITE,
        'WARNING': Colors.YELLOW,
        'ERROR': Colors.RED,
        'CRITICAL': Colors.RED,
    }

    def format(self, record):
        # Add colors only if we're in a TTY
        if sys.stdout.isatty():
            # Color the levelname
            if record.levelname in self.COLORS:
                color = self.COLORS[record.levelname]
                record.levelname = f"{color}{record.levelname}{Colors.RESET}"
            
            # Color the message based on level
            if record.levelname in ['WARNING', 'ERROR', 'CRITICAL']:
                record.msg = f"{self.COLORS[record.levelname]}{record.msg}{Colors.RESET}"
            elif record.levelname == 'INFO' and '✅' in str(record.msg):
                # Success messages (with checkmark) in green
                record.msg = f"{Colors.GREEN}{record.msg}{Colors.RESET}"
            elif record.levelname == 'INFO' and '[Lamia][Ask]' in str(record.msg):
                # Grey out prompts
                record.msg = f"{Colors.GREY}{record.msg}{Colors.RESET}"
        
        return super().format(record)

def setup_cli_logging(level: str = 'INFO'):
    """
    Setup logging with colored output for CLI usage.
    This should only be called from the CLI entrypoint.
    When Lamia is used as a library, it will use the parent application's logger configuration.
    """
    formatter = ColoredFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove any existing handlers and add our colored handler
    for hdlr in root_logger.handlers[:]:
        root_logger.removeHandler(hdlr)
    root_logger.addHandler(handler) 