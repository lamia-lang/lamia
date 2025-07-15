import subprocess
import requests
import time
import logging

logger = logging.getLogger(__name__)

class OllamaManager:
    def is_running(self) -> bool:
        """Check if Ollama service is running by trying to connect to its API."""
        try:
            response = requests.get("http://localhost:11434/api/version", timeout=2)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def list_models(self) -> list[str]:
        """
        Get list of available local Ollama models.
        Returns empty list if service is not running or no models found.
        """
        if not self.is_running():
            logger.warning("⚠️ Ollama service is not running. Start it with 'ollama serve'")
            return []
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                return [model['name'] for model in models]
            return []
        except requests.exceptions.RequestException:
            return []

    def start_service(self) -> bool:
        """
        Start the Ollama service if it's not running.
        Returns:
            bool: True if service started successfully or was already running
        """
        if self.is_running():
            logger.info("✓ Ollama service is running")
            return True
        logger.info("Starting Ollama service...")
        try:
            # Start Ollama in the background
            subprocess.Popen(["ollama", "serve"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
            # Wait for service to start (max 30 seconds)
            for i in range(30):
                if self.is_running():
                    print("✓ Ollama service started successfully")
                    return True
                if i % 5 == 0:  # Show progress every 5 seconds
                    print(".", end="", flush=True)
                time.sleep(1)
            logger.error("Timeout waiting for Ollama service to start")
            return False
        except FileNotFoundError:
            logger.error("Ollama is not installed. Please install it first: https://ollama.ai/download")
            raise RuntimeError("Ollama is not installed")
        except Exception as e:
            logger.error(f"Failed to start Ollama service: {str(e)}")
            return False

    def ensure_model_pulled(self, model_name: str) -> bool:
        """
        Ensure the specified Ollama model is pulled and available.
        Args:
            model_name: Name of the Ollama model to check/pull
        Returns:
            bool: True if model is available
        """
        try:
            # Check if model exists
            response = requests.get(f"http://localhost:11434/api/show", json={"name": model_name})
            if response.status_code == 200:
                return True
            # If model doesn't exist, pull it
            pull_response = requests.post(f"http://localhost:11434/api/pull", json={"name": model_name})
            return pull_response.status_code == 200
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to check/pull Ollama model: {str(e)}") 