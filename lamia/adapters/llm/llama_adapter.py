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
        has_context_memory: bool = None,
        configs: Optional[dict] = None
    ):
        """Initialize local LLaMA adapter.
        
        Args:
            model_path: Path to the LLaMA model file. If not provided, will look for LLAMA_MODEL_PATH environment variable
            has_context_memory: Optional override for context memory capability
            configs: Optional dictionary of advanced/extra settings (e.g., n_ctx, n_threads, etc.)
        """
        self.model_path = model_path or os.getenv("LLAMA_MODEL_PATH")
        if not self.model_path:
            raise ValueError("LLaMA model path must be provided or set in LLAMA_MODEL_PATH environment variable")
        if not Path(self.model_path).exists():
            raise FileNotFoundError(f"Model file not found at {self.model_path}")
        self.model = None
        self._has_context_memory = has_context_memory
        self.configs = configs or {}

    async def initialize(self) -> None:
        """Initialize the LLaMA model."""
        llama_kwargs = dict(model_path=self.model_path)
        llama_kwargs.update(self.configs)
        self.model = Llama(**llama_kwargs)

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
        n_ctx = self.configs.get('n_ctx', 2048)
        if max_tokens is None:
            max_tokens = min(n_ctx - len(prompt), 2048)

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

    @property
    def has_context_memory(self) -> bool:
        if self._has_context_memory is not None:
            return self._has_context_memory
        # Infer from model name (file name): if contains 'chat' or 'instruct', assume context memory
        model_name = str(self.model_path).lower()
        if any(x in model_name for x in ["chat", "instruct"]):
            return True
        return False 