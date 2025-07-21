from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional
from lamia import LLMModel

@dataclass
class LLMResponse:
    """Container for LLM response data."""
    text: str
    raw_response: Any
    usage: Dict[str, int]
    model: str

class BaseLLMAdapter(ABC):
    """Base interface for all LLM adapters."""
    
    @classmethod
    @abstractmethod
    def name(cls) -> str:
        """Return the provider name (e.g., 'openai', 'anthropic', 'ollama')."""
        pass
    
    @classmethod
    def env_var_names(cls) -> list[str]:
        """Return list of environment variable names to try, in order of precedence.
        
        Default implementation generates from provider name: {PROVIDER_NAME}_API_KEY
        Override this method for providers that use different or multiple env var names.
        """
        return [f"{cls.name().upper()}_API_KEY"]
    
    @classmethod
    @abstractmethod
    def is_remote(cls) -> bool:
        """Return True if this adapter makes network calls, False for local."""
        pass

    async def async_initialize(self) -> None:
        """Initialize any necessary asynchronous resources for the adapter.

        Subclasses that require asynchronous start-up (e.g. opening network
        sessions, loading local models) should override this method.  Adapters
        that don't need special preparation can rely on this default no-op
        implementation.
        """
        return

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: LLMModel
    ) -> LLMResponse:
        """Generate a response from the LLM.
        
        Pure adapter method - just implement the API call.
        
        Args:
            prompt: The input prompt text
            model: The LLM model configuration
            
        Returns:
            LLMResponse containing the generated text and metadata
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Cleanup any resources used by the adapter."""
        pass

    async def __aenter__(self):
        await self.async_initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close() 