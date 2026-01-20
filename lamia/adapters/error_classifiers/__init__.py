"""Error classifiers for external operation failures."""

from .categories import ErrorCategory
from .base import ErrorClassifier
from .composite import CompositeErrorClassifier
from .http import HttpErrorClassifier  
from .filesystem import FilesystemErrorClassifier
from .self_hosted import SelfHostedLLMErrorClassifier
from .browser import BrowserErrorClassifier

__all__ = [
    'ErrorCategory',
    'ErrorClassifier',
    'CompositeErrorClassifier',
    'HttpErrorClassifier',
    'FilesystemErrorClassifier', 
    'SelfHostedLLMErrorClassifier',
    'BrowserErrorClassifier',
] 