"""Retry wrapper and factory for adapters with external system retry capabilities."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, TypeVar, Dict, List, Callable, Awaitable
import time
import asyncio
import aiohttp

from .config import ExternalSystemRetryConfig, ErrorCategory
from .errors import ExternalSystemError, ExternalSystemRetryError, ExternalSystemRateLimitError, ExternalSystemTransientError, ExternalSystemPermanentError
from .defaults import get_default_config


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
        external_system_type: str = "network",
        collect_stats: bool = True
    ):
        self.config = config or get_default_config(external_system_type)
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

                error_category = self._classify_error(e)
                if error_category == ErrorCategory.PERMANENT or attempts >= self.config.max_attempts:
                    if self.stats:
                        self.stats.total_operations += 1
                        self.stats.failed_operations += 1
                        self.stats.total_retries += attempts - 1
                        self.stats.total_operation_time += time.time() - start_time
                    
                    if error_category == ErrorCategory.PERMANENT:
                        raise ExternalSystemPermanentError(str(e), e)
                    elif error_category == ErrorCategory.RATE_LIMIT:
                        raise ExternalSystemRateLimitError(str(e), [], e)
                    elif error_category == ErrorCategory.TRANSIENT:
                        raise ExternalSystemTransientError(str(e), [], e)
                    else:
                        raise ExternalSystemRetryError(str(e), [], e)

                delay = self._calculate_delay(attempts, error_category)
                await asyncio.sleep(delay)

    def get_stats(self) -> Optional[RetryStats]:
        """Get current retry statistics if enabled."""
        return self.stats
    
    def _classify_error(self, error: Exception) -> ErrorCategory:
        """Classify an error to determine retry behavior."""
        error_msg = str(error).lower()
        
        # Check for rate limiting
        if (
            isinstance(error, aiohttp.ClientResponseError) and error.status == 429
            or "rate limit" in error_msg
            or "too many requests" in error_msg
            or "quota" in error_msg
        ):
            return ErrorCategory.RATE_LIMIT
        
        # Check for permanent errors (authentication, authorization, bad requests)
        if isinstance(error, aiohttp.ClientResponseError):
            if 400 <= error.status < 500 and error.status != 429:
                return ErrorCategory.PERMANENT
        
        if (
            "unauthorized" in error_msg
            or "forbidden" in error_msg
            or "invalid api key" in error_msg
            or "authentication" in error_msg
            or "invalid request" in error_msg
            or "bad request" in error_msg
        ):
            return ErrorCategory.PERMANENT
        
        # Check for transient errors (network, timeouts, server errors)
        if (
            isinstance(error, (
                aiohttp.ClientConnectorError,
                aiohttp.ClientConnectionError,
                aiohttp.ClientTimeout,
                aiohttp.ServerTimeoutError,
                ConnectionError,
                TimeoutError
            ))
            or (isinstance(error, aiohttp.ClientResponseError) and error.status >= 500)
            or "timeout" in error_msg
            or "connection" in error_msg
            or "network" in error_msg
            or "server error" in error_msg
            or "service unavailable" in error_msg
        ):
            return ErrorCategory.TRANSIENT
        
        # Default to transient for unknown errors (safer to retry)
        return ErrorCategory.TRANSIENT
    
    def _calculate_delay(self, attempts: int, error_category: ErrorCategory) -> float:
        """Calculate delay before next retry attempt."""
        base_delay = self.config.base_delay
        
        # Apply exponential backoff
        delay = base_delay * (self.config.exponential_base ** (attempts - 1))
        
        # Apply category-specific multipliers
        if error_category == ErrorCategory.RATE_LIMIT:
            delay *= 2.0  # Longer delays for rate limits
        elif error_category == ErrorCategory.TRANSIENT:
            delay *= 1.0  # Standard delay for transient errors
        
        # Cap at maximum delay
        return min(delay, self.config.max_delay)