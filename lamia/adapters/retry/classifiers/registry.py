"""Simple error classifier registry."""

from enum import Enum
from typing import Type, Dict

from .base import ErrorClassifier
from .http import HttpErrorClassifier
from .filesystem import FilesystemErrorClassifier
from .local import LocalErrorClassifier


class ClassifierType(Enum):
    HTTP = "http"
    FILESYSTEM = "filesystem"
    LOCAL = "local"


# Simple registry mapping
_REGISTRY: Dict[str, Type[ErrorClassifier]] = {
    "http": HttpErrorClassifier,
    "filesystem": FilesystemErrorClassifier,
    "local": LocalErrorClassifier,
}


def get_error_classifier(system_type: str) -> ErrorClassifier:
    """Get error classifier for system type."""
    # Check for exact match first
    if system_type in _REGISTRY:
        return _REGISTRY[system_type]()
    
    # Simple pattern matching
    system_lower = system_type.lower()
    if any(x in system_lower for x in ["llm", "api", "http"]):
        return HttpErrorClassifier()
    elif any(x in system_lower for x in ["file", "fs", "disk"]):
        return FilesystemErrorClassifier()
    elif "local" in system_lower:
        return LocalErrorClassifier()
    
    # Default to HTTP
    return HttpErrorClassifier()


def register_error_classifier(system_type: str, classifier_class: Type[ErrorClassifier]) -> None:
    """Register custom error classifier."""
    _REGISTRY[system_type] = classifier_class 