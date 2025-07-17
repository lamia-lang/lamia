from typing import Optional, Dict, Any, List

from .config_provider import ConfigProvider
from .factories import ManagerFactory, ValidationStrategyFactory
from .validation_manager import ValidationManager
from lamia.command_types import CommandType
from lamia.validation.base import ValidationResult
from lamia.validation.validator_registry import ValidatorRegistry
from lamia.validation.base import BaseValidator


class LamiaEngine:
    """Main engine for Lamia that orchestrates different domain managers."""
    
    def __init__(self, config_provider: ConfigProvider):
        """Initialize the Lamia engine."""
        self.config_provider = config_provider

        # Initialize factories
        self.validation_factory = ValidationStrategyFactory()
        self.manager_factory = ManagerFactory(config_provider)

        # Build validator registry (allows project / user extensions)
        ext_folder = config_provider.get_extensions_folder()
        registry = ValidatorRegistry(ext_folder, enable_contract_checking=False)
        self.registry = registry.get_registry()
        
        # Initialize validation manager for centralized coordination and statistics
        self.validation_manager = ValidationManager()
    
    async def execute(
        self,
        command_type: CommandType,
        content: str,
        validators: Optional[List[BaseValidator]] = None,
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
        if validators is not None:
            validators = self.config_provider.get_validators()

        validation_strategy = await self.validation_factory.get_strategy(command_type, validators)
        
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