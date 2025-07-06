import asyncio
from typing import Optional, Dict, Type, Any, Union
import logging
from pathlib import Path
import importlib
import pkgutil
import inspect
import sys
import os

from .config_manager import ConfigManager
from .llm_manager import create_adapter_from_config
from lamia.adapters.llm.base import LLMResponse
from lamia.validation.base import BaseValidator
from lamia.validation.custom_loader import (
    load_validator_from_file,
    load_validator_from_function
)
from lamia.adapters.llm.strategy import ValidationStrategy, RetryConfig
from lamia.validation import validators as validators_pkg
from lamia.validation.validator_registry import ValidatorRegistry

logger = logging.getLogger(__name__)

class LamiaEngine:
    """Main engine for Lamia that handles runtime configuration and execution."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the Lamia engine.
        
        Args:
            config: Configuration dictionary.
        """
        self.config_manager = ConfigManager(config)
        self.adapter = None
        self.validation_strategy = None
        self._adapter_initialized = False
    
    async def _setup_validation(self):
        """Set up the validation strategy if enabled in config."""
        validation_config = self.config_manager.config.get('validation', {})
        if validation_config.get('enabled'):
            retry_config = RetryConfig(
                max_retries=validation_config.get('max_retries'),
                fallback_models=validation_config.get('fallback_models'),
                validators=validation_config.get('validators')
            )
            # Use ValidatorRegistry for registry
            ext_folder = self.config_manager.get_extensions_folder()
            validator_registry = ValidatorRegistry(self.config_manager.config, ext_folder)
            registry = await validator_registry.get_registry()
            self.validation_strategy = ValidationStrategy(
                config=retry_config,
                validator_registry=registry
            )
            logger.info("Validation strategy enabled")
        else:
            self.validation_strategy = None
            logger.info("Validation strategy disabled")
    
    async def start(self):
        """Start the Lamia engine. Only initialize the adapter if it's a remote provider."""
        try:
            model_name = self.config_manager.get_default_model()
            logger.info(f"Starting Lamia with {model_name} model")
            
            # Always create the adapter, but only initialize remote ones immediately
            self.adapter = create_adapter_from_config(self.config_manager)
            if self.adapter.is_remote():
                await self.adapter.initialize()
                self._adapter_initialized = True
            # Local adapters will be initialized lazily in generate() when needed
            
            # Set up validation if enabled
            await self._setup_validation()
            logger.info("Engine started successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to start engine: {e}")
            return False
    
    async def stop(self):
        """Stop the Lamia engine and cleanup resources."""
        if self.adapter:
            try:
                await self.adapter.close()
                logger.info("Engine stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping engine: {str(e)}")
    
    async def generate(
        self,
        prompt: str,
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """Generate a response using the configured model.
        
        Args:
            prompt: The input prompt
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            
        Returns:
            LLMResponse containing the generated text and metadata
        """
        model_name = self.config_manager.get_default_model()
        config = self.config_manager.get_model_config(model_name)
        # Use config values if not overridden
        temperature = temperature if temperature is not None else config.get('temperature')
        max_tokens = max_tokens if max_tokens is not None else config.get('max_tokens')
        # Lazily initialize the adapter if needed (for local models)
        if not self._adapter_initialized:
            await self.adapter.initialize()
            self._adapter_initialized = True
        # If validation is enabled, use the validation strategy
        if self.validation_strategy:
            return await self.validation_strategy.execute_with_retries(
                primary_adapter=self.adapter,
                prompt=prompt,
                create_adapter_fn=lambda model: create_adapter_from_config(
                    self.config_manager,
                    override_model=model
                ),
                temperature=temperature,
                max_tokens=max_tokens
            )
        # Otherwise, just generate normally
        return await self.adapter.generate(
            prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )

    async def __aenter__(self):
        """Allow using the engine as an async context manager."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup when exiting the context manager."""
        await self.stop() 