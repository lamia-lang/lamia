"""Action namespace objects for .hu scripts"""

from .web import WebActions
from .http import HttpActions
from .file import FileActions
from .trigger import TriggerActions

# Create singleton namespace instances for .hu script injection
web = WebActions()
http = HttpActions()
file = FileActions()
trigger = TriggerActions()

__all__ = ['web', 'http', 'file', 'trigger']