from lamia.engine.engine import LamiaEngine
import asyncio
from typing import Any, Optional, List, Dict, Union
import yaml
import logging
from lamia.interpreter.python_runner import is_python_code, run_python_code

logger = logging.getLogger(__name__)

class Lamia:
    """
    Main user interface for Lamia LLM engine.
    
    This class provides a simple interface for LLM interactions with automatic
    initialization and cleanup.
    
    Args:
        *models: Model names (e.g., 'openai', 'ollama', ...)
        api_keys: Optional dict of API keys (e.g., {'openai': 'sk-...'}).
        validators: Optional list of functions or Lamia validator instances.
        config: Optional config dict or path. If provided, overrides *models.
    """
    
    def __init__(
        self, 
        *models: str, 
        api_keys: Optional[dict] = None, 
        validators: Optional[List[Any]] = None, 
        config: Optional[Union[str, Dict[str, Any]]] = None
    ):
        # Configuration
        self._config_dict = self._build_config(models, api_keys, validators, config)
        
        # Store validators for manual validation
        self._validators = validators if validators is not None else []
        
        # Initialize engine - ready to use immediately!
        self._engine = LamiaEngine(self._config_dict)
        
        logger.info("Lamia instance created")

    def _build_config(
        self, 
        models: tuple, 
        api_keys: Optional[dict], 
        validators: Optional[List[Any]], 
        config: Optional[Union[str, Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Build configuration from parameters"""
        if config is not None:
            if isinstance(config, str):
                with open(config, 'r') as f:
                    return yaml.safe_load(f)
            elif isinstance(config, dict):
                return config
            else:
                raise ValueError("config must be a dict or a file path")
        
        # Build config from models/api_keys/validators
        config_dict = {
            'default_model': models[0] if models else 'ollama',
            'models': {},
            'validation': {
                'enabled': True,
                'max_retries': 1,
                'fallback_models': list(models[1:]) if len(models) > 1 else [],
                'validators': [{'type': 'html'}] if not validators else validators
            }
        }
        
        # Add model configs
        for model in models:
            config_dict['models'][model] = {'enabled': True}
        
        if api_keys:
            config_dict['api_keys'] = api_keys
            
        return config_dict

    # No more ceremony needed - engine is ready on creation!

    async def run_async(
        self, 
        prompt: str, 
        *, 
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None, 
        skip_validators: bool = False
    ) -> str:
        """
        Generate a response, trying Python code first, then LLM.
        
        Args:
            prompt: The input prompt
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            skip_validators: Whether to skip manual validators
            
        Returns:
            str: Generated response text
            
        Raises:
            RuntimeError: If engine fails to start
            MissingAPIKeysError: If API keys are missing
            ValueError: If validator fails
        """
        # Check if this is Python code
        success, result = run_python_code(prompt, mode='interactive', show_banner=False)
        if success:
            return str(result) if result is not None else ""
        
        # Generate LLM response
        response = await self._engine.execute(
            'llm',
            prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Apply manual validators if not skipped
        if not skip_validators and self._validators:
            text = response.text
            for validator in self._validators:
                try:
                    # Try instance method first
                    if hasattr(validator, 'validate') and callable(getattr(validator, 'validate')):
                        valid = validator.validate(text)
                    else:
                        # Fall back to callable
                        valid = validator(text)
                    
                    if not valid:
                        validator_name = getattr(validator, '__name__', validator.__class__.__name__)
                        raise ValueError(f"Validator {validator_name} failed for response: {text}")
                except Exception as e:
                    if isinstance(e, ValueError):
                        raise  # Re-raise validation errors
                    # Log other errors but continue
                    logger.warning(f"Validator error: {e}")
        
        return response.text

    def run(
        self,
        prompt: str,
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        skip_validators: bool = False,
    ) -> str:
        """
        Synchronous helper around run_async.

        Note: cannot be called from inside an active event-loop.
        """
        try:
            return asyncio.run(
                self.run_async(
                    prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    skip_validators=skip_validators,
                )
            )
        except RuntimeError as e:
            # Happens only if there is already a running event loop
            if "running event loop" in str(e):
                raise RuntimeError(
                    "run() cannot be used inside an async context. "
                    "Use 'await lamia.run_async(...)' instead."
                ) from e
            raise

    def get_validation_stats(self) -> Optional[Any]:
        """Get validation statistics."""
        return self._engine.get_validation_stats()
    
    def get_recent_validation_results(self, limit: Optional[int] = None) -> Optional[List[Any]]:
        """Get recent validation results."""
        return self._engine.get_recent_validation_results(limit)

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        # Engine cleans up automatically via __del__
        pass