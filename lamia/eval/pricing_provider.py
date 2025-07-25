from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
from .model_cost import ModelCost

class PricingProvider(ABC):
    """Abstract base class for pricing providers."""
    
    @classmethod
    @abstractmethod
    def name(cls) -> str:
        """Return the name of this pricing provider."""
        pass
    
    @abstractmethod
    async def get_model_pricing(self, model: str) -> Optional[Dict[str, float]]:
        """Get pricing information for a specific model."""
        pass
    
    @abstractmethod
    async def calculate_cost(self, model: str, usage: Dict[str, Any]) -> Optional[ModelCost]:
        """Calculate cost based on usage data. Returns None if pricing unavailable."""
        pass
    
    @abstractmethod
    async def update_pricing(self) -> bool:
        """Update pricing from provider API if available."""
        pass
    
    @abstractmethod
    async def get_ordered_models(self, max_model: str) -> List[str]:
        """Get models ordered by cost from expensive to cheap, up to max_model."""
        pass