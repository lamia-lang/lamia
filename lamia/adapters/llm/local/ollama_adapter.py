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
        base_url: str = "http://localhost:11434",
        **model_params
    ):
        """Initialize Ollama adapter.
        
        Args:
            model: Name of the Ollama model to use (must be pulled first)
            base_url: URL of the Ollama API server
            context_size: Maximum context size for the model
            **model_params: Additional model parameters supported by Ollama
        """
        self.base_url = base_url.rstrip('/')
        self.model_params = model_params

        # Start Ollama service if not running
        if not self.start_ollama_service():
            raise RuntimeError("Failed to start Ollama service")
        self.session = aiohttp.ClientSession()

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

    async def generate(
        self,
        prompt: str,
        model: LLMModel,
    ) -> LLMResponse:
        """Generate a response using the Ollama model."""
        if not self.session:
            raise RuntimeError("Adapter not initialized. Use 'async with' or call initialize()")
        
        # Ensure model is pulled
        if not self.ensure_ollama_model_pulled(model.name):
            raise RuntimeError(f"Failed to pull Ollama model: {model.name}")

        # Prepare request payload
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": model.temperature,
                "max_tokens": model.max_tokens,
                "stop": model.stop_sequences,
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