"""Visual element picker for interactive selector resolution."""

from .picker import VisualElementPicker
from .strategies.singular_strategy import SingularSelectionStrategy
from .strategies.plural_strategy import PluralSelectionStrategy

__all__ = ['VisualElementPicker', 'SingularSelectionStrategy', 'PluralSelectionStrategy']