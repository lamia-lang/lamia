"""Retry wrapper for LLM adapters."""

from typing import Optional

from ...llm.base import BaseLLMAdapter
from ...llm.base import LLMModel, LLMResponse
from ..retry_handler import RetryHandler
from lamia.types import ExternalOperationRetryConfig

class RetryingLLMAdapter(BaseLLMAdapter):
    """Adds retry capabilities to LLM adapters.
    
    Automatically configures industry-standard retry settings optimized
    for LLM operations with rate limiting and error handling.
    """
    
    def __init__(
        self,
        adapter: BaseLLMAdapter,
        retry_config: Optional[ExternalOperationRetryConfig] = None,
        collect_stats: bool = True
    ):
        """Initialize the retry wrapper.
        
        Args:
            adapter: The LLM adapter to wrap
            retry_config: Optional retry configuration (uses LLM defaults if None)
            collect_stats: Whether to collect retry statistics
        """
        self._adapter = adapter
        self._retry_handler = RetryHandler(
            adapter=adapter,  # Pass adapter for intelligent defaults
            config=retry_config,
            collect_stats=collect_stats
        )

    @classmethod
    def name(cls) -> str:
        """This method should not be called on the wrapper class."""
        raise NotImplementedError("This method should not be called on the wrapper class.")
    
    @classmethod
    def env_var_names(cls) -> list[str]:
        """This method should not be called on the wrapper class."""
        raise NotImplementedError("This method should not be called on the wrapper class.")
    
    @classmethod
    def is_remote(cls) -> bool:
        """This method should not be called on the wrapper class."""
        raise NotImplementedError("This method should not be called on the wrapper class.")
    
    @property
    def has_context_memory(self) -> bool:
        """Check if the adapter has context memory."""
        return self._adapter.has_context_memory
    
    async def generate(
        self,
        prompt: str,
        model: Optional[LLMModel] = None
    ) -> LLMResponse:
        """Execute prompt with retry handling.
        
        Uses industry-standard retry logic optimized for LLM APIs:
        - 5 max attempts
        - 2-60 second exponential backoff
        - Rate limit detection and extended delays
        
        Args:
            prompt: The input prompt
            model: Optional model override
            
        Returns:
            LLMResponse containing the generated text and metadata
        """
        return await self._retry_handler.execute(
            lambda: self._adapter.generate(prompt, model)
        )
    
    def get_stats(self):
        """Get retry statistics if enabled."""
        return self._retry_handler.get_stats()
    
    async def close(self) -> None:
        """Close the retry wrapper."""
        await self._adapter.close()