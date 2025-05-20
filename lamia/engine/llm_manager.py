import asyncio
from typing import List
import os
import subprocess
import requests
import time
import sys
from typing import Optional, Dict, Any

from dotenv import load_dotenv

from lamia.adapters.llm.openai_adapter import OpenAIAdapter
from lamia.adapters.llm.anthropic_adapter import AnthropicAdapter
from lamia.adapters.llm.local import OllamaAdapter
from lamia.adapters.llm.base import BaseLLMAdapter, LLMResponse
from .config_manager import ConfigManager

def check_api_key(model_type: str) -> str:
    """
    Get and validate API key from environment variables.
    Exits with error if required variables are missing.
    
    Args:
        model_type: The type of model being used ('openai' or 'anthropic')
        
    Returns:
        str: The API key if found
        
    Raises:
        SystemExit: If the required API key is not found
    """
    env_vars = {
        'openai': 'OPENAI_API_KEY',
        'anthropic': 'ANTHROPIC_API_KEY'
    }
    
    if model_type not in env_vars:
        return None
        
    env_var = env_vars[model_type]
    api_key = os.getenv(env_var)
    
    if not api_key:
        print(f"Error: {env_var} environment variable is not set")
        print(f"Please set it using: export {env_var}=your-api-key")
        print("You can also add it to your .env file:")
        print(f"{env_var}=your-api-key")
        sys.exit(1)
        
    return api_key

def is_ollama_running() -> bool:
    """Check if Ollama service is running by trying to connect to its API."""
    try:
        response = requests.get("http://localhost:11434/api/version", timeout=2)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def list_available_ollama_models() -> list[str]:
    """
    Get list of available local Ollama models.
    Returns empty list if service is not running or no models found.
    """
    if not is_ollama_running():
        print("⚠️  Ollama service is not running. Start it with 'ollama serve'")
        return []
        
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            return [model['name'] for model in models]
        return []
    except requests.exceptions.RequestException:
        return []

