"""
Lamia - A unified interface for LLM interactions.

This package provides a simple way to interact with various LLM providers
through a consistent interface, with configuration management and a CLI.
"""

__version__ = "0.1.0"

from lamia.engine.engine import LamiaEngine
import tempfile
import yaml
import os
import asyncio
from typing import Any, Optional, Callable, List, Union

class Lamia:
    """
    Main user interface for Lamia LLM engine.

    Args:
        *models: Model names (e.g., 'openai', 'ollama', ...)
        api_keys: Optional dict of API keys (e.g., {'openai': 'sk-...'}). Sets os.environ.
        validators: Optional list of functions or Lamia validator instances. Each is called as validator(response_text) or validator.validate(response_text) after generation. If any returns False, a ValueError is raised.
    """
    def __init__(self, *models: str, api_keys: Optional[dict] = None, validators: Optional[List[Any]] = None):
        # Set API keys in environment if provided
        if api_keys:
            for k, v in api_keys.items():
                os.environ[self._key_env_name(k)] = v
        # Create a temporary config file with the specified models as primary and fallback
        self._tmp_config = tempfile.NamedTemporaryFile(delete=False, suffix='.yaml')
        self._tmp_config.close()
        self._config_path = self._tmp_config.name
        self._setup_config(models)
        self._engine = LamiaEngine(config_path=self._config_path)
        self._loop = None
        # Store validators as a list
        self._validators = validators if validators is not None else []

    def _key_env_name(self, key):
        # Map key to env var name (e.g., 'openai' -> 'OPENAI_API_KEY')
        if key.lower().endswith('_api_key'):
            return key.upper()
        return f"{key.upper()}_API_KEY"

    def _setup_config(self, models):
        # Use the first model as default, rest as fallback
        config = {
            'default_model': models[0] if models else 'ollama',
            'models': {},
            'validation': {
                'enabled': True,
                'max_retries': 3,
                'fallback_models': list(models[1:]),
                'validators': [
                    {'type': 'html'}
                ]
            }
        }
        # Minimal model config for each
        for m in models:
            config['models'][m] = {'enabled': True}
        with open(self._config_path, 'w') as f:
            yaml.safe_dump(config, f)

    def run(self, prompt: str, temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> str:
        """Generate a response synchronously (hides async details). Applies validators if provided."""
        async def _run():
            async with self._engine as engine:
                response = await engine.generate(prompt, temperature=temperature, max_tokens=max_tokens)
                text = response.text
                for validator in self._validators:
                    # If it's a class instance with .validate, use that
                    if hasattr(validator, 'validate') and callable(getattr(validator, 'validate')):
                        valid = validator.validate(text)
                    else:
                        valid = validator(text)
                    if not valid:
                        name = getattr(validator, '__name__', validator.__class__.__name__)
                        raise ValueError(f"Validator {name} failed for response: {text}")
                return text
        # Use existing event loop if present
        try:
            loop = asyncio.get_running_loop()
            return loop.run_until_complete(_run())
        except RuntimeError:
            return asyncio.run(_run())

    def __del__(self):
        # Clean up the temporary config file
        try:
            os.unlink(self._config_path)
        except Exception:
            pass

__all__ = ["Lamia"] 