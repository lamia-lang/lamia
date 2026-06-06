from abc import ABC, abstractmethod
from typing import Any
from lamia.interpreter.commands import Command
from lamia.validation.base import BaseValidator
from typing import Generic, TypeVar
from lamia.hooks.runner import HookRunner

T = TypeVar('T', bound=Command)

_EMPTY_HOOK_RUNNER = HookRunner([])


class Manager(ABC, Generic[T]):
    """Abstract base class for all domain managers."""

    hook_runner: HookRunner = _EMPTY_HOOK_RUNNER
    
    @abstractmethod
    async def execute(self, command: T, validator: BaseValidator) -> Any:
        """Execute a request in this domain.

        Args:
            content: The content to process
            validator: The validator to use
        Returns:
            Domain-specific response
        """
        pass

    async def close(self) -> None:
        pass