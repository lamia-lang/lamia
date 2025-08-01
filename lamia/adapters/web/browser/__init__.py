"""Browser automation adapters."""

from .base import BaseBrowserAdapter
from .selenium_adapter import SeleniumAdapter
from .playwright_adapter import PlaywrightAdapter

__all__ = [
    'BaseBrowserAdapter',
    'SeleniumAdapter', 
    'PlaywrightAdapter'
]
