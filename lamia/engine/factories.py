from typing import Dict, Type
from .interfaces import Manager, ValidationStrategy, DomainType
from .config_manager import ConfigManager

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
        from .llm.llm_manager import LLMManager
        
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

class ValidationStrategyFactory:
    """Factory for creating validation strategies based on domain type."""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self._strategy_registry: Dict[DomainType, Type[ValidationStrategy]] = {}
        self._strategy_instances: Dict[DomainType, ValidationStrategy] = {}
        self._register_strategies()
    
    def _register_strategies(self):
        """Register available validation strategy implementations."""
        # Import here to avoid circular imports
        from .llm.llm_validation_strategy import LLMValidationStrategy
        
        self._strategy_registry[DomainType.LLM] = LLMValidationStrategy
        # TODO: Register other strategies as they're implemented
        # self._strategy_registry[DomainType.FILESYSTEM] = FSValidationStrategy
        # self._strategy_registry[DomainType.WEB] = WebValidationStrategy
    
    async def get_strategy(self, domain_type: DomainType) -> ValidationStrategy:
        """Get or create a validation strategy for the specified domain type.
        
        Args:
            domain_type: The domain type to get a strategy for
            
        Returns:
            ValidationStrategy instance for the domain
            
        Raises:
            ValueError: If domain type is not supported
        """
        if domain_type not in self._strategy_registry:
            raise ValueError(f"Unsupported domain type for validation: {domain_type}")
        
        # Return existing instance if available (singleton pattern)
        if domain_type in self._strategy_instances:
            return self._strategy_instances[domain_type]
        
        # Create new instance
        strategy_class = self._strategy_registry[domain_type]
        strategy = strategy_class(self.config_manager)
        await strategy.initialize()
        self._strategy_instances[domain_type] = strategy
        
        return strategy
    
    async def close_all(self):
        """Close all created strategy instances."""
        for strategy in self._strategy_instances.values():
            await strategy.close()
        self._strategy_instances.clear() 