from typing import Dict, Type
from lamia.interpreter.command_types import CommandType
from ..managers import Manager
from ..config_provider import ConfigProvider
from ..managers.llm.llm_manager import LLMManager
from ..managers.fs_manager import FSManager
from ..managers.web_manager import WebManager

class ManagerFactory:
    """Factory for creating domain managers based on request type."""
    
    def __init__(self, config_provider: ConfigProvider):
        self.config_provider = config_provider
        self._manager_registry: Dict[CommandType, Type[Manager]] = {}
        self._manager_instances: Dict[CommandType, Manager] = {}
        self._register_managers()
    
    def _register_managers(self):
        """Register available manager implementations."""
        # Import here to avoid circular imports
        
        self._manager_registry[CommandType.LLM] = LLMManager
        self._manager_registry[CommandType.FILESYSTEM] = FSManager
        self._manager_registry[CommandType.WEB] = WebManager
    
    def get_manager(self, command_type: CommandType) -> Manager:
        """Get or create a manager for the specified command type.
        
        Args:
            command_type: The command type to get a manager for
            validation_strategy: The validation strategy to use for this manager
            
        Returns:
            Manager instance for the command
            
        Raises:
            ValueError: If command type is not supported
        """
        if command_type not in self._manager_registry:
            raise ValueError(f"Unsupported command type: {command_type}")
        
        # Return existing instance if available (singleton pattern)
        if command_type in self._manager_instances:
            return self._manager_instances[command_type]
        
        # Create new instance with provided validation strategy
        manager_class = self._manager_registry[command_type]
        manager = manager_class(self.config_provider)
        self._manager_instances[command_type] = manager
        
        return manager
    
    async def close_all(self):
        """Close all created manager instances."""
        for manager in self._manager_instances.values():
            await manager.close()
        self._manager_instances.clear()