from typing import Optional, Dict, Any
import asyncio

from .config_provider import ConfigProvider
from .factories import ManagerFactory, ValidationStrategyFactory
from .validation_manager import ValidationManager
from lamia.command_types import CommandType

class LamiaEngine:
    """Main engine for Lamia that orchestrates different domain managers."""
    
    def __init__(self, config_provider: ConfigProvider):
        """Initialize the Lamia engine."""
        self.config_provider = config_provider
        
        # Initialize factories (DIP compliance)
        self.manager_factory = ManagerFactory(self.config_provider)
        self.validation_factory = ValidationStrategyFactory(self.config_provider)
        
        # Initialize validation manager for centralized coordination and statistics
        self.validation_manager = ValidationManager(self.validation_factory)
        self._validation_enabled = self._is_validation_enabled()
    
    def _is_validation_enabled(self) -> bool:
        """Check if validation is enabled in config."""
        validation_config = self.config_provider.config.get('validation', {})
        return validation_config.get('enabled', False)
    
    async def execute(
        self,
        command_type: CommandType,
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
        
        # Get the appropriate manager
        manager = await self.manager_factory.get_manager(command_type)
        
        # Apply domain-specific parameter handling (for LLM)
        if command_type == CommandType.LLM:
            '''request_model = kwargs.get('model')
            if request_model is not None:
                if isinstance(request_model, str):
                    model_name = request_model
                else:
                    model_name = request_model.model
                    kwargs['temperature'] = request_model.temperature
                    kwargs['max_tokens'] = request_model.max_tokens
                    kwargs['top_p'] = request_model.top_p
                    kwargs['top_k'] = request_model.top_k
                    kwargs['frequency_penalty'] = request_model.frequency_penalty
                    kwargs['presence_penalty'] = request_model.presence_penalty
                    kwargs['stream'] = request_model.stream
            else:
                model_name = self.config_provider.get_primary_model().model.model

            # Use config values if not overridden
            config = self.config_provider.get_primary_model().model.get_config()

            kwargs['temperature'] = kwargs.get('temperature') or config.get('temperature')
            kwargs['max_tokens'] = kwargs.get('max_tokens') or config.get('max_tokens')
            kwargs['top_p'] = kwargs.get('top_p') or config.get('top_p')
            kwargs['top_k'] = kwargs.get('top_k') or config.get('top_k')
            kwargs['frequency_penalty'] = kwargs.get('frequency_penalty') or config.get('frequency_penalty')
            kwargs['presence_penalty'] = kwargs.get('presence_penalty') or config.get('presence_penalty')
            kwargs['stream'] = kwargs.get('stream') or config.get('stream')'''
            pass
        

        return await self.validation_manager.validate(command_type, manager, content, **kwargs)
    
    def get_validation_stats(self):
        """Get validation statistics from the validation manager."""
        return self.validation_manager.get_validation_stats()
    
    def get_recent_validation_results(self, limit: Optional[int] = None):
        """Get recent validation results from the validation manager."""
        return self.validation_manager.get_recent_results(limit)

    def __del__(self):
        """Cleanup is now handled automatically by individual components."""
        # No more complex async cleanup needed!
        # - Adapters clean themselves up via the resource manager
        # - ValidationManager handles its own cleanup
        # - Factories handle their own cleanup
        pass 