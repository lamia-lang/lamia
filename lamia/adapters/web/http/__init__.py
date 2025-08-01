"""HTTP client adapters."""

from .base import BaseHttpAdapter
from .http_adapter import RequestsAdapter

__all__ = [
    'BaseHttpAdapter',
    'RequestsAdapter'
]
