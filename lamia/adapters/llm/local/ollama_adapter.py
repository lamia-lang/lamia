from typing import Optional, Dict, Any
import aiohttp
import json
import logging
import subprocess
import requests
import time
from ..base import BaseLLMAdapter, LLMResponse, LLMModel

logger = logging.getLogger(__name__)

class OllamaAdapter(BaseLLMAdapter):
    """Adapter for local Ollama models.
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
        base_url: str = "http://localhost:11434",
    ):
        """Initialize Ollama adapter.
        
        Args:
            model: Name of the Ollama model to use (must be pulled first)
        """
        self.base_url = base_url.rstrip('/')

        # Start Ollama service if not running
        if not self._start_ollama_service():
            raise RuntimeError("Failed to start Ollama service")
        # Initialize session as None - will be created on first use
        self.session = None

    @property
    def has_context_memory(self) -> bool:
        """Check if the adapter has context memory."""
        return False

    async def generate(
        self,
        prompt: str,
        model: LLMModel,
    ) -> LLMResponse:
        """Generate a response using the Ollama model."""
        await self._ensure_session()
        
        # Ensure model is pulled
        if not self._ensure_ollama_model_pulled(model.get_model_name_without_provider()):
            raise RuntimeError(f"Failed to pull Ollama model: {model.get_model_name_without_provider()}")

        # Prepare request payload
        payload = {
            "model": model.get_model_name_without_provider(),
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": model.temperature,
                "max_tokens": model.max_tokens,
                #"stop": model.stop_sequences,
                "top_p": model.top_p,
                "top_k": model.top_k,
                "frequency_penalty": model.frequency_penalty,
                "presence_penalty": model.presence_penalty,
                "seed": model.seed,
            }
        }

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
                    model=model.name
                )

        except aiohttp.ClientError as e:
            raise ConnectionError(f"Failed to communicate with Ollama server: {str(e)}") from e

    def _is_ollama_running(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/version", timeout=2)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def _start_ollama_service(self) -> bool:
        if self._is_ollama_running():
            logger.info("✓ Ollama service is running")
            return True
        logger.info("Starting Ollama service...")
        try:
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for i in range(30):
                if self._is_ollama_running():
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

    def _ensure_ollama_model_pulled(self, model_name: str) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/show", json={"name": model_name})
            if response.status_code == 200:
                return True
            pull_response = requests.post(f"{self.base_url}/api/pull", json={"name": model_name})
            return pull_response.status_code == 200
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to check/pull Ollama model: {str(e)}")
            return False

    async def _ensure_session(self):
        """Ensure we have an active session."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None