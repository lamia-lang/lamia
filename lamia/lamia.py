from lamia.engine.engine import LamiaEngine
import asyncio
from typing import Any, Optional, List, Dict, Union, Tuple
from lamia.interpreter.python_runner import run_python_code
from lamia.command_parser import CommandParser
from dataclasses import dataclass
from lamia.engine.config_provider import ConfigProvider
import logging
from lamia import LLMModel
from lamia._internal_types.model_retry import ModelWithRetries
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
        validators: Optional[List[Any]] = None, 
    ):
        # Initialize engine - ready to use immediately!
        self._engine = LamiaEngine(self._build_config(models, api_keys, validators))
        
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

        # Unpack the models list for the constructor
        return cls(
            *models,
            validators=config["validation"]["validators"] if "validation" in config and "validators" in config["validation"] else None
        )

    def _build_config(
        self,
        models: Tuple[Union[Union[str, LLMModel], Tuple[Union[str, LLMModel], int]], ...],
        api_keys: Optional[dict], 
        validators: Optional[List[Any]], 
    ) -> Dict[str, Any]:

        DEFAULT_RETRIES = 1
        # Convert the *models* var-tuple into a proper list for iteration.
        incoming_models = list(models) if models else []

        # If nothing was supplied default to a local Ollama setup.
        if not incoming_models:
            incoming_models = ["ollama"]

        models_and_retries: List[ModelWithRetries] = []
        for item in incoming_models:
            retries = DEFAULT_RETRIES

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
            "validators": validators or [],
            "api_keys": api_keys,
        }    

        return ConfigProvider(config_dict)

    # No more ceremony needed - engine is ready on creation!

    async def run_async(
        self,
        command: str, 
        models: Union[Union[str, LLMModel], Tuple[Union[str, LLMModel], int]] = None, 
    ) -> LamiaResult:
        """
        Generate a response, trying Python code first, then LLM.
        
        Args:
            command: The command to execute
            models: The models to use, if not provided, the default models will be used
        Returns:
            str: Generated response text
            
        Raises:
            RuntimeError: If engine fails to start
            MissingAPIKeysError: If API keys are missing for LLM requests
            ValueError: If validator fails
        """
        # Run Python code if this is Python code
        try:
            result = run_python_code(command, mode='interactive')
            return LamiaResult(result_text=str(result) if result is not None else "", typed_result=result, executor="python")
        except SyntaxError as e:
            logger.error(f"Syntax error: {e}", command)
            pass
        except Exception as e:
            logger.error(f"Python code execution failed: {e}")
            pass

        # Always create a fresh parser for each command to avoid reusing the
        # previous command's state (which caused the first‐command‐only bug).
        current_parser = CommandParser(command)

        response = await self._engine.execute(
            current_parser.command_type,
            current_parser.content,
        )
        return LamiaResult(result_text=response.raw_text, typed_result=response.result_type, executor=current_parser.command_type)

    def run(
        self,
        command: str,
        models: Union[Union[str, LLMModel], Tuple[Union[str, LLMModel], int]] = None,
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
                    models,
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

    def get_recent_validation_results(self, limit: Optional[int] = None):
        """Get recent validation results from the engine's validation manager."""
        return self._engine.get_recent_validation_results(limit)

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        # Engine cleans up automatically via __del__
        pass