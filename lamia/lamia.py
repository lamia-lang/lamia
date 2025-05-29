from lamia.engine.engine import LamiaEngine
import asyncio
from typing import Any, Optional, List, Dict, Union
import yaml

class Lamia:
    """
    Main user interface for Lamia LLM engine.

    Args:
        *models: Model names (e.g., 'openai', 'ollama', ...)
        api_keys: Optional dict of API keys (e.g., {'openai': 'sk-...'}).
        validators: Optional list of functions or Lamia validator instances. Each is called as validator(response_text) or validator.validate(response_text) after generation. If any returns False, a ValueError is raised.
        config: Optional config dict or path. If provided, overrides *models.
    """
    def __init__(self, *models: str, api_keys: Optional[dict] = None, validators: Optional[List[Any]] = None, config: Optional[Union[str, Dict[str, Any]]] = None):
        # If config is provided, use it. Otherwise, build config from models/api_keys/validators.
        config_dict = None
        if config is not None:
            if isinstance(config, str):
                with open(config, 'r') as f:
                    config_dict = yaml.safe_load(f)
            elif isinstance(config, dict):
                config_dict = config
            else:
                raise ValueError("config must be a dict or a file path")
        else:
            config_dict = self._build_config_from_models(models, api_keys=api_keys, validators=validators)
        self._engine = LamiaEngine(config_dict)
        self._loop = None
        # Store validators as a list
        self._validators = validators if validators is not None else []

    def _key_env_name(self, key):
        # Map key to env var name (e.g., 'openai' -> 'OPENAI_API_KEY')
        if key.lower().endswith('_api_key'):
            return key.upper()
        return f"{key.upper()}_API_KEY"

    def _build_config_from_models(self, models, api_keys=None, validators=None):
        # Use the first model as default, rest as fallback
        config = {
            'default_model': models[0] if models else 'ollama',
            'models': {},
            'validation': {
                'enabled': True,
                'max_retries': 1,
                'fallback_models': list(models[1:]),
                'validators': [
                    {'type': 'html'}
                ]
            }
        }
        # Minimal model config for each
        for m in models:
            config['models'][m] = {'enabled': True}
        if api_keys:
            config['api_keys'] = api_keys
        if validators is not None:
            config['validation']['validators'] = validators
        return config

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