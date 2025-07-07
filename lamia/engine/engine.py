import asyncio
from typing import Optional, Dict, Type, Any, Union
import logging
from pathlib import Path

from .config_manager import ConfigManager
from .llm.llm_manager import LLMManager
from .validation_manager import ValidationManager
from lamia.adapters.llm.base import LLMResponse

logger = logging.getLogger(__name__)

class LamiaEngine:
    """Main engine for Lamia that orchestrates different domain managers."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the Lamia engine.
        
        Args:
            config: Configuration dictionary.
        """
        self.config_manager = ConfigManager(config)
        
        # Initialize domain managers
        self.llm_manager = LLMManager(self.config_manager)
        self.validation_manager = ValidationManager(self.config_manager)
        # TODO: Add other managers as they're implemented
        # self.fs_manager = FSManager(self.config_manager)
        # self.web_manager = WebManager(self.config_manager)
        
        self._initialized = False
    
    async def _setup_validation(self):
        """Set up the validation manager."""
        await self.validation_manager.initialize()
        if self.validation_manager.enabled:
            logger.info("Validation enabled")
        else:
            logger.info("Validation disabled")
    
    async def start(self):
        """Start the Lamia engine and initialize all managers."""
        try:
            logger.info("Starting Lamia engine")
            
            # Check API keys early
            self.llm_manager.check_all_required_api_keys()
            
            # Set up validation if enabled
            await self._setup_validation()
            
            self._initialized = True
            logger.info("Engine started successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to start engine: {e}")
            return False
    
    async def stop(self):
        """Stop the Lamia engine and cleanup resources."""
        try:
            # Stop all managers
            await self.llm_manager.close()
            await self.validation_manager.close()
            # TODO: Stop other managers when implemented
            logger.info("Engine stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping engine: {str(e)}")
    
    async def execute(
        self,
        request_type: str,
        content: str,
        **kwargs
    ) -> Any:
        """Execute a request using the appropriate domain manager.
        
        Args:
            request_type: Type of request ('llm', 'fs', 'web', etc.)
            content: The content to process
            **kwargs: Additional parameters for the specific manager
            
        Returns:
            Response from the appropriate manager
        """
        if request_type == 'llm':
            return await self._execute_llm_request(content, **kwargs)
        # TODO: Add other request types
        # elif request_type == 'fs':
        #     return await self._execute_fs_request(content, **kwargs)
        # elif request_type == 'web':
        #     return await self._execute_web_request(content, **kwargs)
        else:
            raise ValueError(f"Unsupported request type: {request_type}")
    
    async def _execute_llm_request(
        self,
        prompt: str,
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """Execute an LLM request using the LLM manager.
        
        Args:
            prompt: The input prompt
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            
        Returns:
            LLMResponse containing the generated text and metadata
        """
        if not self._initialized:
            raise RuntimeError("Engine not initialized. Call start() first.")
            
        model_name = self.config_manager.get_default_model()
        config = self.config_manager.get_model_config(model_name)
        
        # Use config values if not overridden
        temperature = temperature if temperature is not None else config.get('temperature')
        max_tokens = max_tokens if max_tokens is not None else config.get('max_tokens')
        
        # Check if validation is enabled
        if self.validation_manager.enabled:
            # Use validation manager for validated responses
            return await self.validation_manager.validate_llm_response(
                llm_manager=self.llm_manager,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )
        else:
            # Use LLM manager directly (no validation)
            return await self.llm_manager.generate(
                prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )

    def get_validation_stats(self):
        """Get validation statistics from the validation manager."""
        return self.validation_manager.get_validation_stats()
    
    def get_recent_validation_results(self, limit: Optional[int] = None):
        """Get recent validation results from the validation manager."""
        return self.validation_manager.get_recent_results(limit)

    async def __aenter__(self):
        """Allow using the engine as an async context manager."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup when exiting the context manager."""
        await self.stop() 