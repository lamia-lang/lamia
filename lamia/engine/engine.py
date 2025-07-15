from typing import Optional, Dict, Any
import asyncio

from .config_provider import ConfigProvider
from .factories import ManagerFactory, ValidationStrategyFactory
from .validation_manager import ValidationManager
from lamia.command_types import CommandType
from lamia.validation.base import ValidationResult

class LamiaEngine:
    """Main engine for Lamia that orchestrates different domain managers."""
    
    def __init__(self, config_provider: ConfigProvider):
        """Initialize the Lamia engine."""
        self.config_provider = config_provider
        
        # Initialize factories
        self.validation_factory = ValidationStrategyFactory(self.config_provider)
        self.manager_factory = ManagerFactory(self.config_provider)
        
        # Initialize validation manager for centralized coordination and statistics
        self.validation_manager = ValidationManager()
        self._validation_enabled = self._is_validation_enabled()
    
    def _is_validation_enabled(self) -> bool:
        """Check if validation is enabled in config."""
        validation_config = self.config_provider.config.get('validation', {})
        return validation_config.get('enabled', False)
    
    async def execute(
        self,
        command_type: CommandType,
        content: str,
    ) -> ValidationResult:
        """Execute a request using the appropriate domain manager.
        
        Args:
            request_type: Type of request ('llm', 'fs', 'web', etc.)
            content: The content to process
            **kwargs: Additional parameters for the specific manager
            
        Returns:
            Response from the appropriate manager
        """
        
        # Create validation strategy for this command type
        validation_strategy = await self.validation_factory.get_strategy(command_type)
        
        # Get the appropriate manager with its validation strategy
        manager = await self.manager_factory.get_manager(command_type, validation_strategy)
        
        return await self.validation_manager.validate(command_type, manager, content)
    
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