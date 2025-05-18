import asyncio
from typing import Optional, Dict, Type, Any
import logging
from pathlib import Path

from .config_manager import ConfigManager
from .llm_manager import create_adapter_from_config
from adapters.llm.base import LLMResponse
from adapters.llm.validation.base import BaseValidator
from adapters.llm.validation.validators import (
    HTMLValidator,
    JSONValidator,
    RegexValidator,
    LengthValidator
)
from adapters.llm.validation.custom_loader import (
    load_validator_from_file,
    load_validator_from_function
)
from adapters.llm.validation.strategy import ValidationStrategy, RetryConfig

logger = logging.getLogger(__name__)

class LamiaEngine:
    """Main engine for Lamia that handles runtime configuration and execution."""
    
    # Registry of built-in validators
    BUILTIN_VALIDATORS: Dict[str, Type[BaseValidator]] = {
        "html": HTMLValidator,
        "json": JSONValidator,
        "regex": RegexValidator,
        "length": LengthValidator,
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the Lamia engine.
        
        Args:
            config_path: Optional path to config file. If None, uses default lookup paths.
        """
        self.config_manager = ConfigManager(config_path)
        self.adapter = None
        self.validation_strategy = None
        self._setup_logging()
    
    def _setup_logging(self):
        """Configure logging for the engine."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
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
    
    def _get_validator_registry(self) -> Dict[str, Type[BaseValidator]]:
        """Get combined registry of built-in and custom validators."""
        registry = self.BUILTIN_VALIDATORS.copy()
        
        # Add custom validators from config
        validation_config = self.config_manager.config.validation
        if validation_config.validators:
            for validator_config in validation_config.validators:
                if validator_config.get("type") in ["custom_file", "custom_function"]:
                    try:
                        validator_class = self._load_custom_validator(validator_config)
                        if validator_class:
                            registry[validator_class.name] = validator_class
                    except Exception as e:
                        logger.error(f"Error loading custom validator: {str(e)}")
        
        return registry
    
    def _setup_validation(self):
        """Set up the validation strategy if enabled in config."""
        validation_config = self.config_manager.config.validation
        if validation_config.enabled:
            retry_config = RetryConfig(
                max_retries=validation_config.max_retries,
                fallback_models=validation_config.fallback_models,
                validators=validation_config.validators
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
        """Start the Lamia engine."""
        try:
            config = self.config_manager.get_active_model_config()
            model_name = self.config_manager.config.default_model
            
            logger.info(f"Starting Lamia with {model_name} model")
            logger.info(f"Using configuration from: {self.config_manager.config_path}")
            
            self.adapter = create_adapter_from_config(self.config_manager)
            await self.adapter.initialize()
            
            # Set up validation if enabled
            self._setup_validation()
            
            logger.info("Engine started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start engine: {str(e)}")
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
        if not self.adapter:
            raise RuntimeError("Engine not started. Call start() first.")
        
        config = self.config_manager.get_active_model_config()
        
        # Use config values if not overridden
        temperature = temperature if temperature is not None else config.temperature
        max_tokens = max_tokens if max_tokens is not None else config.max_tokens
        
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