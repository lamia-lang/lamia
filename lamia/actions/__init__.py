"""Action namespace objects for .hu scripts with excellent IntelliSense support."""

from .web import WebActions
from .http import HttpActions
from .file import FileActions

# Create singleton namespace instances for .hu script injection
web = WebActions()
http = HttpActions()
file = FileActions()

__all__ = ['web', 'http', 'file']