from typing import Optional, Dict, Any
import aiohttp
import json
import logging

from ...base import BaseLLMAdapter, LLMResponse

logger = logging.getLogger(__name__)

class OllamaAdapter(BaseLLMAdapter):
    """Adapter for local Ollama models."""
    
    def __init__(
        self,
        model: str = "llama2",
        base_url: str = "http://localhost:11434",
        context_size: int = 4096,
        **model_params
    ):
        """Initialize Ollama adapter.
        
        Args:
            model: Name of the Ollama model to use (must be pulled first)
            base_url: URL of the Ollama API server
            context_size: Maximum context size for the model
            **model_params: Additional model parameters supported by Ollama
        """
        self.model = model
        self.base_url = base_url.rstrip('/')
        self.context_size = context_size
        self.model_params = model_params
        self.session = None

    async def initialize(self) -> None:
        """Initialize the aiohttp session and verify model availability."""
        self.session = aiohttp.ClientSession()
        
        # Check if model is available
        try:
            async with self.session.post(
                f"{self.base_url}/api/show",
                json={"name": self.model}
            ) as response:
                if response.status != 200:
                    raise ValueError(
                        f"Model '{self.model}' not found. Please pull it first using: "
                        f"'ollama pull {self.model}'"
                    )
                model_info = await response.json()
                logger.info(f"Using Ollama model: {self.model}")
                logger.debug(f"Model details: {json.dumps(model_info, indent=2)}")
                
        except aiohttp.ClientError as e:
            raise ConnectionError(
                f"Failed to connect to Ollama server at {self.base_url}. "
                "Is Ollama running?"
            ) from e

    async def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[list[str]] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate a response using the Ollama model."""
        if not self.session:
            raise RuntimeError("Adapter not initialized. Use 'async with' or call initialize()")

        # Prepare request payload
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                **self.model_params,
                **kwargs
            }
        }

        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        if stop_sequences:
            payload["options"]["stop"] = stop_sequences

        try:
            async with self.session.post(
                f"{self.base_url}/api/generate",
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(
                        f"Ollama API error (status {response.status}): {error_text}"
                    )
                
                result = await response.json()
                
                # Extract token counts if available
                usage = {
                    "prompt_tokens": result.get("prompt_eval_count", 0),
                    "completion_tokens": result.get("eval_count", 0),
                    "total_tokens": result.get("prompt_eval_count", 0) + result.get("eval_count", 0)
                }

                return LLMResponse(
                    text=result["response"],
                    raw_response=result,
                    usage=usage,
                    model=f"ollama/{self.model}"
                )

        except aiohttp.ClientError as e:
            raise ConnectionError(f"Failed to communicate with Ollama server: {str(e)}") from e

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None 