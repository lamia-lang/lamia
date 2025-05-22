"""
Local LLM adapters for running models directly on the user's machine.
Currently supports:
- Ollama (https://ollama.ai)
"""

from .ollama_adapter import OllamaAdapter

__all__ = ['OllamaAdapter'] 