from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

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

    @property
    @abstractmethod
    def has_context_memory(self) -> bool:
        """Whether the LLM adapter supports context memory (chat history)."""
        pass

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close() 