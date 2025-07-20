"""Default configurations for different adapter types based on industry standards."""

from datetime import timedelta
from typing import Dict, Any, Union, TYPE_CHECKING

from .config import ExternalSystemRetryConfig

if TYPE_CHECKING:
    from ..llm.base import BaseLLMAdapter
    from ..filesystem.base import BaseFSAdapter

# Industry-tested retry configurations for different adapter types
# Based on OpenAI cookbook, AWS best practices, and production experience
RETRY_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "network": {  # Standard HTTP/REST APIs, web adapters
        "max_attempts": 3,         # Industry standard: 3 attempts (1 initial + 2 retries)
        "base_delay": 1.0,         # OpenAI recommendation: start with 1 second
        "max_delay": 32.0,         # Common ceiling for network timeouts
        "exponential_base": 2.0,   # Standard exponential backoff
        "max_duration_seconds": 300 # 5 minutes total for network operations
    },
    "llm": {                      # Remote LLM APIs (OpenAI, Anthropic)
        "max_attempts": 5,         # LLMs need more retries due to higher rate limits
        "base_delay": 2.0,         # Longer initial delay for expensive LLM operations
        "max_delay": 60.0,         # OpenAI cookbook recommendation: up to 60s
        "exponential_base": 2.0,   # Standard exponential backoff
        "max_duration_seconds": 600 # 10 minutes for complex LLM operations
    },
    "self_hosted_llm": {         # Self-hosted LLMs (Ollama, local models, custom servers)
        "max_attempts": 3,         # Moderate retries - some errors are permanent, some transient
        "base_delay": 5.0,         # Longer initial delay for slow inference
        "max_delay": 180.0,        # Up to 3 minutes between retries (large models on CPU)
        "exponential_base": 2.0,   # Standard exponential backoff
        "max_duration_seconds": 1800 # 30 minutes total (very large models can be extremely slow)
    },
    "filesystem": {
        "max_attempts": 2,         # Limited retries - most FS errors are permanent
        "base_delay": 0.5,         # Quick retry for transient FS issues
        "max_delay": 5.0,          # FS operations should be fast
        "exponential_base": 2.0,   # Standard exponential backoff
        "max_duration_seconds": 60 # 1 minute for filesystem operations
    }
}

def get_default_config_for_adapter(adapter: Union["BaseLLMAdapter", "BaseFSAdapter"]) -> ExternalSystemRetryConfig:
    """Get default retry configuration based on adapter type and characteristics."""
    from ..llm.base import BaseLLMAdapter
    from ..filesystem.base import BaseFSAdapter
    
    if isinstance(adapter, BaseLLMAdapter):
        if adapter.is_remote():
            category = "llm"  # Remote LLM APIs (OpenAI, Anthropic)
        else:
            category = "self_hosted_llm"  # Self-hosted LLMs (Ollama, local models)
    elif isinstance(adapter, BaseFSAdapter):
        category = "filesystem"  # Filesystem operations
    else:
        category = "network"  # Default fallback
    
    params = RETRY_DEFAULTS[category]
    return ExternalSystemRetryConfig(
        max_attempts=params["max_attempts"],
        base_delay=params["base_delay"],
        max_delay=params["max_delay"],
        exponential_base=params["exponential_base"],
        max_total_duration=timedelta(seconds=params["max_duration_seconds"])
    ) 