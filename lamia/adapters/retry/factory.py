"""Factory for creating retry-enabled adapters."""

from typing import Optional, Type, TypeVar, cast

from ..base import BaseAdapter
from ..llm.base import BaseLLMAdapter
from ..filesystem.base import BaseFSAdapter
from .config import ExternalSystemRetryConfig
from .wrappers import RetryWrappedLLMAdapter, RetryWrappedFSAdapter

T = TypeVar('T', bound=BaseAdapter)

class AdapterFactory:
    """Factory for creating adapters with optional retry capabilities."""
    
    _enable_retries: bool = True
    _collect_stats: bool = True
    
    @classmethod
    def configure(
        cls,
        enable_retries: Optional[bool] = None,
        collect_stats: Optional[bool] = None
    ) -> None:
        """Configure global factory behavior.
        
        Args:
            enable_retries: Whether to enable retry wrapping globally
            collect_stats: Whether to collect retry statistics globally
        """
        if enable_retries is not None:
            cls._enable_retries = enable_retries
        if collect_stats is not None:
            cls._collect_stats = collect_stats
    
    @classmethod
    def create_llm_adapter(
        cls,
        adapter_type: Type[BaseLLMAdapter],
        retry_config: Optional[ExternalSystemRetryConfig] = None,
        **adapter_kwargs
    ) -> BaseLLMAdapter:
        """Create an LLM adapter with optional retry capabilities.
        
        Args:
            adapter_type: The LLM adapter class to instantiate
            retry_config: Optional retry configuration
            **adapter_kwargs: Additional arguments for the adapter
            
        Returns:
            An LLM adapter, optionally wrapped with retry handling
        """
        adapter = adapter_type(**adapter_kwargs)
        if cls._enable_retries:
            return RetryWrappedLLMAdapter(
                adapter,
                retry_config,
                collect_stats=cls._collect_stats
            )
        return adapter
    
    @classmethod
    def create_fs_adapter(
        cls,
        adapter_type: Type[BaseFSAdapter],
        retry_config: Optional[ExternalSystemRetryConfig] = None,
        **adapter_kwargs
    ) -> BaseFSAdapter:
        """Create a filesystem adapter with optional retry capabilities.
        
        Args:
            adapter_type: The filesystem adapter class to instantiate
            retry_config: Optional retry configuration
            **adapter_kwargs: Additional arguments for the adapter
            
        Returns:
            A filesystem adapter, optionally wrapped with retry handling
        """
        adapter = adapter_type(**adapter_kwargs)
        if cls._enable_retries:
            return RetryWrappedFSAdapter(
                adapter,
                retry_config,
                collect_stats=cls._collect_stats
            )
        return adapter
    
    @classmethod
    def create_adapter(
        cls,
        adapter_type: Type[T],
        retry_config: Optional[ExternalSystemRetryConfig] = None,
        **adapter_kwargs
    ) -> T:
        """Create any adapter type with appropriate retry wrapping.
        
        This method automatically detects the adapter type and applies
        the appropriate retry wrapper.
        
        Args:
            adapter_type: The adapter class to instantiate
            retry_config: Optional retry configuration
            **adapter_kwargs: Additional arguments for the adapter
            
        Returns:
            An adapter of the requested type, optionally wrapped with retry handling
        """
        if issubclass(adapter_type, BaseLLMAdapter):
            return cast(T, cls.create_llm_adapter(
                cast(Type[BaseLLMAdapter], adapter_type),
                retry_config,
                **adapter_kwargs
            ))
        elif issubclass(adapter_type, BaseFSAdapter):
            return cast(T, cls.create_fs_adapter(
                cast(Type[BaseFSAdapter], adapter_type),
                retry_config,
                **adapter_kwargs
            ))
        else:
            # For now, return raw adapter if type is unknown
            return adapter_type(**adapter_kwargs) 