"""Error classifier factory for different adapter types."""

from enum import Enum
from typing import Type, Dict

from .base import ErrorClassifier
from .http import HttpErrorClassifier
from .filesystem import FilesystemErrorClassifier


class ClassifierType(Enum):
    HTTP = "http"              # External HTTP/API calls (LLMs, web, REST APIs)
    FILESYSTEM = "filesystem"  # File operations (local/remote storage) 


# Classifier mapping - only for adapter types we actually have
_REGISTRY: Dict[str, Type[ErrorClassifier]] = {
    "http": HttpErrorClassifier,
    "filesystem": FilesystemErrorClassifier,
}


def get_error_classifier(system_type: str) -> ErrorClassifier:
    """Get error classifier for system type."""
    # Check for exact match first
    if system_type in _REGISTRY:
        return _REGISTRY[system_type]()
    
    # Simple pattern matching for actual adapter types
    system_lower = system_type.lower()
    if any(x in system_lower for x in ["file", "fs", "disk", "storage"]):
        return FilesystemErrorClassifier()
    
    # Default to HTTP for everything else (LLM, web, network, etc.)
    return HttpErrorClassifier()


def register_error_classifier(system_type: str, classifier_class: Type[ErrorClassifier]) -> None:
    """Register custom error classifier."""
    _REGISTRY[system_type] = classifier_class 