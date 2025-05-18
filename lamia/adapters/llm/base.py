from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, TypeVar, Callable, Tuple
from functools import wraps
import importlib

T = TypeVar('T')

def lazy_import(module_name: str) -> Callable:
    """
    Decorator for lazy importing of optional dependencies.
    Will try HTTP fallback if import fails.
    
    Usage:
        @lazy_import("openai")
        def some_function(self, ...):
            # use openai here
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # Only import when the function is actually called
                globals()[module_name] = importlib.import_module(module_name)
                return func(*args, **kwargs)
            except ImportError:
                # Function should handle the case when self._use_sdk is False
                if hasattr(args[0], '_use_sdk'):
                    args[0]._use_sdk = False
                return func(*args, **kwargs)
        return wrapper
    return decorator

@dataclass
class LLMResponse:
    """Container for LLM response data."""
    text: str
    raw_response: Any
    usage: Dict[str, int]
    model: str

class BaseLLMAdapter(ABC):
    """Base interface for all LLM adapters."""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize any necessary resources for the adapter."""
        pass

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[list[str]] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate a response from the LLM.
        
        Args:
            prompt: The input prompt text
            temperature: Controls randomness in generation (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
            stop_sequences: List of sequences that will stop generation
            **kwargs: Additional model-specific parameters
            
        Returns:
            LLMResponse containing the generated text and metadata
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Cleanup any resources used by the adapter."""
        pass

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close() 