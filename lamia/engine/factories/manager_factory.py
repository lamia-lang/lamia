from typing import Dict, Type
from ..interfaces import Manager, DomainType
from ..config_manager import ConfigManager

class ManagerFactory:
    """Factory for creating domain managers based on request type."""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self._manager_registry: Dict[DomainType, Type[Manager]] = {}
        self._manager_instances: Dict[DomainType, Manager] = {}
        self._register_managers()
    
    def _register_managers(self):
        """Register available manager implementations."""
        # Import here to avoid circular imports
        from ..llm.llm_manager import LLMManager
        
        self._manager_registry[DomainType.LLM] = LLMManager
        # TODO: Register other managers as they're implemented
        # self._manager_registry[DomainType.FILESYSTEM] = FSManager
        # self._manager_registry[DomainType.WEB] = WebManager
    
    async def get_manager(self, domain_type: DomainType) -> Manager:
        """Get or create a manager for the specified domain type.
        
        Args:
            domain_type: The domain type to get a manager for
            
        Returns:
            Manager instance for the domain
            
        Raises:
            ValueError: If domain type is not supported
        """
        if domain_type not in self._manager_registry:
            raise ValueError(f"Unsupported domain type: {domain_type}")
        
        # Return existing instance if available (singleton pattern)
        if domain_type in self._manager_instances:
            return self._manager_instances[domain_type]
        
        # Create new instance
        manager_class = self._manager_registry[domain_type]
        manager = manager_class(self.config_manager)
        await manager.initialize()
        self._manager_instances[domain_type] = manager
        
        return manager
    
    async def close_all(self):
        """Close all created manager instances."""
        for manager in self._manager_instances.values():
            await manager.close()
        self._manager_instances.clear() 