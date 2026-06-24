"""
Main Lamia facade class.

This module provides the simplified Lamia interface that coordinates
between different subsystems (engine, adapters, validation).
"""

import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional, List, Dict, Union, Tuple, Type

from lamia.async_bridge import EventLoopManager
from lamia.env_loader import load_env_files
from lamia.engine.engine import LamiaEngine
from lamia import LLMModel
from lamia._internal_types.model_retry import ModelWithRetries
from lamia.types import BaseType, ExternalOperationRetryConfig
from lamia.type_converter import create_validator
from lamia.interpreter.commands import Command
from lamia.engine.managers.llm.files_context_manager import get_current_source_file
from lamia.validation.base import TrackingContext

from .result_types import LamiaResult
from .config_builder import build_config_from_dict, build_config_from_models, _build_model_chain_from_specs
from .command_processor import process_string_command

logger = logging.getLogger(__name__)

_PATH_PREFIXES = ('./', '../', '/', '~/')


def _resolve_local_file(command: str) -> Optional[Path]:
    """Return resolved Path if *command* is an explicit local file path.

    Rules:
    - Must be single-line
    - URLs are never treated as files
    - Must use explicit path prefixes: ./, ../, /, ~/
    - Unquoted whitespace invalidates file detection
    - Spaces are allowed only in shell-like forms:
      - quoted string: "./path with spaces/file"
      - escaped spaces: ./path\ with\ spaces/file
    """
    stripped = command.strip()
    if not stripped or '\n' in stripped:
        return None
    if stripped.startswith(('http://', 'https://')):
        return None

    candidate_text = stripped
    quoted = (
        (stripped.startswith('"') and stripped.endswith('"'))
        or (stripped.startswith("'") and stripped.endswith("'"))
    )
    if quoted:
        candidate_text = stripped[1:-1]
    elif re.search(r"(?<!\\)\s", stripped):
        # Unescaped whitespace means this is not a file-path token.
        return None

    looks_like_path = candidate_text.startswith(_PATH_PREFIXES)
    if not looks_like_path:
        return None

    # Support Linux-style escaped spaces in path tokens.
    normalized = candidate_text.replace(r"\ ", " ")
    if re.search(r"\s", normalized) and not (quoted or r"\ " in candidate_text):
        return None

    if normalized.startswith('~/'):
        candidate = Path(normalized).expanduser()
    elif not os.path.isabs(normalized):
        source = get_current_source_file()
        base = Path(source).parent if source else Path.cwd()
        candidate = base / normalized
    else:
        candidate = Path(normalized)

    resolved = candidate.resolve()
    if resolved.is_file():
        return resolved
    raise FileNotFoundError(f"File not found: {candidate_text} (resolved to {resolved})")


