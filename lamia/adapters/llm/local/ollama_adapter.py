from typing import Optional, Dict, Any, List, Type
import asyncio
import aiohttp
import json
import logging
import subprocess
import requests
import time
import sys
import weakref
import atexit
import threading
from ..base import BaseLLMAdapter, LLMResponse, LLMModel, make_strict_schema, raise_for_status, raise_for_connection_error
from lamia.errors import OllamaNotInstalledError
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# Global registry to track instances for cleanup
_active_instances = weakref.WeakSet()

def _wire_process_logs(process: subprocess.Popen, label: str) -> None:
    """Forward child process stdout/stderr to Lamia logger."""
    def _pump(stream, level: int, stream_name: str) -> None:
        if stream is None:
            return
        try:
            for line in iter(stream.readline, ""):
                text = line.strip()
                if text:
                    logger.log(level, "%s %s: %s", label, stream_name, text)
        except Exception:
            pass

    threading.Thread(
        target=_pump,
        args=(process.stdout, logging.INFO, "stdout"),
        daemon=True,
    ).start()
    threading.Thread(
        target=_pump,
        args=(process.stderr, logging.WARNING, "stderr"),
        daemon=True,
    ).start()

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
    async def models(cls, api_key: str = "", base_url: str = "http://localhost:11434") -> list[dict]:
        """Fetch installed models from the local Ollama instance."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{base_url.rstrip('/')}/api/tags") as response:
                    if response.status != 200:
                        return []
                    data = await response.json()
                    return [
                        {"id": m["name"], **{k: v for k, v in m.items() if k != "name"}}
                        for m in data.get("models", [])
                    ]
        except aiohttp.ClientError:
            return []

    @property
    def supports_structured_output(self) -> bool:
        return True

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
            process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            _wire_process_logs(process, "ollama serve")
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
        response_model: Optional[Type[BaseModel]] = None,
    ) -> LLMResponse:
        """Generate a response using the Ollama model."""
        
        if not self._ensure_ollama_model_pulled(model.get_model_name_without_provider()):
            raise RuntimeError(f"Failed to pull Ollama model: {model.get_model_name_without_provider()}")

        options: Dict[str, Any] = {}
        if model.temperature is not None:
            options["temperature"] = model.temperature
        if model.max_tokens is not None:
            options["num_predict"] = model.max_tokens
        if model.top_p is not None:
            options["top_p"] = model.top_p
        if model.top_k is not None:
            options["top_k"] = model.top_k
        if model.frequency_penalty is not None:
            options["frequency_penalty"] = model.frequency_penalty
        if model.presence_penalty is not None:
            options["presence_penalty"] = model.presence_penalty
        if model.seed is not None:
            options["seed"] = model.seed

        payload: Dict[str, Any] = {
            "model": model.get_model_name_without_provider(),
            "prompt": prompt,
            "stream": False,
        }
        if options:
            payload["options"] = options
        if response_model is not None:
            payload["format"] = make_strict_schema(response_model)

        url = f"{self.base_url}/api/generate"
        timeout = aiohttp.ClientTimeout(total=300, connect=10)
        logger.debug("Ollama request: model=%s url=%s", payload["model"], url)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise_for_status(response.status, error_text, "Ollama API error")
                    
                    result = await response.json()
                    
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

        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ConnectionError) as e:
            raise_for_connection_error(e, "Failed to communicate with Ollama server")

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
            self.ollama_process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            _wire_process_logs(self.ollama_process, "ollama serve")
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