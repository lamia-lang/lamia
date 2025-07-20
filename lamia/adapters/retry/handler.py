"""Retry wrapper and factory for adapters with external system retry capabilities."""

from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Type, TypeVar, Generic, Dict, List, Callable, Awaitable, Any
import time
import asyncio

from .base import BaseAdapter
from .infrastructure import ExternalSystemRetryConfig, ExternalSystemError, RetryHandler, ErrorCategory, get_default_config
from .llm import BaseLLMAdapter, LLMModel, LLMResponse
from .llm.openai import OpenAIAdapter

T = TypeVar('T')

@dataclass
class RetryStats:
    """Statistics for retry operations."""
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    total_retries: int = 0
    total_operation_time: float = 0.0
    errors_by_type: Dict[str, int] = field(default_factory=dict)
    error_history: List[Dict] = field(default_factory=list)
    last_error_time: Optional[datetime] = None

class RetryHandler:
    """Handles retry logic and statistics for external system operations."""
    
    def __init__(
        self,
        config: Optional[ExternalSystemRetryConfig] = None,
        collect_stats: bool = True
    ):
        self.config = config or get_default_config()
        self.stats = RetryStats() if collect_stats else None

    async def execute(
        self,
        operation: Callable[[], Awaitable[T]]
    ) -> T:
        """Execute operation with retries and stat collection."""
        start_time = time.time()
        attempts = 0

        while True:
            try:
                result = await operation()
                
                if self.stats:
                    operation_time = time.time() - start_time
                    self.stats.total_operations += 1
                    self.stats.successful_operations += 1
                    self.stats.total_retries += attempts
                    self.stats.total_operation_time += operation_time
                
                return result

            except Exception as e:
                attempts += 1
                error_category = self._classify_error(e)
                
                if self.stats:
                    error_type = type(e).__name__
                    self.stats.errors_by_type[error_type] = (
                        self.stats.errors_by_type.get(error_type, 0) + 1
                    )
                    self.stats.last_error_time = datetime.now()
                    self.stats.error_history.append({
                        'time': self.stats.last_error_time,
                        'error_type': error_type,
                        'error_message': str(e),
                        'attempt': attempts
                    })

                if error_category == ErrorCategory.PERMANENT or attempts >= self.config.max_attempts:
                    if self.stats:
                        self.stats.total_operations += 1
                        self.stats.failed_operations += 1
                        self.stats.total_retries += attempts - 1
                        self.stats.total_operation_time += time.time() - start_time
                    raise

                delay = self._calculate_delay(attempts, error_category)
                await asyncio.sleep(delay)

    def get_stats(self) -> Optional[RetryStats]:
        """Get current retry statistics if enabled."""
        return self.stats

class RetryWrappedAdapter(Generic[T]):
    """Wrapper that adds retry capabilities and statistics to any adapter."""

    def __init__(
        self,
        adapter: BaseAdapter,
        retry_config: Optional[ExternalSystemRetryConfig] = None,
        collect_stats: bool = True
    ):
        """Initialize the retry wrapper.
        
        Args:
            adapter: The base adapter to wrap
            retry_config: Optional retry configuration. If not provided, defaults will be used
                based on the adapter type.
            collect_stats: Whether to collect retry and performance statistics
        """
        self.adapter = adapter
        self.retry_handler = RetryHandler(retry_config, collect_stats)
        self.stats = RetryStats() if collect_stats else None

    async def execute(
        self,
        operation: Callable[[], Awaitable[T]]
    ) -> T:
        """Execute an operation with retry handling and statistics collection."""
        start_time = time.time()
        retries = 0
        
        try:
            result = await self.retry_handler.execute(operation)
            operation_time = time.time() - start_time
            
            if self.stats:
                self.stats.record_success(operation_time, retries)
            
            return result
            
        except ExternalSystemError as e:
            operation_time = time.time() - start_time
            if self.stats:
                self.stats.record_failure(e, operation_time, retries)
            raise

    def get_stats(self) -> Optional[RetryStats]:
        """Get the current retry statistics if enabled."""
        return self.stats

class RetryWrappedLLMAdapter(BaseLLMAdapter):
    def __init__(
        self,
        adapter: BaseLLMAdapter,
        retry_config: Optional[ExternalSystemRetryConfig] = None,
        collect_stats: bool = True
    ):
        self._adapter = adapter
        self._retry_handler = RetryHandler(retry_config, collect_stats)
    
    async def execute_prompt(self, prompt: str, model: Optional[LLMModel] = None) -> LLMResponse:
        return await self._retry_handler.execute(
            lambda: self._adapter.execute_prompt(prompt, model)
        )
    
    def get_stats(self) -> Optional[RetryStats]:
        return self._retry_handler.get_stats()