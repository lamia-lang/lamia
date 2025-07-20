# Retry System

Production-ready retry handling for external adapters with industry-standard configurations.

## Quick Start

```python
from lamia.adapters.retry import RetryHandler

# Basic usage
handler = RetryHandler(external_system_type="llm")
result = await handler.execute(my_operation)

# Wrapper usage
from lamia.adapters.retry import RetryWrappedLLMAdapter
retry_adapter = RetryWrappedLLMAdapter(original_adapter)
response = await retry_adapter.generate("Hello world")
```

## Configuration Profiles

| Type | Max Attempts | Base Delay | Max Delay | Purpose |
|------|-------------|------------|-----------|---------|
| **llm** | 5 | 2.0s | 60.0s | LLM APIs (OpenAI, Anthropic) |
| **network** | 3 | 1.0s | 32.0s | Web/HTTP adapters |
| **filesystem** | 2 | 0.5s | 5.0s | File operations |

## Error Classification

- **PERMANENT**: Never retry (401, 403, bad requests)
- **RATE_LIMIT**: Retry with longer delays (429, quota exceeded) 
- **TRANSIENT**: Retry normally (timeouts, 5xx errors)

## Custom Classifiers

```python
from lamia.adapters.retry import ErrorClassifier, ErrorCategory, register_error_classifier

class CacheErrorClassifier(ErrorClassifier):
    def classify_error(self, error: Exception) -> ErrorCategory:
        if 'temporary' in str(error).lower():
            return ErrorCategory.TRANSIENT
        return ErrorCategory.PERMANENT

register_error_classifier('cache', CacheErrorClassifier)
handler = RetryHandler(external_system_type='cache')
```

## Adding Retry to Your Adapter

```python
class MyAdapter:
    def __init__(self):
        self.retry_handler = RetryHandler(external_system_type="network")
    
    async def operation(self, data):
        return await self.retry_handler.execute(
            lambda: self._do_operation(data)
        )
```

Based on OpenAI cookbook and AWS best practices. 