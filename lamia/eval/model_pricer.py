from typing import Dict, Optional, Type, List
import logging
from pathlib import Path
from .pricing_provider import PricingProvider
from .model_cost import ModelCost
from lamia import LamiaResult
from ..engine.managers.llm.llm_manager import LLMManager

# Import all pricing providers here
from .providers.openai_pricing_provider import OpenAIPricingProvider
from .providers.anthropic_pricing_provider import AnthropicPricingProvider  
from .providers.ollama_pricing_provider import OllamaPricingProvider

logger = logging.getLogger(__name__)

class ModelPricer:
    """Main pricing coordinator that uses imported provider implementations."""
    
    def __init__(self, config_path: Optional[Path] = None, llm_manager: Optional[LLMManager] = None):
        self.config_path = config_path or Path(__file__).parent / "config" / "models_and_pricing.json"
        self.llm_manager = llm_manager
        self._provider_classes = self._build_provider_registry()
        self._provider_instances: Dict[str, PricingProvider] = {}
    
    def _build_provider_registry(self) -> Dict[str, Type[PricingProvider]]:
        """Build registry from imported provider classes using their name() method."""
        registry = {}
        
        # Get all imported provider classes
        provider_classes = [
            OpenAIPricingProvider,
            AnthropicPricingProvider,
            OllamaPricingProvider
        ]
        
        for provider_class in provider_classes:
            name = provider_class.name()
            registry[name] = provider_class
            logger.debug(f"Registered pricing provider: {name}")
        
        return registry
    
    def _get_provider(self, provider_name: str) -> Optional[PricingProvider]:
        """Get provider instance, loading it lazily if needed."""
        if provider_name in self._provider_instances:
            return self._provider_instances[provider_name]
        
        if provider_name not in self._provider_classes:
            return None
        
        try:
            provider_class = self._provider_classes[provider_name]
            provider_instance = provider_class(self.config_path, self.llm_manager)
            self._provider_instances[provider_name] = provider_instance
            return provider_instance
        except Exception as e:
            logger.error(f"Failed to instantiate pricing provider {provider_name}: {e}")
            return None
    
    async def calculate_cost(self, model: str, result: LamiaResult) -> Optional[ModelCost]:
        """Calculate cost by delegating to appropriate provider."""
        provider_name = model.split(":")[0] if ":" in model else model
        provider = self._get_provider(provider_name)
        
        if provider is None:
            logger.debug(f"No pricing provider for {provider_name}")
            return None
        
        usage = result.tracking_context.metadata.get("usage", {})
        if not usage:
            logger.debug(f"No usage data available for cost calculation")
            return None
        
        return await provider.calculate_cost(model, usage)
    
    async def update_pricing(self, provider_name: str) -> bool:
        """Update pricing for a specific provider."""
        provider = self._get_provider(provider_name)
        if provider is None:
            logger.warning(f"No pricing provider found for {provider_name}")
            return False
        
        try:
            return await provider.update_pricing()
        except Exception as e:
            logger.error(f"Failed to update pricing for {provider_name}: {e}")
            return False
    
    async def get_ordered_models(self, max_model: str) -> List[str]:
        """Get models ordered by cost, delegating to appropriate provider."""
        provider_name = max_model.split(":")[0] if ":" in max_model else max_model
        provider = self._get_provider(provider_name)
        
        if provider is None:
            logger.warning(f"No provider found for {provider_name}")
            return [max_model]
        
        return await provider.get_ordered_models(max_model)
    
    def get_available_providers(self) -> List[str]:
        """Get list of available pricing providers."""
        return list(self._provider_classes.keys())