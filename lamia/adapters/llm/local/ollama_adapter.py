from typing import Optional, Dict, Any, List
import aiohttp
import json
import logging
import subprocess
import requests
import time
import sys
import weakref
import atexit
from ..base import BaseLLMAdapter, LLMResponse, LLMModel
from lamia.errors import OllamaNotInstalledError

logger = logging.getLogger(__name__)


# Global registry to track instances for cleanup
_active_instances = weakref.WeakSet()

def _cleanup_all_instances():
    """Cleanup function called at exit."""
    for instance in list(_active_instances):
        try:
            if instance.ollama_process:
                instance.ollama_process.terminate()
        except Exception:
            pass

atexit.register(_cleanup_all_instances)

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

    @classmethod
    def is_ollama_running(cls, base_url: str = "http://localhost:11434") -> bool:
        """Check if the Ollama service is currently responding."""
        try:
            response = requests.get(f"{base_url.rstrip('/')}/api/version", timeout=2)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    @classmethod
    def is_ollama_installed(cls) -> bool:
        """Check if the Ollama CLI binary is available."""
        try:
            result = subprocess.run(
                ["ollama", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                text=True,
            )
            return result.returncode == 0
        except OSError:
            return False

    @classmethod
    def start_ollama_service(cls, base_url: str = "http://localhost:11434") -> bool:
        """Best-effort start of `ollama serve` and wait briefly for readiness."""
        if cls.is_ollama_running(base_url=base_url):
            return True
        if not cls.is_ollama_installed():
            return False
        try:
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for _ in range(10):
                if cls.is_ollama_running(base_url=base_url):
                    return True
                time.sleep(1)
        except Exception:
            pass
        return False

    @classmethod
    def list_models_sync(cls, base_url: str = "http://localhost:11434") -> list[str]:
        """Synchronously query Ollama for installed model names."""
        try:
            response = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=3)
            if response.status_code == 200:
                return [m["name"] for m in response.json().get("models", [])]
        except requests.RequestException:
            pass
        return []
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
    ):
        """Initialize Ollama adapter.
        
        Args:
            model: Name of the Ollama model to use (must be pulled first)
        """
        self.base_url = base_url.rstrip('/')
        self.ollama_process = None  # Track the process we start

        # Start Ollama service if not running (raises OllamaNotInstalledError if binary missing)
        self._start_ollama_service()
        
        # Register this instance for cleanup
        _active_instances.add(self)

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
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session: # 5 minutes total timeout, local models on normal computers are slow
                async with session.post(
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
        return self.is_ollama_running(base_url=self.base_url)

    def _start_ollama_service(self) -> None:
        """Start the Ollama service if not already running.

        Raises:
            OllamaNotInstalledError: If the ollama binary is not found on PATH.
            RuntimeError: If the service fails to start for other reasons.
        """
        if self._is_ollama_running():
            logger.info("Ollama service is running")
            return
        logger.info("Starting Ollama service...")
        if not self.is_ollama_installed():
            raise OllamaNotInstalledError()
        try:
            self.ollama_process = subprocess.Popen(["ollama", "serve"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for i in range(30):
                if self._is_ollama_running():
                    logger.info("Ollama service started successfully")
                    return
                time.sleep(1)
            raise RuntimeError("Timeout waiting for Ollama service to start")
        except OllamaNotInstalledError:
            raise
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to start Ollama service: {str(e)}") from e

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

    async def get_available_models(self) -> List[str]:
        """Get available model names from local Ollama installation."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        models = data.get("models", [])
                        return [model["name"] for model in models]
                    else:
                        logger.error(f"Failed to fetch Ollama models: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Error fetching Ollama models: {e}")
            return []
    
    async def get_model_details(self) -> List[Dict[str, Any]]:
        """Get detailed model information including sizes."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("models", [])
                    else:
                        logger.error(f"Failed to fetch Ollama model details: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Error fetching Ollama model details: {e}")
            return []

    async def close(self) -> None:
        
        # Terminate the Ollama process if we started it
        if self.ollama_process:
            try:
                self.ollama_process.terminate()
                # Give it a moment to terminate gracefully
                try:
                    self.ollama_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't terminate gracefully
                    self.ollama_process.kill()
                    self.ollama_process.wait()
                logger.info("✓ Ollama process terminated")
            except Exception as e:
                logger.warning(f"Failed to terminate Ollama process: {e}")
            finally:
                self.ollama_process = None

    def __del__(self):
        """Ensure cleanup during garbage collection."""
        # Check if Python is shutting down
        if sys.meta_path is None:
            return
        
        # Kill ollama process if it exists
        if hasattr(self, 'ollama_process') and self.ollama_process:
            try:
                self.ollama_process.terminate()
                self.ollama_process = None
            except Exception:
                pass