from typing import Dict, Type
from lamia.command_types import CommandType
from ..interfaces import Manager
from ..config_provider import ConfigProvider

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
        from ..llm.llm_manager import LLMManager
        
        self._manager_registry[CommandType.LLM] = LLMManager
        # TODO: Register other managers as they're implemented
        # self._manager_registry[CommandType.FILESYSTEM] = FSManager
        # self._manager_registry[CommandType.WEB] = WebManager
    
    async def get_manager(self, command_type: CommandType) -> Manager:
        """Get or create a manager for the specified command type.
        
        Args:
            command_type: The command type to get a manager for
            
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
        
        # Create new instance
        manager_class = self._manager_registry[command_type]
        manager = manager_class(self.config_provider, validation_strategy)
        self._manager_instances[command_type] = manager
        
        return manager
    
    async def close_all(self):
        """Close all created manager instances."""
        for manager in self._manager_instances.values():
            await manager.close()
        self._manager_instances.clear() 