from lamia.engine.engine import LamiaEngine
import asyncio
import sys
from typing import Any, Optional, List, Dict, Union, Tuple
from lamia.interpreter.python_runner import run_python_code
from lamia.command_parser import CommandParser
from dataclasses import dataclass
from lamia.engine.config_provider import ConfigProvider
import logging
from lamia import LLMModel
from lamia._internal_types.model_retry import ModelWithRetries
from lamia.validation.base import BaseValidator
from lamia.types import BaseType, ExternalOperationRetryConfig
from typing import Type
from datetime import timedelta

logger = logging.getLogger(__name__)

@dataclass
class LamiaResult:
    result_text: str
    typed_result: Any
    executor: str

class Lamia:
    """
    Main user interface for Lamia LLM engine.
    
    This class provides a simple interface for LLM interactions with automatic
    initialization and cleanup.
    
    Args:
        *models: Model names or Model objects (e.g., 'openai:gpt-4o', 'ollama', ...)
        api_keys: Optional dict of API keys (e.g., {'openai': 'sk-...'}).
        validators: Optional list of functions or Lamia validator instances.
    """
    
    def __init__(
        self, 
        *models: Union[Union[str, LLMModel], Tuple[Union[str, LLMModel], int]], 
        api_keys: Optional[dict] = None, 
        retry_config: Optional['ExternalOperationRetryConfig'] = None,
    ):
        # Initialize engine - ready to use immediately!
        self._engine = LamiaEngine(self._build_config(models, api_keys, retry_config))
        
        # Initialize command parser instance
        self._command_parser = None

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "Lamia":
        def construct_model(config, model_chain_item) -> LLMModel:
            if "name" not in model_chain_item:
                raise ValueError("Model chain item must have a name")
            
            if ":" in model_chain_item["name"]:
                model_family_name = model_chain_item["name"].split(":")[1]
                model_full_name = model_chain_item["name"]
                provider_name = model_chain_item["name"].split(":")[0]
            else:
                if "providers" not in config:
                    raise ValueError("Providers are not configured.")
                
                providers = config["providers"]
                provider_name = model_chain_item["name"]
                if provider_name not in providers:
                    raise ValueError(f"Provider {provider_name} is not configured. Please provide the model full name, e.g. 'openai:gpt-4o'.")
                
                if not providers[provider_name]["enabled"]:
                    logger.warning(f"Provider {provider_name} is not enabled. Please enable it in the config if you want to use it.")
                    return None
                
                if "default_model" not in providers[provider_name]:
                    raise ValueError(f"Provider {provider_name} does not have a default model. Please provide a default model in the config")
                
                model_family_name = providers[provider_name]["default_model"]
                model_full_name = f"{provider_name}:{model_family_name}"
            
            providers = config.get("providers", {})
            provider_settings = providers.get(provider_name, {})
            model_family_settings = provider_settings.get(model_family_name, {})
            get_model_param = lambda key: model_chain_item.get(key, None) or model_family_settings.get(key, None) or provider_settings.get(key, None)
            
            return LLMModel(
                name=model_full_name,
                temperature=get_model_param("temperature"),
                max_tokens=get_model_param("max_tokens"),
                top_p=get_model_param("top_p"),
                top_k=get_model_param("top_k"),
                frequency_penalty=get_model_param("frequency_penalty"),
                presence_penalty=get_model_param("presence_penalty"),
                seed=get_model_param("seed")
            )
        

        models = []
        if "model_chain" in config:
            model_chain = config['model_chain']
            for index, model_chain_item in enumerate(model_chain):
                try:
                    model = construct_model(config, model_chain_item)
                    if model is not None: # Gracefully handle disabled providers
                        models.append(model)
                except ValueError as e:
                    raise ValueError(f"Model chain item {index} with name '{model_chain_item.get('name', 'unknown')}' excluded. Reason: {e}")

        if len(models) == 0:
            logger.warning("No valid LLM model found in the model chain. LLM operations will not be possible.")
            
        # Convert the config dictionary to ExternalOperationRetryConfig
        retry_config_settings = config.get("retry_config", {})
        if not retry_config_settings.get('enabled', True):
            retry_config = None
        else:
            max_total_duration = retry_config_settings.get('max_total_duration')
            if max_total_duration is not None:
                max_total_duration = timedelta(seconds=max_total_duration)
                
            retry_config = ExternalOperationRetryConfig(
                max_attempts=retry_config_settings.get('max_attempts', 3),
                base_delay=retry_config_settings.get('base_delay', 1.0),
                max_delay=retry_config_settings.get('max_delay', 60.0),
                exponential_base=retry_config_settings.get('exponential_base', 2.0),
                max_total_duration=max_total_duration
            ) 

        # Unpack the models list for the constructor
        return cls(
            *models,
            retry_config=retry_config
        )

    def _build_config(
        self,
        models: Tuple[Union[Union[str, LLMModel], Tuple[Union[str, LLMModel], int]], ...],
        api_keys: Optional[dict], 
        retry_config: Optional[ExternalOperationRetryConfig],
    ) -> Dict[str, Any]:

        DEFAULT_LLM_RETRIES = 1
        # Convert the *models* var-tuple into a proper list for iteration.
        incoming_models = list(models) if models else []

        # If nothing was supplied default to a local Ollama setup.
        if not incoming_models:
            incoming_models = ["ollama"]

        models_and_retries: List[ModelWithRetries] = []
        for item in incoming_models:
            retries = DEFAULT_LLM_RETRIES

            # Unpack `(something, retries)`
            if isinstance(item, tuple):
                item, retries = item  # type: ignore[misc]

            # Turn strings into ``Model`` instances
            if isinstance(item, str):
                item = LLMModel(name=item) # When only the model name is provided, the model params are set to None automatically
            elif not isinstance(item, LLMModel):
                raise TypeError(
                    "Each model spec must be a str, Model or (spec, retries) tuple"
                )

            models_and_retries.append(ModelWithRetries(item, retries))

        # Assemble the final config dict
        config_dict: Dict[str, Any] = {
            "model_chain": models_and_retries,
            "api_keys": api_keys,
            "retry_config": retry_config,
        }    

        return ConfigProvider(config_dict)

    # No more ceremony needed - engine is ready on creation!

    async def run_async(
        self,
        command: str, 
        return_type: Optional[Type[BaseType]] = None,
        *,
        models: Union[Union[str, LLMModel], Tuple[Union[str, LLMModel], int]] = None, 
    ) -> LamiaResult:
        """
        Generate a response, trying Python code first, then LLM.
        
        Args:
            command: The command to execute
            models: The models to use, if not provided, the default models will be used
            return_type: The expected return type for validation
            
        Returns:
            LamiaResult: Generated response with result text and typed result
            
        Raises:
            MissingAPIKeysError: If API keys are missing for LLM requests
            ValueError: If validator fails
            ExternalOperationPermanentError: If external service has permanent failure (API key issues, invalid requests)
            ExternalOperationRateLimitError: If external service rate limits are exceeded
            ExternalOperationTransientError: If external service has temporary failures (network issues, timeouts)
            ExternalOperationFailedError: If external service fails with unclassified error
        """
        # Run Python code if this is Python code
        try:
            result = run_python_code(command, mode='interactive')
            return LamiaResult(result_text=str(result) if result is not None else "", typed_result=result, executor="python")
        except SyntaxError as e:
            logger.debug(f"Syntax error: {e} in command: {command}")
            pass
        except Exception as e:
            logger.debug(f"Python code execution failed: {e}")
            pass

        # Always create a fresh parser for each command to avoid reusing the
        # previous command's state (which caused the first‐command‐only bug).
        current_parser = CommandParser(command)
        #if current_parser.return_type is not None and type(current_parser.return_type) == str:
        #    validator = get_return_type_from_str(current_parser.return_type)

        if models is not None:
            self._engine.config_provider.override_model_chain_with(models)

        response = await self._engine.execute(
            current_parser.command_type,
            current_parser.content,
            return_type=return_type
        )

        if models is not None:
            self._engine.config_provider.reset_model_chain()

        return LamiaResult(result_text=response.raw_text, typed_result=response.result_type, executor=current_parser.command_type)

    def run(
        self,
        command: str,
        return_type: Optional[Type[BaseType]] = None,
        *,
        models: Union[Union[str, LLMModel], Tuple[Union[str, LLMModel], int]] = None,
    ) -> LamiaResult:
        """
        Run a command synchronously.
        
        Args:
            command: The command to execute
            models: The models to use, if not provided, the default models will be used
            return_type: The expected return type for validation
        
        Returns:
            LamiaResult: Generated response with result text and typed result
        
        Raises:
            MissingAPIKeysError: If API keys are missing
            ValueError: If validator fails
            ExternalOperationPermanentError: If external service has permanent failure (API key issues, invalid requests)
            ExternalOperationRateLimitError: If external service rate limits are exceeded
            ExternalOperationTransientError: If external service has temporary failures (network issues, timeouts)
            ExternalOperationFailedError: If external service fails with unclassified error
            RuntimeError: If run() is called inside an async context
        """
        try:
            return asyncio.run(
                self.run_async(
                    command,
                    return_type,
                    models=models,
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

    def load_python_folder(self, folder_path: str, recursive: bool = False) -> None:
        """Import every ``.py`` file in *folder_path* so in‐folder imports work.

        Args:
            folder_path: Path to the directory containing ``.py`` files.
            recursive: If *True*, walk sub-directories recursively.  Otherwise only the
            top-level files are imported.
            
        Raises:
            NotADirectoryError: If the folder path is not a directory
        """

        import sys
        import importlib.util
        from pathlib import Path

        base_path = Path(folder_path).expanduser().resolve()
        if not base_path.is_dir():
            raise NotADirectoryError(f"{folder_path} is not a directory")

        # Ensure the folder is on sys.path so regular import statements work.
        if str(base_path) not in sys.path:
            sys.path.insert(0, str(base_path))

        # Choose glob strategy based on recursion flag.
        file_iter = base_path.rglob('*.py') if recursive else base_path.glob('*.py')

        for py_file in file_iter:
            # Skip package init files – they’re imported automatically when
            # other modules in that package are loaded.
            if py_file.name == '__init__.py':
                continue

            # Derive a module name relative to the base folder so that nested
            # packages import with dotted paths (e.g. ``pkg.sub.module``).
            relative_parts = py_file.relative_to(base_path).with_suffix('').parts
            module_name = '.'.join(relative_parts)

            # Don’t reload if it’s already imported.
            if module_name in sys.modules:
                continue

            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module  # must be in sys.modules before exec
                spec.loader.exec_module(module)

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self._engine.cleanup()

    def __del__(self):
        """Clean up resources when the Lamia instance is destroyed."""
        try:
            # Try to run cleanup in a new event loop if no loop is running
            try:
                # Check if there's already a running event loop
                loop = asyncio.get_running_loop()
                # There's a running loop, so we can't call asyncio.run()
                # The cleanup will need to be handled by the user manually
                # or through the async context manager
                logger.warning("Lamia instance destroyed while event loop is running. "
                             "Consider using 'async with lamia:' or manually calling 'await lamia._engine.cleanup()'")
            except RuntimeError:
                # No running event loop, safe to create a new one
                asyncio.run(self._engine.cleanup())
        except Exception as e:
            logger.warning(f"Error during Lamia cleanup: {e}")