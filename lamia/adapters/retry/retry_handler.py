"""Retry wrapper and factory for adapters with external system retry capabilities."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, TypeVar, Dict, List, Callable, Awaitable, Union
import time
import asyncio

from lamia.errors import ExternalOperationError, ExternalOperationPermanentError, ExternalOperationRateLimitError, ExternalOperationTransientError, ExternalOperationFailedError
from .defaults import get_default_config_for_adapter
from lamia.types import ExternalOperationRetryConfig
from lamia.adapters.error_classifiers.categories import ErrorCategory
from lamia.adapters.llm.base import BaseLLMAdapter
from lamia.adapters.filesystem.base import BaseFSAdapter
from lamia.adapters.web.browser.base import BaseBrowserAdapter
from lamia.adapters.error_classifiers import HttpErrorClassifier, FilesystemErrorClassifier, SelfHostedLLMErrorClassifier, BrowserErrorClassifier, CompositeErrorClassifier
import logging

logger = logging.getLogger(__name__)

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
        adapter: Union[BaseLLMAdapter, BaseFSAdapter, BaseBrowserAdapter],
        config: Optional[ExternalOperationRetryConfig] = None,
        collect_stats: bool = True
    ):
        """Initialize retry handler.
        
        Args:
            adapter: The adapter instance to determine proper config/classifier
            config: Optional retry configuration
            collect_stats: Whether to collect retry statistics
        """
        self.config = config or get_default_config_for_adapter(adapter)
        self.error_classifier = _get_error_classifier_for_adapter(adapter)
        self.stats = RetryStats() if collect_stats else None

    async def execute(
        self,
        operation: Callable[[], Awaitable[T]]
    ) -> T:
        """Execute operation with retries and stat collection."""
        start_time = time.time()
        attempts = 0
        retry_history = []

        while True:
            try:
                logger.debug(f"External operation attempt {attempts + 1} of {self.config.max_attempts}")
                result = await operation()
                
                if self.stats:
                    operation_time = time.time() - start_time
                    self.stats.total_operations += 1
                    self.stats.successful_operations += 1
                    self.stats.total_retries += attempts
                    self.stats.total_operation_time += operation_time
                
                return result

            except ExternalOperationError as e:
                # External operation errors should be retried based on their type
                attempts += 1
                retry_history.append(f"Attempt {attempts}: {type(e).__name__}: {str(e)}")
                
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

                error_category = self._derive_error_category(e)
                logger.debug(f"External error classified as {error_category} on attempt {attempts}: {type(e).__name__}")
                
                should_abort = (
                    error_category == ErrorCategory.PERMANENT
                    or attempts >= self.config.max_attempts
                )

                if should_abort:
                    if self.stats:
                        self.stats.total_operations += 1
                        self.stats.failed_operations += 1
                        self.stats.total_retries += attempts - 1
                        self.stats.total_operation_time += time.time() - start_time

                    raise self._raise_with_category(e, retry_history)

                delay = self._calculate_delay(attempts, error_category)
                logger.info(f"Retrying in {delay:.2f}s due to {error_category} error (attempt {attempts}/{self.config.max_attempts})")
                await asyncio.sleep(delay)
                
            except Exception as e:
                # Non-ExternalOperationError exceptions are programming bugs
                # and should never be retried - let them bubble up immediately
                logger.debug(f"Programming error detected (not ExternalOperationError): {type(e).__name__}: {e}")
                raise

    def get_stats(self) -> Optional[RetryStats]:
        """Get current retry statistics if enabled."""
        return self.stats
    
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
        final_delay = min(delay, self.config.max_delay)
        logger.debug(f"Calculated backoff delay: base={base_delay}s, multiplied={delay:.2f}s, final={final_delay:.2f}s")
        return final_delay

    def _derive_error_category(self, error: ExternalOperationError) -> ErrorCategory:
        if isinstance(error, ExternalOperationPermanentError):
            return ErrorCategory.PERMANENT
        if isinstance(error, ExternalOperationRateLimitError):
            return ErrorCategory.RATE_LIMIT
        if isinstance(error, ExternalOperationTransientError):
            return ErrorCategory.TRANSIENT
        return self.error_classifier.classify_error(error)

    @staticmethod
    def _raise_with_category(error: ExternalOperationError, retry_history: List[str]) -> ExternalOperationError:
        # Prefer to bubble original typed exceptions to avoid losing context
        _update_retry_history(error, retry_history)
        raise error


def _get_error_classifier_for_adapter(adapter):
    """Get appropriate error classifier based on adapter type and characteristics."""
    
    if isinstance(adapter, BaseLLMAdapter):
        if adapter.is_remote():
            return HttpErrorClassifier()  # Remote LLM APIs (OpenAI, Anthropic)
        else:
            # Self-hosted LLMs use HTTP, so check HTTP status codes first,
            # then fall back to LLM-specific message patterns
            return CompositeErrorClassifier(
                HttpErrorClassifier(),
                SelfHostedLLMErrorClassifier(),
            )
    elif isinstance(adapter, BaseFSAdapter):
        return FilesystemErrorClassifier()
    elif isinstance(adapter, BaseBrowserAdapter):
        return BrowserErrorClassifier()  # Browser automation
    else:
        return HttpErrorClassifier()


def _update_retry_history(error: ExternalOperationError, retry_history: List[str]) -> None:
    """Replace exception retry history with combined attempts."""
    if hasattr(error, "retry_history"):
        error.retry_history = list(retry_history)