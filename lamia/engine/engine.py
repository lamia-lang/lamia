from typing import Optional, Dict, Any
import asyncio

from .config_manager import ConfigManager
from .factories import ManagerFactory, ValidationStrategyFactory
from .validation_manager import ValidationManager
from lamia.command_types import CommandType

class LamiaEngine:
    """Main engine for Lamia that orchestrates different domain managers."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the Lamia engine."""
        self.config_manager = ConfigManager(config)
        
        # Initialize factories (DIP compliance)
        self.manager_factory = ManagerFactory(self.config_manager)
        self.validation_factory = ValidationStrategyFactory(self.config_manager)
        
        # Initialize validation manager for centralized coordination and statistics
        self.validation_manager = ValidationManager(self.validation_factory)
        self._validation_enabled = self._is_validation_enabled()
    
    def _is_validation_enabled(self) -> bool:
        """Check if validation is enabled in config."""
        validation_config = self.config_manager.config.get('validation', {})
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
            model_name = self.config_manager.get_default_model()
            config = self.config_manager.get_model_config(model_name)
            
            # Use config values if not overridden
            kwargs['temperature'] = kwargs.get('temperature') or config.get('temperature')
            kwargs['max_tokens'] = kwargs.get('max_tokens') or config.get('max_tokens')
        
        # Engine makes routing decision based on validation enabled flag
        if self._validation_enabled:
            # Use validation manager for coordination and statistics
            return await self.validation_manager.validate(command_type, manager, content, **kwargs)
        else:
            # Use manager directly (no validation)
            return await manager.execute(content, **kwargs)
    
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