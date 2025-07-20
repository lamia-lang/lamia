"""Retry wrapper for LLM adapters."""

from typing import Optional

from ...llm.base import BaseLLMAdapter
from ...llm.base import LLMModel, LLMResponse
from ..retry_handler import RetryHandler
from ..config import ExternalSystemRetryConfig

class RetryWrappedLLMAdapter(BaseLLMAdapter):
    """Adds retry capabilities to LLM adapters."""
    
    def __init__(
        self,
        adapter: BaseLLMAdapter,
        retry_config: Optional[ExternalSystemRetryConfig] = None,
        collect_stats: bool = True
    ):
        """Initialize the retry wrapper.
        
        Args:
            adapter: The LLM adapter to wrap
            retry_config: Optional retry configuration
            collect_stats: Whether to collect retry statistics
        """
        self._adapter = adapter
        self._retry_handler = RetryHandler(retry_config, collect_stats)

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
    
    async def generate(
        self,
        prompt: str,
        model: Optional[LLMModel] = None
    ) -> LLMResponse:
        """Execute prompt with retry handling.
        
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