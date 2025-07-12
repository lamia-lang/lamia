from lamia.engine.engine import LamiaEngine
import asyncio
from typing import Any, Optional, List, Dict, Union, Tuple
from lamia.interpreter.python_runner import run_python_code
from lamia.command_parser import CommandParser
from dataclasses import dataclass

@dataclass
class LamiaResult:
    result: str
    executor: str

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
        *models: Union[str, Tuple[str, int]], 
        api_keys: Optional[dict] = None, 
        validators: Optional[List[Any]] = None, 
    ):
        # Configuration
        self._config_dict = self._build_config(models, api_keys, validators, None)
        
        # Store validators for manual validation
        self._validators = validators if validators is not None else []
        
        # Initialize engine - ready to use immediately!
        self._engine = LamiaEngine(self._config_dict)
        
        # Initialize command parser instance
        self._command_parser = None

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "Lamia":
        def new_method(config, default_model):
            if ":" in default_model:
                models = [default_model]
            else:
                model_family_name = config['models'][default_model]["default_model"]
                full_model_name = f"{default_model}:{model_family_name}"
                models = [full_model_name]
            return models

        default_model = config['default_model']
        if default_model is not None:
            models = new_method(config, default_model)
        
        fallback_models = config["fallback_models"]
        if fallback_models is not None:
            for model in fallback_models:
                models.extend(new_method(config, model))

        return cls(
            models=models,
            validators=config['validators']
        )

    def _build_config(
        self, 
        models: tuple, 
        api_keys: Optional[dict], 
        validators: Optional[List[Any]], 
        config: Optional[Dict[str, Union[str, int, float, bool]]]
    ) -> Dict[str, Any]:
        """Build configuration from parameters"""
        if config is not None:
            return config
        
        # Build config from models/api_keys/validators
        config_dict = {
            'default_model': models[0] if models else 'ollama',
            'models': models,
            'validation': {
                'enabled': True,
                'max_retries': 1,
                'fallback_models': list(models[1:]) if len(models) > 1 else [],
                'validators': [] if not validators else validators
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
        command: str, 
    ) -> LamiaResult:
        """
        Generate a response, trying Python code first, then LLM.
        
        Args:
            command: The command to execute
            
        Returns:
            str: Generated response text
            
        Raises:
            RuntimeError: If engine fails to start
            MissingAPIKeysError: If API keys are missing
            ValueError: If validator fails
        """
        # Run Python code if this is Python code
        try:
            result = run_python_code(command, mode='interactive')
            return LamiaResult(result=str(result) if result is not None else "", executor="python")
        except SyntaxError as e:
            print(f"Syntax error: {e}", command)
            pass
        except Exception as e:
            print(f"Python code execution failed: {e}")
            pass
        
        # If not Python code, parse command using Lamia parser
        if self._command_parser is None:
            self._command_parser = CommandParser(command)
        response = await self._engine.execute(
            self._command_parser.command_type,
            self._command_parser.content,
            **self._command_parser.kwargs
        )
        return LamiaResult(result=response.text, executor=response.model)

    def run(
        self,
        command: str,
    ) -> LamiaResult:
        """
        Synchronous helper around run_async.

        Note: cannot be called from inside an active event-loop.
        
        Raises:
            MissingAPIKeysError: If API keys are missing
            ValueError: If validator fails
        """
        try:
            return asyncio.run(
                self.run_async(
                    command,
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

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        # Engine cleans up automatically via __del__
        pass