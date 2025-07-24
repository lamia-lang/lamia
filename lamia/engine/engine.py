from typing import Optional, Dict, Any, List, Type

from .config_provider import ConfigProvider
from .factories import ManagerFactory, ValidatorFactory
from .validation_manager import ValidationManager
from lamia.command_types import CommandType
from lamia.validation.base import ValidationResult, BaseValidator
from lamia.validation.validator_registry import ValidatorRegistry
from lamia.types import BaseType

import logging

logger = logging.getLogger(__name__)

class LamiaEngine:
    """Main engine for Lamia that orchestrates different domain managers."""
    
    def __init__(self, config_provider: ConfigProvider):
        """Initialize the Lamia engine."""
        self.config_provider = config_provider

        # Initialize factories
        self.validator_factory = ValidatorFactory()
        self.manager_factory = ManagerFactory(config_provider)
        
        # Initialize registry for built-in and user-defined validators
        self.validator_registry = ValidatorRegistry(extensions_folder=config_provider.get_extensions_folder())
        
        # Initialize validation manager for centralized coordination and statistics
        self.validation_manager = ValidationManager()

    async def execute(
        self,
        command_type: CommandType,
        content: str,
        return_type: Optional[Type[BaseType]] = None,
    ) -> ValidationResult:
        """Execute a request using the appropriate domain manager.
        
        Args:
            command_type: Type of request ('llm', 'fs', 'web', etc.)
            content: The content to process
            validators: Optional list of validator classes to use.
                      If not provided, uses validators from config.
            
        Returns:
            Response from the appropriate manager
        """
                
        # Create validator
        if return_type is not None:
            validator = self.validator_factory.get_validator(
                    command_type, 
                    return_type
                )
            # Check contracts for non-built-in validators
            validator_type = type(validator)
            passed, violations = self.validator_registry.check_validator(validator_type)
            if not passed:
                raise ValueError(f"Validator {validator_type.__name__} does not pass contract checks: {violations}")
        else:
            validator = None
        
        # Get the appropriate manager with its validation strategy
        manager = self.manager_factory.get_manager(command_type)
        
        return await self.validation_manager.validate(command_type, manager, content, validator)
    
    def get_validation_stats(self):
        """Get validation statistics from the validation manager."""
        return self.validation_manager.get_validation_stats()
    
    def get_recent_validation_results(self, limit: Optional[int] = None):
        """Get recent validation results from the validation manager."""
        return self.validation_manager.get_recent_results(limit)

    async def cleanup(self):
        """Cleanup all managed resources asynchronously."""
        try:
            await self.manager_factory.close_all()
        except Exception as e:
            logger.warning(f"Error during engine cleanup: {e}")

    def __del__(self):
        """Cleanup is now handled automatically by individual components."""
        # No more complex async cleanup needed!
        # - Adapters clean themselves up via the resource manager
        # - ValidationManager handles its own cleanup
        # - Factories handle their own cleanup
        pass 