"""Factory for creating retry-enabled adapters."""

from typing import Optional, TypeVar, cast

from ..llm.base import BaseLLMAdapter
from ..filesystem.base import BaseFSAdapter
from .config import ExternalSystemRetryConfig
from .adapter_wrappers.llm import RetryWrappedLLMAdapter
from .adapter_wrappers.fs import RetryWrappedFSAdapter

T = TypeVar('T', bound=BaseLLMAdapter | BaseFSAdapter)

class AdapterFactory:
    """Factory for creating retry-enabled adapters."""
    
    _collect_stats: bool = True
    
    @classmethod
    def configure(
        cls,
        collect_stats: Optional[bool] = None
    ) -> None:
        """Configure global factory behavior.
        
        Args:
            collect_stats: Whether to collect retry statistics globally
        """
        if collect_stats is not None:
            cls._collect_stats = collect_stats
    
    @classmethod
    def create_llm_adapter(
        cls,
        adapter: BaseLLMAdapter,
        retry_config: Optional[ExternalSystemRetryConfig] = None
    ) -> BaseLLMAdapter:
        """Create an LLM adapter with retry capabilities.
        
        Args:
            adapter: The LLM adapter instance to wrap
            retry_config: Optional retry configuration
            
        Returns:
            The adapter wrapped with retry handling
        """
        return RetryWrappedLLMAdapter(
            adapter,
            retry_config,
            collect_stats=cls._collect_stats
        )
    
    @classmethod
    def create_fs_adapter(
        cls,
        adapter: BaseFSAdapter,
        retry_config: Optional[ExternalSystemRetryConfig] = None
    ) -> BaseFSAdapter:
        """Create a filesystem adapter with retry capabilities.
        
        Args:
            adapter: The filesystem adapter instance to wrap
            retry_config: Optional retry configuration
            
        Returns:
            The adapter wrapped with retry handling
        """
        return RetryWrappedFSAdapter(
            adapter,
            retry_config,
            collect_stats=cls._collect_stats
        )
    
    @classmethod
    def create_adapter(
        cls,
        adapter: T,
        retry_config: Optional[ExternalSystemRetryConfig] = None
    ) -> T:
        """Create any adapter type with appropriate retry wrapping.
        
        This method automatically detects the adapter type and applies
        the appropriate retry wrapper.
        
        Args:
            adapter: The adapter instance to wrap
            retry_config: Optional retry configuration
            
        Returns:
            The adapter wrapped with retry handling if a wrapper exists,
            otherwise returns the original adapter
        """
        if isinstance(adapter, BaseLLMAdapter):
            return cast(T, cls.create_llm_adapter(adapter, retry_config))
        elif isinstance(adapter, BaseFSAdapter):
            return cast(T, cls.create_fs_adapter(adapter, retry_config))
        return adapter  # Return as-is if no wrapper available 