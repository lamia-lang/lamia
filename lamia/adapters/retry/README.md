# Retry System

Production-ready retry handling for external adapters with automatic configuration based on adapter type.

## Quick Start

```python
from lamia.adapters.retry import RetryHandler, RetryWrappedLLMAdapter

# Direct usage
handler = RetryHandler(adapter=my_adapter)
result = await handler.execute(my_operation)

# Wrapper usage  
retry_adapter = RetryWrappedLLMAdapter(original_adapter)
response = await retry_adapter.generate("Hello world")
```

## Automatic Configuration

The system automatically detects adapter types and configures appropriate retry settings:

| Adapter Type | Detection | Attempts | Delays | Purpose |
|-------------|-----------|----------|---------|---------|
| **Remote LLM** | `isinstance(adapter, BaseLLMAdapter) and adapter.is_remote()` | 5 | 2-60s | OpenAI, Anthropic |
| **Self-hosted LLM** | `isinstance(adapter, BaseLLMAdapter) and not adapter.is_remote()` | 3 | 5-180s | Ollama, local models |
| **Filesystem** | `isinstance(adapter, BaseFSAdapter)` | 2 | 0.5-5s | File operations |

## Error Classification

Automatically selects appropriate error classifiers:
- **Remote LLMs**: HTTP errors, rate limiting, auth failures
- **Self-hosted LLMs**: Hardware errors, model loading, memory issues  
- **Filesystem**: Permission errors, disk space, file locks

## Usage Examples

```python
# LLM adapter with automatic config
openai_adapter = OpenAIAdapter(api_key="...")
handler = RetryHandler(adapter=openai_adapter)
# Automatically gets: 5 attempts, 2-60s delays, HTTP error classification

# Ollama adapter with automatic config
ollama_adapter = OllamaAdapter(base_url="...")
handler = RetryHandler(adapter=ollama_adapter) 
# Automatically gets: 3 attempts, 5-180s delays, self-hosted error classification

# Filesystem adapter with automatic config
s3_adapter = S3Adapter(bucket="...")
handler = RetryHandler(adapter=s3_adapter)
# Automatically gets: 2 attempts, 0.5-5s delays, filesystem error classification
```

Based on `isinstance()` type checking and `adapter.is_remote()` method - no magic strings! 