"""Error classifiers for external operation failures."""

from .base import ErrorClassifier
from .http import HttpErrorClassifier
from .filesystem import FilesystemErrorClassifier  
from .self_hosted import SelfHostedLLMErrorClassifier 