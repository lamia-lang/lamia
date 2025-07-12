from lamia.engine.engine import LamiaEngine
import asyncio
from typing import Any, Optional, List, Dict, Union, Tuple
from lamia.interpreter.python_runner import run_python_code
from lamia.command_parser import CommandParser
from dataclasses import dataclass
from lamia.engine.config_provider import ConfigProvider

@dataclass
class Model:
    model: str
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    stream: Optional[bool] = None

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
        *models: Union[Union[str, Model], Tuple[Union[str, Model], int]], 
        api_keys: Optional[dict] = None, 
        validators: Optional[List[Any]] = None, 
    ):
        # Initialize engine - ready to use immediately!
        self._engine = LamiaEngine(self._build_config(models, api_keys, validators, None))
        
        # Initialize command parser instance
        self._command_parser = None

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "Lamia":
        def constuct_full_model_name(config, model_name):
            if ":" in model_name:
                return model_name
            else:
                if "providers" not in config:
                    raise ValueError("Providers are not configured.")
                
                providers = config["providers"]
                provider_name = model_name
                if provider_name not in providers:
                    raise ValueError(f"Provider {provider_name} is not configured.")
                
                if not providers[provider_name]["enabled"]:
                    raise ValueError(f"Provider {provider_name} is not enabled. Please enable it in the config")
                
                if "default_model" not in providers[provider_name]:
                    raise ValueError(f"Provider {provider_name} does not have a default model. Please provide a default model in the config")
                
                model_family_name = providers[provider_name]["default_model"]
                full_model_name = f"{provider_name}:{model_family_name}"
            return full_model_name

        default_model = config['default_model']
        if default_model is not None:
            try:
                models = [constuct_full_model_name(config, default_model)]
            except ValueError as e:
                raise ValueError(f"{e}. Please provide full model name like 'openai:gpt-4o' for default-model or fix the config for {default_model}")
        
        if "validation" in config:
            if "fallback_models" in config["validation"]:
                if default_model is not None:
                    raise ValueError("Fallback models are not supported when no default model is provided. Please provide a default model in the config")

                fallback_models = config["validation"]["fallback_models"]
                for model in fallback_models:
                    try:
                        models.extend(constuct_full_model_name(config, model))
                    except ValueError as e:
                        raise ValueError(f"{e}. Please provide full model name like 'openai:gpt-4o' in the fallback-models list or fix the config for {model}")

        return cls(
            models,
            validators=config["validation"]["validators"] if "validation" in config and "validators" in config["validation"] else None
        )

    def _get_provider_name(self, model_obj: "Model") -> str:
        """Extract provider name from a Model instance.
        A model can be expressed either as "provider"  (e.g. "openai") or
        "provider:model_family" (e.g. "openai:gpt-4o").  In both cases we only
        need the provider part for routing / config keys.
        """
        return model_obj.model.split(":", 1)[0]

    def _build_config(
        self,
        models: Union[Union[str, Model], Tuple[Union[str, Model], int]],
        api_keys: Optional[dict], 
        validators: Optional[List[Any]], 
        config: Optional[Dict[str, Union[str, int, float, bool]]]
    ) -> Dict[str, Any]:

        # If the user supplied a ready-made config dict we keep it verbatim.
        if config is not None:
            return config

        DEFAULT_RETRIES = 1
        # Convert the *models* var-tuple into a proper list for iteration.
        incoming_models = list(models) if models else []

        # If nothing was supplied default to a local Ollama setup.
        if not incoming_models:
            incoming_models = ["ollama"]

        models_and_retries: List[Tuple[Model, int]] = []
        for item in incoming_models:
            retries = DEFAULT_RETRIES

            # Unpack `(something, retries)`
            if isinstance(item, tuple):
                item, retries = item  # type: ignore[misc]

            # Turn strings into ``Model`` instances
            if isinstance(item, str):
                item = Model(model=item)
            elif not isinstance(item, Model):
                raise TypeError(
                    "Each model spec must be a str, Model or (spec, retries) tuple"
                )

            models_and_retries.append((item, retries))

        # Assemble the final config dict
        config_dict: Dict[str, Any] = {
            "default_model": models_and_retries[0],
            "fallback_models": models_and_retries[1:],
            "validators": validators or [],
            "api_keys": api_keys,
        }    

        return ConfigProvider(config_dict)

    # No more ceremony needed - engine is ready on creation!

    async def run_async(
        self,
        command: str, 
        models: Union[Union[str, Model], Tuple[Union[str, Model], int]] = None, 
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

        parser_kwargs = dict(self._command_parser.kwargs)  # copy
        if models is not None:
            parser_kwargs['models'] = models

        response = await self._engine.execute(
            self._command_parser.command_type,
            self._command_parser.content,
            **parser_kwargs,
        )
        return LamiaResult(result=response.text, executor=response.model)

    def run(
        self,
        command: str,
        models: Union[Union[str, Model], Tuple[Union[str, Model], int]] = None,
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

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        # Engine cleans up automatically via __del__
        pass