"""
Environment variable loader for Lamia.

Automatically loads environment variables from .env file if present.
"""

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, skip loading
    pass