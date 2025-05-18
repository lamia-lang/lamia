from typing import Optional
import os
from pathlib import Path

from llama_cpp import Llama

from .base import BaseLLMAdapter, LLMResponse

class LlamaAdapter(BaseLLMAdapter):
    """Adapter for local LLaMA models using llama.cpp Python bindings."""
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        n_ctx: int = 2048,
        n_threads: Optional[int] = None,
    ):
        """Initialize local LLaMA adapter.
        
        Args:
            model_path: Path to the LLaMA model file. If not provided, will look for LLAMA_MODEL_PATH env var
            n_ctx: Context window size
            n_threads: Number of threads to use for inference. If None, uses all available cores
        """
        self.model_path = model_path or os.getenv("LLAMA_MODEL_PATH")
        if not self.model_path:
            raise ValueError("LLaMA model path must be provided or set in LLAMA_MODEL_PATH environment variable")
        
        if not Path(self.model_path).exists():
            raise FileNotFoundError(f"Model file not found at {self.model_path}")
            
        self.n_ctx = n_ctx
        self.n_threads = n_threads
        self.model = None

    async def initialize(self) -> None:
        """Initialize the LLaMA model."""
        self.model = Llama(
            model_path=self.model_path,
            n_ctx=self.n_ctx,
            n_threads=self.n_threads
        )

    async def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[list[str]] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate a response using local LLaMA model."""
        if not self.model:
            raise RuntimeError("Adapter not initialized. Use 'async with' or call initialize()")

        # Set default max_tokens if not provided
        if max_tokens is None:
            max_tokens = min(self.n_ctx - len(prompt), 2048)

        response = self.model.create_completion(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop_sequences,
            **kwargs
        )

        return LLMResponse(
            text=response["choices"][0]["text"],
            raw_response=response,
            usage={
                "prompt_tokens": response["usage"]["prompt_tokens"],
                "completion_tokens": response["usage"]["completion_tokens"],
                "total_tokens": response["usage"]["total_tokens"]
            },
            model=f"llama-{Path(self.model_path).stem}"
        )

    async def close(self) -> None:
        """Clean up the model resources."""
        self.model = None  # Let Python's GC handle the cleanup 