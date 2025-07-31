"""Factory for creating retry-enabled adapters."""

from typing import Optional, TypeVar, cast

from ..llm.base import BaseLLMAdapter
from ..filesystem.base import BaseFSAdapter
from ..web.browser.base import BaseBrowserAdapter
from lamia.types import ExternalOperationRetryConfig
from .adapter_wrappers.llm import RetryingLLMAdapter
from .adapter_wrappers.fs import RetryingFSAdapter
from .adapter_wrappers.browser import RetryingBrowserAdapter
from .defaults import get_default_config_for_adapter

T = TypeVar('T', bound=BaseLLMAdapter | BaseFSAdapter | BaseBrowserAdapter)

class RetriableAdapterFactory:
    """Factory for creating retriable adapters with intelligent retry configuration.
    
    This factory wraps adapters with retry capabilities, allowing for intelligent
    retry behavior that can be enabled/disabled and configured per adapter type.
    """
    
    _collect_stats: bool = True
    _retries_enabled: bool = True
    
    @classmethod
    def configure(
        cls,
        collect_stats: Optional[bool] = None,
        retries_enabled: Optional[bool] = None
    ) -> None:
        """Configure global factory behavior.
        
        Args:
            collect_stats: Whether to collect retry statistics globally
            retries_enabled: Whether retries are enabled globally
        """
        if collect_stats is not None:
            cls._collect_stats = collect_stats
        if retries_enabled is not None:
            cls._retries_enabled = retries_enabled
    
    @classmethod
    def _get_effective_config(
        cls,
        adapter,
        explicit_config: Optional[ExternalOperationRetryConfig] = None
    ) -> ExternalOperationRetryConfig:
        """Get effective retry configuration based on adapter type and global settings."""
        if explicit_config is not None:
            return explicit_config
            
        if not cls._retries_enabled:
            # Single attempt with intelligent defaults for other params
            base_config = get_default_config_for_adapter(adapter)
            return ExternalOperationRetryConfig(
                max_attempts=1,  # No retries
                base_delay=base_config.base_delay,
                max_delay=base_config.max_delay,
                exponential_base=base_config.exponential_base,
                max_total_duration=base_config.max_total_duration
            )
        
        # Use intelligent defaults based on adapter type
        return get_default_config_for_adapter(adapter)
    
    @classmethod
    def create_llm_adapter(
        cls,
        adapter: BaseLLMAdapter,
        retry_config: Optional[ExternalOperationRetryConfig] = None
    ) -> BaseLLMAdapter:
        """Create an LLM adapter with intelligent retry capabilities.
        
        Args:
            adapter: The LLM adapter instance to wrap
            retry_config: Optional explicit retry configuration
            
        Returns:
            The adapter wrapped with retry handling using intelligent defaults
        """
        effective_config = cls._get_effective_config(adapter, retry_config)
        return RetryingLLMAdapter(
            adapter,
            effective_config,
            collect_stats=cls._collect_stats
        )
    
    @classmethod
    def create_fs_adapter(
        cls,
        adapter: BaseFSAdapter,
        retry_config: Optional[ExternalOperationRetryConfig] = None
    ) -> BaseFSAdapter:
        """Create a filesystem adapter with intelligent retry capabilities.
        
        Args:
            adapter: The filesystem adapter instance to wrap
            retry_config: Optional explicit retry configuration
            
        Returns:
            The adapter wrapped with retry handling using intelligent defaults
        """
        effective_config = cls._get_effective_config(adapter, retry_config)
        return RetryingFSAdapter(
            adapter,
            effective_config,
            collect_stats=cls._collect_stats
        )
    
    @classmethod
    def create_browser_adapter(
        cls,
        adapter: BaseBrowserAdapter,
        retry_config: Optional[ExternalOperationRetryConfig] = None
    ) -> BaseBrowserAdapter:
        """Create a browser adapter with intelligent retry capabilities.
        
        Args:
            adapter: The browser adapter instance to wrap
            retry_config: Optional explicit retry configuration
            
        Returns:
            The adapter wrapped with retry handling using intelligent defaults
        """
        effective_config = cls._get_effective_config(adapter, retry_config)
        return RetryingBrowserAdapter(
            adapter,
            effective_config,
            collect_stats=cls._collect_stats
        )
    
    @classmethod
    def create_adapter(
        cls,
        adapter: T,
        retry_config: Optional[ExternalOperationRetryConfig] = None
    ) -> T:
        """Create any adapter type with appropriate retry wrapping.
        
        This method automatically detects the adapter type and applies
        the appropriate retry wrapper with intelligent configuration.
        
        Args:
            adapter: The adapter instance to wrap
            retry_config: Optional explicit retry configuration
            
        Returns:
            The adapter wrapped with retry handling if a wrapper exists,
            otherwise returns the original adapter
        """
        if isinstance(adapter, BaseLLMAdapter):
            return cast(T, cls.create_llm_adapter(adapter, retry_config))
        elif isinstance(adapter, BaseFSAdapter):
            return cast(T, cls.create_fs_adapter(adapter, retry_config))
        elif isinstance(adapter, BaseBrowserAdapter):
            return cast(T, cls.create_browser_adapter(adapter, retry_config))
        return adapter  # Return as-is if no wrapper available 