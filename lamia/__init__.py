"""
Lamia - A unified interface for LLM interactions.

This package provides a simple way to interact with various LLM providers
through a consistent interface, with configuration management and a CLI.
"""

__version__ = "0.1.0"

from dataclasses import dataclass
from typing import Optional

# By default dataclasses are unhashable when they define an __eq__ method and
# are not frozen. Setting ``frozen=True`` restores hashing behaviour based on
# the instance's fields.
@dataclass(frozen=True)
class LLMModel:
    """Configuration for an LLM model.
    
    Args:
        model: The model identifier (e.g. 'gpt-4', 'claude-2', etc.)
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
    model: str
    # Primary parameters
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    # Advanced parameters
    top_p: Optional[float] = None  
    top_k: Optional[int] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    seed: Optional[int] = None

from .lamia import Lamia

__all__ = ["Lamia"] 