def start_ollama_service() -> bool:
    """
    Start the Ollama service if it's not running.
    
    Returns:
        bool: True if service started successfully or was already running
    """
    if is_ollama_running():
        print("✓ Ollama service is running")
        return True

    print("Starting Ollama service...")
    try:
        # Start Ollama in the background
        subprocess.Popen(["ollama", "serve"], 
                       stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
        
        # Wait for service to start (max 30 seconds)
        for i in range(30):
            if is_ollama_running():
                print("✓ Ollama service started successfully")
                return True
            if i % 5 == 0:  # Show progress every 5 seconds
                print(".", end="", flush=True)
            time.sleep(1)
        
        print("\n❌ Timeout waiting for Ollama service to start")
        return False
    except FileNotFoundError:
        print("\n❌ Ollama is not installed. Please install it first: https://ollama.ai/download")
        return False
    except Exception as e:
        print(f"\n❌ Failed to start Ollama service: {str(e)}")
        return False

def ensure_ollama_model_pulled(model_name: str) -> bool:
    """
    Ensure the specified Ollama model is pulled and available.
    
    Args:
        model_name: Name of the Ollama model to check/pull
        
    Returns:
        bool: True if model is available
    """
    try:
        # Check if model exists
        response = requests.get(f"http://localhost:11434/api/show", 
                              json={"name": model_name})
        
        if response.status_code == 200:
            return True
            
        # If model doesn't exist, pull it
        pull_response = requests.post(f"http://localhost:11434/api/pull", 
                                    json={"name": model_name})
        
        return pull_response.status_code == 200
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to check/pull Ollama model: {str(e)}")

def is_local_model_provider(provider_name: str) -> bool:
    """Return True if the provider is a local engine (like Ollama)."""
    # Add new local providers here as needed
    return provider_name in {"ollama"}

def create_adapter_from_config(config_manager: ConfigManager, override_model: str = None) -> BaseLLMAdapter:
    """Create an adapter instance based on the active configuration. Local engines are not started here."""
    provider_name = override_model or config_manager.get_default_model()
    provider_config = config_manager.get_model_config(provider_name)

    if provider_name == "openai":
        model_name = provider_config.get('default_model')
        if not model_name:
            available_models = provider_config.get('models', [])
            print("\nAvailable OpenAI models:")
            for m in available_models:
                if isinstance(m, str):
                    print(f"- {m}")
                elif isinstance(m, dict):
                    print(f"- {m.get('name')}")
            raise RuntimeError(
                "\nPlease specify one of the above models in config.yaml under openai.default_model"
            )
        return OpenAIAdapter(
            api_key=check_api_key('openai'),
            model=model_name
        )
    elif provider_name == "anthropic":
        model_name = provider_config.get('default_model')
        if not model_name:
            available_models = provider_config.get('models', [])
            print("\nAvailable Anthropic models:")
            for m in available_models:
                if isinstance(m, str):
                    print(f"- {m}")
                elif isinstance(m, dict):
                    print(f"- {m.get('name')}")
            raise RuntimeError(
                "\nPlease specify one of the above models in config.yaml under anthropic.default_model"
            )
        return AnthropicAdapter(
            api_key=check_api_key('anthropic'),
            model=model_name
        )
    elif is_local_model_provider(provider_name):
        # Do NOT start the local engine or pull the model here; defer to adapter.initialize()
        model_name = provider_config.get('default_model')
        if not model_name:
            available_models = provider_config.get('models', [])
            print(f"Available {provider_name} models:")
            for m in available_models:
                if isinstance(m, str):
                    print(f"- {m}")
                elif isinstance(m, dict):
                    print(f"- {m.get('name')}")
            raise RuntimeError(
                f"Please specify one of the available models in config.yaml under {provider_name}.default_model"
            )
        # For Ollama, use OllamaAdapter; for future local providers, add here
        if provider_name == "ollama":
            return OllamaAdapter(
                model=model_name,
                base_url=provider_config.get('base_url', 'http://localhost:11434'),
                context_size=provider_config.get('context_size'),
                num_ctx=provider_config.get('num_ctx'),
                num_gpu=provider_config.get('num_gpu'),
                num_thread=provider_config.get('num_thread'),
                repeat_penalty=provider_config.get('repeat_penalty'),
                top_k=provider_config.get('top_k'),
                top_p=provider_config.get('top_p')
            )
        # Add more local adapters here as needed
        raise ValueError(f"Unsupported local model provider: {provider_name}")
    else:
        raise ValueError(f"Unsupported model type: {provider_name}")

async def generate_response(prompt: str, config_path: str = None) -> LLMResponse:
    """
    Generate a response using the configured model.
    
    Args:
        prompt: The input prompt to send to the LLM
        config_path: Optional path to a config file. If None, uses default config
        
    Returns:
        LLMResponse object containing the model's response and metadata
        
    Raises:
        FileNotFoundError: If config file is not found
        ValueError: If configuration is invalid
        RuntimeError: If Ollama service fails to start or model is unavailable
        SystemExit: If required API keys are not found in environment
    """
    # Load environment variables at the start
    load_dotenv()
    
    config_manager = ConfigManager(config_path)
    adapter = create_adapter_from_config(config_manager)
    
    async with adapter as llm:
        model_config = config_manager.get_model_config(config_manager.get_default_model())
        response = await llm.generate(
            prompt,
            temperature=model_config.get('temperature', 0.7),
            max_tokens=model_config.get('max_tokens', 1000)
        )
    
    return response

async def main():
    """Example usage of the LLM manager."""
    # Example prompt
    prompt = "Explain how neural networks work in one paragraph."
    
    try:
        # Generate response using the configured model
        response = await generate_response(prompt)
        
        print(f"\nModel: {response.model}")
        print(f"Response: {response.text}")
        print(f"Token usage: {response.usage}")
        
    except FileNotFoundError as e:
        print(f"Configuration error: {e}")
        print("Please create a config.yaml file with your desired settings.")
    except ValueError as e:
        print(f"Configuration error: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 