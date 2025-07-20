"""Default configurations for different adapter types based on industry standards."""

from datetime import timedelta
from typing import Dict, Any

from .config import ExternalSystemRetryConfig

# Industry-tested retry configurations for different adapter types
# Based on OpenAI cookbook, AWS best practices, and production experience
RETRY_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "local": {
        "max_attempts": 1,         # No retries for local operations - failures are usually permanent
        "base_delay": 0.1,         # Minimal delay for local operations
        "max_delay": 1.0,          # Local ops should fail fast
        "exponential_base": 2.0,   # Standard exponential backoff
        "max_duration_seconds": 30 # Local ops should complete quickly
    },
    "network": {  # Standard HTTP/REST APIs
        "max_attempts": 3,         # Industry standard: 3 attempts (1 initial + 2 retries)
        "base_delay": 1.0,         # OpenAI recommendation: start with 1 second
        "max_delay": 32.0,         # Common ceiling for network timeouts
        "exponential_base": 2.0,   # Standard exponential backoff
        "max_duration_seconds": 300 # 5 minutes total for network operations
    },
    "llm": {
        "max_attempts": 5,         # LLMs need more retries due to higher rate limits
        "base_delay": 2.0,         # Longer initial delay for expensive LLM operations
        "max_delay": 60.0,         # OpenAI cookbook recommendation: up to 60s
        "exponential_base": 2.0,   # Standard exponential backoff
        "max_duration_seconds": 600 # 10 minutes for complex LLM operations
    },
    "filesystem": {
        "max_attempts": 2,         # Limited retries - most FS errors are permanent
        "base_delay": 0.5,         # Quick retry for transient FS issues
        "max_delay": 5.0,          # FS operations should be fast
        "exponential_base": 2.0,   # Standard exponential backoff
        "max_duration_seconds": 60 # 1 minute for filesystem operations
    }
}

def get_adapter_category(adapter_type: str) -> str:
    """Get the retry category for an adapter type."""
    adapter_lower = adapter_type.lower()
    if "local" in adapter_lower:
        return "local"
    elif "llm" in adapter_lower or "ai" in adapter_lower:
        return "llm"  # LLM-specific optimized settings
    elif "file" in adapter_lower or "fs" in adapter_lower:
        return "filesystem"  # Filesystem-specific settings
    return "network"  # Default to network settings (most adapters are remote)

def get_default_config(adapter_type: str = "network") -> ExternalSystemRetryConfig:
    """Get default retry configuration based on adapter type."""
    category = get_adapter_category(adapter_type)
    params = RETRY_DEFAULTS[category]
    
    return ExternalSystemRetryConfig(
        max_attempts=params["max_attempts"],
        base_delay=params["base_delay"],
        max_delay=params["max_delay"],
        exponential_base=params["exponential_base"],
        max_total_duration=timedelta(seconds=params["max_duration_seconds"])
    ) 