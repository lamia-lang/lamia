"""
Main Lamia facade class.

This module provides the simplified Lamia interface that coordinates
between different subsystems (engine, adapters, validation).
"""

import asyncio
import logging
from typing import Any, Optional, List, Dict, Union, Tuple, Type

from lamia.async_bridge import EventLoopManager
from lamia.env_loader import load_env_files
from lamia.engine.engine import LamiaEngine
from lamia import LLMModel
from lamia._internal_types.model_retry import ModelWithRetries
from lamia.types import BaseType, ExternalOperationRetryConfig
from lamia.interpreter.commands import Command

from .result_types import LamiaResult
from .config_builder import build_config_from_dict, build_config_from_models
from .command_processor import process_string_command

logger = logging.getLogger(__name__)


class Lamia:
    """
    Main user interface for Lamia LLM engine.
    
    This class provides a simple interface for LLM interactions with automatic
    initialization and cleanup.
    
    Args:
        *models: Model names or Model objects (e.g., 'openai:gpt-4o', 'ollama', ...)
        api_keys: Optional dict of API keys (e.g., {'openai': 'sk-...'}).
        retry_config: Optional retry configuration.
        web_config: Optional web configuration.
    """
    
    def __init__(
        self, 
        *models: Union[Union[str, LLMModel], Tuple[Union[str, LLMModel], int]], 
        api_keys: Optional[dict] = None, 
        retry_config: Optional['ExternalOperationRetryConfig'] = None,
        web_config: Optional[Dict[str, Any]] = None,
    ):
        # Initialize engine - ready to use immediately!
        load_env_files()
        config_provider = build_config_from_models(models, api_keys, retry_config, web_config)
        self._engine = LamiaEngine(config_provider)

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "Lamia":
        """Create Lamia instance from configuration dictionary.
        
        The config dict can include:
        - model_chain: List of model specs with provider references
        - api_keys: Dict of API keys per provider
        - retry_config: Retry configuration settings
        - web_config: Web automation configuration
        - providers: Provider-specific model settings
        """
        config_provider = build_config_from_dict(config)
        instance = cls.__new__(cls)
        instance._engine = LamiaEngine(config_provider)
        return instance

    async def run_async(
        self,
        command: Union[str, Command], 
        return_type: Optional[Type[BaseType]] = None,
        *,
        models: Optional[List[ModelWithRetries]] = None,
        _full_result: bool = False,
    ) -> Union[Any, LamiaResult]:
        """
        Generate a response, trying Python code first, then LLM.
        
        Args:
            command: The command to execute (string or Command object)
            models: The models to use, if not provided, the default models will be used
            return_type: The expected return type for validation (optional)
            
        Returns:
            If return_type is None: Plain result (Any) for direct usage
            If return_type is specified: LamiaResult with validation info
            
        Raises:
            MissingAPIKeysError: If API keys are missing for LLM requests
            ValueError: If validator fails
            ExternalOperationPermanentError: If external service has permanent failure (API key issues, invalid requests)
            ExternalOperationRateLimitError: If external service rate limits are exceeded
            ExternalOperationTransientError: If external service has temporary failures (network issues, timeouts)
            ExternalOperationFailedError: If external service fails with unclassified error
        """
        # Handle Command objects vs strings differently
        if isinstance(command, Command):
            # Command object passed directly - skip Python execution and parsing
            parsed_command = command
        else:
            # String command - try Python first, then parse
            parsed_command, python_result = process_string_command(command)
            if python_result is not None:
                return python_result

        if models is not None:
            self._engine.config_provider.override_model_chain_with(models)

        response = await self._engine.execute(
            parsed_command,
            return_type=return_type
        )

        if models is not None:
            self._engine.config_provider.reset_model_chain()

        if return_type is None and not _full_result:
            return response.typed_result
        return LamiaResult(
            result_text=response.raw_text,
            typed_result=response.typed_result if return_type is not None else None,
            tracking_context=response.execution_context
        )

    def run(
        self,
        command: Union[str, Command], 
        return_type: Optional[Type[BaseType]] = None,
        *,
        models: Optional[List[ModelWithRetries]] = None,
    ) -> Union[Any, LamiaResult]:
        """
        Run a command synchronously.
        
        Args:
            command: The command to execute
            models: The models to use, if not provided, the default models will be used
            return_type: The expected return type for validation (optional)
        
        Returns:
            If return_type is None: Plain result (Any) for direct usage
            If return_type is specified: LamiaResult with validation info
        
        Raises:
            MissingAPIKeysError: If API keys are missing
            ValueError: If validator fails
            ExternalOperationPermanentError: If external service has permanent failure (API key issues, invalid requests)
            ExternalOperationRateLimitError: If external service rate limits are exceeded
            ExternalOperationTransientError: If external service has temporary failures (network issues, timeouts)
            ExternalOperationFailedError: If external service fails with unclassified error
            RuntimeError: If run() is called inside an async context
        """
        return EventLoopManager.run_coroutine(
            self.run_async(
                command,
                return_type,
                models=models,
            )
        )

    def get_validation_stats(self) -> Optional[Any]:
        """Get validation statistics."""
        return self._engine.get_validation_stats()

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self._engine.cleanup()

    def __del__(self):
        """Clean up resources when the Lamia instance is destroyed."""
        try:
            EventLoopManager.run_coroutine(self._engine.cleanup())
            EventLoopManager.shutdown()
        except Exception as e:
            logger.warning(f"Error during Lamia cleanup: {e}")