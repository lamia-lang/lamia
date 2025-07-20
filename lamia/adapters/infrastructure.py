"""
Infrastructure layer for handling retries and error handling across different adapters.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import TypeVar, Generic, Callable, Awaitable, Optional, List, Any
import asyncio
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')

# Simple retry defaults for different adapter types
RETRY_DEFAULTS = {
    "local": {
        "max_attempts": 1,         # Number of times to try the operation (1 means no retries)
        "base_delay": 0.1,         # Initial delay between retries in seconds
        "max_delay": 1.0,          # Maximum delay between retries in seconds
        "exponential_base": 2.0,   # Each retry multiplies previous delay by this value
        "max_duration_seconds": 100 # Total time limit for all retries in seconds
    },
    "network": {  # Default for most remote operations
        "max_attempts": 3,         # Try up to 3 times (initial + 2 retries)
        "base_delay": 1.0,         # Start with 1 second delay
        "max_delay": 32.0,         # Never wait more than 32 seconds between retries
        "exponential_base": 2.0,   # Double the delay after each failure
        "max_duration_seconds": 300 # Give up after 5 minutes total
    },
    "llm": {
        "max_attempts": 5,         # LLMs might need more retries
        "base_delay": 2.0,         # Start with longer delays for LLMs
        "max_delay": 60.0,         # Up to 1 minute between retries
        "exponential_base": 2.0,   # Double the delay after each failure
        "max_duration_seconds": 600 # Allow up to 10 minutes total
    }
}

class ErrorCategory(Enum):
    PERMANENT = "permanent"  # Never retry (invalid credentials, etc)
    TRANSIENT = "transient"  # Temporary issues (network, timeout)
    RATE_LIMIT = "rate_limit"  # Special case for rate limiting

@dataclass
class RetryAttempt:
    """Metadata about a retry attempt"""
    attempt_number: int
    start_time: datetime
    error: Exception
    error_category: ErrorCategory

class RetryStrategy(ABC):
    @abstractmethod
    def should_retry(self, attempt: RetryAttempt) -> bool:
        """Determine if another retry should be attempted"""
        pass

    @abstractmethod
    def get_delay(self, attempt: RetryAttempt) -> float:
        """Get delay in seconds before next retry"""
        pass

class ExponentialBackoffStrategy(RetryStrategy):
    def __init__(
        self,
        base_delay: float,
        max_delay: float,
        exponential_base: float
    ):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base

    def should_retry(self, attempt: RetryAttempt) -> bool:
        return attempt.error_category != ErrorCategory.PERMANENT

    def get_delay(self, attempt: RetryAttempt) -> float:
        if attempt.error_category == ErrorCategory.RATE_LIMIT:
            # For rate limits, use a longer delay
            delay = self.base_delay * (self.exponential_base ** attempt.attempt_number) * 2
        else:
            delay = self.base_delay * (self.exponential_base ** attempt.attempt_number)
        
        return min(delay, self.max_delay)

class NoRetryStrategy(RetryStrategy):
    def should_retry(self, attempt: RetryAttempt) -> bool:
        return False

    def get_delay(self, attempt: RetryAttempt) -> float:
        return 0.0

@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_attempts: int = 3
    strategy: RetryStrategy = ExponentialBackoffStrategy()
    max_total_duration: Optional[timedelta] = timedelta(minutes=5)

class ErrorClassifier:
    """Classifies errors into categories for retry decisions"""
    
    def classify_error(self, error: Exception) -> ErrorCategory:
        # Common network errors
        if isinstance(error, (ConnectionError, TimeoutError)):
            return ErrorCategory.TRANSIENT
            
        # Rate limiting - extend with specific API errors
        if "rate limit" in str(error).lower() or "too many requests" in str(error).lower():
            return ErrorCategory.RATE_LIMIT
            
        # Authentication/permission errors are permanent
        if any(msg in str(error).lower() for msg in ["unauthorized", "forbidden", "invalid key"]):
            return ErrorCategory.PERMANENT
            
        # Default to permanent to be safe
        return ErrorCategory.PERMANENT

def get_adapter_category(adapter_type: str) -> str:
    """Get the retry category for an adapter type"""
    if "Local" in adapter_type:
        return "local"
    elif "LLM" in adapter_type:
        return "llm"
    return "network"  # Default to network settings (most adapters are remote)

def get_default_config(adapter_type: str) -> RetryConfig:
    """Get default retry configuration based on adapter type"""
    category = get_adapter_category(adapter_type)
    params = RETRY_DEFAULTS[category]
    
    if category == "local":
        return RetryConfig(
            max_attempts=params["max_attempts"],
            strategy=NoRetryStrategy()
        )
    
    return RetryConfig(
        max_attempts=params["max_attempts"],
        strategy=ExponentialBackoffStrategy(
            base_delay=params["base_delay"],
            max_delay=params["max_delay"],
            exponential_base=params["exponential_base"]
        ),
        max_total_duration=timedelta(seconds=params["max_duration_seconds"])
    )

class InfrastructureLayer(Generic[T]):
    """Handles infrastructure concerns like retries and error handling"""

    def __init__(
        self,
        adapter: Any,  # The adapter instance using this infrastructure
        retry_config: Optional[RetryConfig] = None,
        error_classifier: Optional[ErrorClassifier] = None
    ):
        self.adapter = adapter
        self.retry_config = retry_config or get_default_config(type(adapter).__name__)
        self.error_classifier = error_classifier or ErrorClassifier()

    async def execute_with_retry(
        self,
        operation: Callable[[], Awaitable[T]]
    ) -> T:
        """Execute an operation with configured retry behavior"""
        
        start_time = datetime.now()
        attempts: List[RetryAttempt] = []

        for attempt_number in range(self.retry_config.max_attempts):
            try:
                # Attempt the operation
                return await operation()

            except Exception as e:
                # Classify the error
                error_category = self.error_classifier.classify_error(e)
                
                # Record the attempt
                attempt = RetryAttempt(
                    attempt_number=attempt_number + 1,
                    start_time=datetime.now(),
                    error=e,
                    error_category=error_category
                )
                attempts.append(attempt)

                # Log the error
                logger.warning(
                    f"Operation failed (attempt {attempt_number + 1}/{self.retry_config.max_attempts})"
                    f" with {error_category.value} error: {str(e)}"
                )

                # Check if we should stop retrying
                if self._should_stop_retrying(attempt, start_time, attempts):
                    raise self._create_final_error(attempts)

                # Get delay before next attempt
                delay = self.retry_config.strategy.get_delay(attempt)
                
                logger.info(f"Retrying in {delay:.1f} seconds...")
                await asyncio.sleep(delay)

        # If we get here, we've exhausted all attempts
        raise self._create_final_error(attempts)

    def _should_stop_retrying(
        self,
        current_attempt: RetryAttempt,
        start_time: datetime,
        attempts: List[RetryAttempt]
    ) -> bool:
        """Determine if we should stop retrying"""
        
        # Never retry permanent errors
        if current_attempt.error_category == ErrorCategory.PERMANENT:
            return True

        # Check if we've exceeded max total duration
        if self.retry_config.max_total_duration:
            elapsed = datetime.now() - start_time
            if elapsed > self.retry_config.max_total_duration:
                return True

        # Check if the strategy says to stop
        if not self.retry_config.strategy.should_retry(current_attempt):
            return True

        return False

    def _create_final_error(self, attempts: List[RetryAttempt]) -> Exception:
        """Create a detailed error message from all attempts"""
        
        error_messages = [
            f"Attempt {a.attempt_number}: {a.error_category.value} - {str(a.error)}"
            for a in attempts
        ]
        
        return RuntimeError(
            f"Operation failed after {len(attempts)} attempts:\n" +
            "\n".join(error_messages)
        ) 