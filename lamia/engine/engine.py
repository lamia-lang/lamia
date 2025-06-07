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
from lamia.adapters.llm.validation.base import BaseValidator
from lamia.adapters.llm.validation.custom_loader import (
    load_validator_from_file,
    load_validator_from_function
)
from lamia.adapters.llm.validation.strategy import ValidationStrategy, RetryConfig
from lamia.adapters.llm.validation import validators as validators_pkg

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
    
    def _load_custom_validator(self, validator_config: dict) -> Optional[Type[BaseValidator]]:
        """Load a custom validator from file or function."""
        validator_type = validator_config.get("type")
        
        if validator_type == "custom_file":
            file_path = validator_config.get("path")
            if not file_path:
                logger.error("Missing 'path' in custom_file validator config")
                return None
            return load_validator_from_file(file_path)
            
        elif validator_type == "custom_function":
            func_path = validator_config.get("path")
            if not func_path:
                logger.error("Missing 'path' in custom_function validator config")
                return None
            return load_validator_from_function(func_path)
            
        return None
    
    def _discover_validators_recursively(self, package) -> dict:
        """Recursively discover all validator classes in a package and its submodules."""
        validator_class_map = {}
        for finder, name, ispkg in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
            module = importlib.import_module(name)
            # Add classes from this module
            for _, cls in inspect.getmembers(module, inspect.isclass):
                if (
                    cls.__module__ == module.__name__ and
                    issubclass(cls, BaseValidator) and
                    hasattr(cls, 'name') and
                    callable(getattr(cls, 'name'))
                ):
                    validator_class_map[cls.name()] = cls
            # If it's a package, recurse
            if ispkg:
                try:
                    validator_class_map.update(self._discover_validators_recursively(module))
                except Exception as e:
                    logger.warning(f"Could not import submodule {name}: {e}")
        return validator_class_map

    def _discover_validators_in_path(self, path: str) -> dict:
        """Discover all validator classes in a given filesystem path."""
        import importlib.util
        import inspect
        validator_class_map = {}
        if not os.path.isdir(path):
            return validator_class_map
        sys.path.insert(0, path)
        for file in os.listdir(path):
            if file.endswith(".py") and not file.startswith("__"):
                module_name = file[:-3]
                try:
                    spec = importlib.util.spec_from_file_location(module_name, os.path.join(path, file))
                    if not spec or not spec.loader:
                        continue
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    for _, cls in inspect.getmembers(module, inspect.isclass):
                        if (
                            issubclass(cls, BaseValidator)
                            and cls is not BaseValidator
                            and hasattr(cls, 'name')
                            and callable(getattr(cls, 'name'))
                        ):
                            validator_class_map[cls.name()] = cls
                except Exception as e:
                    logger.warning(f"Could not import validator from {file}: {e}")
        sys.path.pop(0)
        return validator_class_map

    def _get_validator_registry(self) -> Dict[str, BaseValidator]:
        """Preload all validators in the validators folder and extensions, checking for name conflicts."""
        # Built-in validators
        validator_class_map = self._discover_validators_recursively(validators_pkg)
        # Load from extensions/validators if present
        ext_folder = self.config_manager.get_extensions_folder()
        ext_validators_path = os.path.join(os.getcwd(), ext_folder, "validators")
        ext_validator_class_map = self._discover_validators_in_path(ext_validators_path)
        # Check for name conflicts
        conflict_names = set(validator_class_map.keys()) & set(ext_validator_class_map.keys())
        if conflict_names:
            raise ValueError(f"User-defined validator name(s) conflict with built-in validators: {', '.join(conflict_names)}")
        # Merge
        validator_class_map.update(ext_validator_class_map)
        registry = {}
        validation_config = self.config_manager.config.get('validation', {})
        if validation_config.get('validators'):
            for validator_config in validation_config['validators']:
                vtype = validator_config.get("type")
                strict = validator_config.get("strict", True)
                config_copy = validator_config.copy()
                config_copy.pop("type", None)
                config_copy.pop("strict", None)
                if vtype in validator_class_map:
                    cls = validator_class_map[vtype]
                    registry[cls.name()] = cls
                elif vtype in ["custom_file", "custom_function"]:
                    try:
                        validator_class = self._load_custom_validator(validator_config)
                        if validator_class:
                            registry[validator_class.name()] = validator_class
                    except Exception as e:
                        logger.error(f"Error loading custom validator: {str(e)}")
                else:
                    raise ValueError(f"Unknown validator type: {vtype}")
        return registry
    
    def _setup_validation(self):
        """Set up the validation strategy if enabled in config."""
        validation_config = self.config_manager.config.get('validation', {})
        if validation_config.get('enabled'):
            retry_config = RetryConfig(
                max_retries=validation_config.get('max_retries'),
                fallback_models=validation_config.get('fallback_models'),
                validators=validation_config.get('validators')
            )
            self.validation_strategy = ValidationStrategy(
                config=retry_config,
                validator_registry=self._get_validator_registry()
            )
            logger.info("Validation strategy enabled")
        else:
            self.validation_strategy = None
            logger.info("Validation strategy disabled")
    
    async def start(self):
        """Start the Lamia engine. Only initialize the adapter if the default model is not a local provider."""
        try:
            model_name = self.config_manager.get_default_model()
            logger.info(f"Starting Lamia with {model_name} model")
            if self.config_manager.is_remote_provider(model_name):
                self.adapter = create_adapter_from_config(self.config_manager)
                await self.adapter.initialize()
            else:
                self.adapter = None  # Will be lazily initialized in generate()
            # Set up validation if enabled
            self._setup_validation()
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
        if self.adapter is None:
            self.adapter = create_adapter_from_config(self.config_manager)
            await self.adapter.initialize()
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