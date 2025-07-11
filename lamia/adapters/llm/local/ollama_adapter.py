from typing import Optional, Dict, Any
import aiohttp
import json
import logging
import subprocess
import requests
import time

from ..base import BaseLLMAdapter, LLMResponse

logger = logging.getLogger(__name__)

class OllamaAdapter(BaseLLMAdapter):
    """Adapter for local Ollama models.
    
    The has_context_memory property infers context memory from the model name (if it contains 'chat' or 'instruct', returns True),
    but can be overridden by passing has_context_memory in model_params.
    """
    
    @classmethod
    def name(cls) -> str:
        return "ollama"
    
    @classmethod
    def env_var_names(cls) -> list[str]:
        """Ollama is local and doesn't need API keys."""
        return []  # No environment variables needed
    
    @classmethod
    def is_remote(cls) -> bool:
        return False  # Local model
    
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

    def is_ollama_running(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/version", timeout=2)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def start_ollama_service(self) -> bool:
        if self.is_ollama_running():
            logger.info("✓ Ollama service is running")
            return True
        logger.info("Starting Ollama service...")
        try:
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for i in range(30):
                if self.is_ollama_running():
                    logger.info("✓ Ollama service started successfully")
                    return True
                time.sleep(1)
            logger.error("Timeout waiting for Ollama service to start")
            return False
        except FileNotFoundError:
            logger.error("Ollama is not installed. Please install it first: https://ollama.ai/download")
            return False
        except Exception as e:
            logger.error(f"Failed to start Ollama service: {str(e)}")
            return False

    def ensure_ollama_model_pulled(self, model_name: str) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/show", json={"name": model_name})
            if response.status_code == 200:
                return True
            pull_response = requests.post(f"{self.base_url}/api/pull", json={"name": model_name})
            return pull_response.status_code == 200
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to check/pull Ollama model: {str(e)}")
            return False

    async def async_initialize(self) -> None:
        """Initialize the aiohttp session and verify model availability. Start Ollama service and pull model if needed."""
        # Start Ollama service if not running
        if not self.start_ollama_service():
            raise RuntimeError("Failed to start Ollama service")
        # Ensure model is pulled
        if not self.ensure_ollama_model_pulled(self.model):
            raise RuntimeError(f"Failed to pull Ollama model: {self.model}")
        self.session = aiohttp.ClientSession()
        # Check if model is available (API check)
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

    @property
    def has_context_memory(self) -> bool:
        # Allow explicit override
        if 'has_context_memory' in self.model_params:
            return bool(self.model_params['has_context_memory'])
        # Infer from model name
        model_name = self.model.lower()
        if any(x in model_name for x in ["chat", "instruct"]):
            return True
        return False 