def _normalize_models(models) -> Optional[List[ModelWithRetries]]:
    """Convert str or list-of-str model specs into List[ModelWithRetries]."""
    if models is None:
        return None
    if isinstance(models, str):
        return _build_model_chain_from_specs((models,))
    if isinstance(models, list):
        if not models:
            return None
        if isinstance(models[0], ModelWithRetries):
            return models
        return _build_model_chain_from_specs(tuple(models))
    return models


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
        load_env_files()
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
        _append_context: Optional[str] = None,
        _target_encoding: Optional[str] = None,
        _function_name: Optional[str] = None,
    ) -> Union[Any, LamiaResult]:
        """
        Generate a response, trying Python code first, then LLM.
        
        Args:
            command: The command to execute (string or Command object)
            models: The models to use, if not provided, the default models will be used
            return_type: The expected return type for validation (optional)
            _append_context: Existing file content to prepend as context (used by File append)
            
        Returns:
            If return_type is None: for lamia f(): functions without return types
            If return_type is specified: LamiaResult with validation info
            
        Raises:
            MissingAPIKeysError: If API keys are missing for LLM requests
            ValueError: If validator fails
            ExternalOperationPermanentError: If external service has permanent failure (API key issues, invalid requests)
            ExternalOperationRateLimitError: If external service rate limits are exceeded
            ExternalOperationTransientError: If external service has temporary failures (network issues, timeouts)
        """
        # Prepend existing file content as context for append operations
        if _append_context and isinstance(command, str):
            command = (
                f"Existing file content (append new rows only, do NOT repeat headers or existing data):\n"
                f"{_append_context}\n\n{command}"
            )

        # Handle Command objects vs strings differently
        if isinstance(command, Command):
            parsed_command = command
        else:
            local_path = _resolve_local_file(command)
            if local_path is not None:
                return await self._read_local_file(local_path, return_type, _full_result)

            parsed_command, python_result = process_string_command(command)
            if python_result is not None:
                return python_result

        if _target_encoding:
            parsed_command.target_encoding = _target_encoding

        self._engine.hook_runner.set_context(
            function_name=_function_name,
            return_type=return_type.__name__ if return_type else None,
        )

        normalized_models = _normalize_models(models)
        if normalized_models is not None:
            self._engine.config_provider.override_model_chain_with(normalized_models)

        response = await self._engine.execute(
            parsed_command,
            return_type=return_type
        )

        if normalized_models is not None:
            self._engine.config_provider.reset_model_chain()

        if _full_result:
            return LamiaResult(
                result_text=response.validated_text or response.raw_text or "",
                typed_result=response.typed_result if return_type is not None else None,
                tracking_context=response.execution_context,
            )
        if return_type is None:
            if not response.is_valid and isinstance(command, Command):
                raise ValueError(response.error_message or "Command execution failed")
            return response.typed_result or response.raw_text # for no return action both typed_result and raw_text will be None and None will be returned
        if not response.is_valid:
            raise ValueError(response.error_message or "Validation failed for requested return type")
        if response.typed_result is not None:
            return response.typed_result
        if response.validated_text is not None:
            return response.validated_text
        return response.raw_text

    async def _read_local_file(
        self,
        path: Path,
        return_type: Optional[Type[BaseType]],
        _full_result: bool,
    ) -> Union[Any, LamiaResult]:
        """Read a local file and validate/convert it according to *return_type*."""
        raw_text = path.read_text(encoding='utf-8')

        ctx = TrackingContext(
            data_provider_name="local_file",
            command_type="file_read",
            metadata={"path": str(path)},
        )

        if return_type is not None:
            validator = create_validator(return_type)
            result = await validator.validate(raw_text, execution_context=ctx)
            if not result.is_valid:
                raise ValueError(
                    f"Local file '{path}' failed validation: {result.error_message}"
                )
            typed_result = result.typed_result if result.typed_result is not None else result.validated_text
            validated_text = result.validated_text or raw_text
        else:
            typed_result = raw_text
            validated_text = raw_text

        if _full_result:
            return LamiaResult(result_text=validated_text, typed_result=typed_result, tracking_context=ctx)
        return typed_result

    def run(
        self,
        command: Union[str, Command], 
        return_type: Optional[Type[BaseType]] = None,
        *,
        models: Optional[List[ModelWithRetries]] = None,
        _full_result: bool = False,
        _append_context: Optional[str] = None,
        _target_encoding: Optional[str] = None,
        _function_name: Optional[str] = None,
    ) -> Union[Any, LamiaResult]:
        """
        Run a command synchronously.
        
        Args:
            command: The command to execute
            models: The models to use, if not provided, the default models will be used
            return_type: The expected return type for validation (optional)
            _full_result: If True, return LamiaResult with both raw text and typed result
            _append_context: Existing file content to prepend as context (used by File append)
        
        Returns:
            If return_type is None: Plain result (Any) for direct usage
            If return_type is specified: LamiaResult with validation info
        
        Raises:
            MissingAPIKeysError: If API keys are missing
            ValueError: If validator fails
            ExternalOperationPermanentError: If external service has permanent failure (API key issues, invalid requests)
            ExternalOperationRateLimitError: If external service rate limits are exceeded
            ExternalOperationTransientError: If external service has temporary failures (network issues, timeouts)
            RuntimeError: If run() is called inside an async context
        """
        return EventLoopManager.run_coroutine(
            self.run_async(
                command,
                return_type,
                models=models,
                _append_context=_append_context,
                _full_result=_full_result,
                _target_encoding=_target_encoding,
                _function_name=_function_name,
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