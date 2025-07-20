"""Default configurations for different adapter types."""

from datetime import timedelta
from typing import Dict, Any

from .strategies import ExponentialBackoffStrategy, NoRetryStrategy
from .config import ExternalSystemRetryConfig

# Default retry configurations for different adapter types
RETRY_DEFAULTS: Dict[str, Dict[str, Any]] = {
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

def get_adapter_category(adapter_type: str) -> str:
    """Get the retry category for an adapter type."""
    if "Local" in adapter_type:
        return "local"
    elif "LLM" in adapter_type:
        return "llm"
    return "network"  # Default to network settings (most adapters are remote)

def get_default_config(adapter_type: str) -> ExternalSystemRetryConfig:
    """Get default retry configuration based on adapter type."""
    category = get_adapter_category(adapter_type)
    params = RETRY_DEFAULTS[category]
    
    if category == "local":
        return ExternalSystemRetryConfig(
            max_attempts=params["max_attempts"],
            strategy=NoRetryStrategy()
        )
    
    return ExternalSystemRetryConfig(
        max_attempts=params["max_attempts"],
        strategy=ExponentialBackoffStrategy(
            base_delay=params["base_delay"],
            max_delay=params["max_delay"],
            exponential_base=params["exponential_base"]
        ),
        max_total_duration=timedelta(seconds=params["max_duration_seconds"])
    ) 