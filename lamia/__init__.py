"""
Lamia - A unified interface for LLM interactions.

This package provides a simple way to interact with various LLM providers
through a consistent interface, with configuration management and a CLI.
"""

__version__ = "0.1.0"

from dataclasses import dataclass
from typing import Optional, Union, Dict
from lamia.types import InputType

@dataclass(frozen=True)
class LLMModel:
    """Configuration for an LLM model.
    
    Args:
        name: The full model identifier (e.g. 'openai:gpt-4', 'anthropic:claude-2', etc.)
        temperature: Controls randomness in responses. Higher values (e.g. 0.8) make output more random, 
                    lower values (e.g. 0.2) make it more focused and deterministic.
        max_tokens: The maximum number of tokens to generate in the response.
        stream: Whether to stream the response token by token instead of waiting for the complete response.
                Useful for real-time display of model output.
        
        # Advanced parameters
        top_p: Nucleus sampling parameter. Only consider tokens whose cumulative probability exceeds this threshold.
        top_k: Only consider the top k tokens for each next token prediction.
        frequency_penalty: Positive values penalize tokens based on their frequency in the text so far.
        presence_penalty: Positive values penalize tokens that have appeared in the text at all.
    """
    name: str
    # Primary parameters
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    # Advanced parameters
    top_p: Optional[float] = None  
    top_k: Optional[int] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    seed: Optional[int] = None

    def get_provider_name(self) -> str:
        return self.name.split(":")[0]
    
    def get_model_name_without_provider(self) -> str:
        return ":".join(self.name.split(":")[1:])

@dataclass(frozen=True)
class OllamaModel(LLMModel):
    base_url: Optional[str] = None
    context_size: Optional[int] = None
    num_ctx: Optional[int] = None
    num_gpu: Optional[int] = None
    num_thread: Optional[int] = None
    repeat_penalty: Optional[float] = None

from .facade.lamia import Lamia
from .facade.result_types import LamiaResult
from .errors import (
    MissingAPIKeysError,
    ExternalOperationError,
    ExternalOperationFailedError,
    ExternalOperationTransientError,
    ExternalOperationRateLimitError,
    ExternalOperationPermanentError,
    AmbiguousFileError,
    FileReferenceError,
)

__all__ = [
    "Lamia",
    "LamiaResult",
    "InputType",  # For form automation
    "MissingAPIKeysError", 
    "ExternalOperationError",
    "ExternalOperationFailedError",
    "ExternalOperationTransientError", 
    "ExternalOperationRateLimitError",
    "ExternalOperationPermanentError",
    "AmbiguousFileError",
    "FileReferenceError",
] 