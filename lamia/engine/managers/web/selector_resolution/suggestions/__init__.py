"""AI-powered selector suggestions on failure.

This package provides intelligent selector suggestions when element finding fails.
Analyzes page HTML and operation type to suggest alternative selectors.
"""

from .suggestion_service import SelectorSuggestionService

__all__ = ['SelectorSuggestionService']




