"""Selection strategies for different web method types."""

from .singular_strategy import SingularSelectionStrategy
from .plural_strategy import PluralSelectionStrategy
from .action_strategy import ActionSelectionHandler

__all__ = ['SingularSelectionStrategy', 'PluralSelectionStrategy', 'ActionSelectionHandler']