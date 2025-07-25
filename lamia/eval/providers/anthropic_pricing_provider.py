from typing import Optional, Dict, Any, List
import json
import logging
import aiohttp
from pathlib import Path
from ..pricing_provider import PricingProvider
from ..model_cost import ModelCost
from ...engine.managers.llm.llm_manager import LLMManager

logger = logging.getLogger(__name__)

class AnthropicPricingProvider(PricingProvider):
    """Pricing provider for Anthropic models."""
    
    def __init__(self, config_path: Path, llm_manager: Optional[LLMManager] = None):
        self.config_path = config_path
        self.pricing_data = self._load_pricing_config()
        self.llm_manager = llm_manager
    
    @classmethod
    def name(cls) -> str:
        return "anthropic"
    
    def _load_pricing_config(self) -> Dict[str, Dict[str, float]]:
        """Load pricing configuration from unified config file."""
        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}")
            return {}
            
        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
                anthropic_models = data.get("anthropic", {}).get("models", [])
                
                # Convert list format to dict format for easier lookup
                pricing_dict = {}
                for model in anthropic_models:
                    pricing_dict[model["name"]] = {
                        "input_cost_per_1m": model["input_cost_per_1m"],
                        "output_cost_per_1m": model["output_cost_per_1m"]
                    }
                return pricing_dict
        except Exception as e:
            logger.error(f"Failed to load Anthropic pricing config: {e}")
            return {}
    
    async def get_model_pricing(self, model: str) -> Optional[Dict[str, float]]:
        """Get pricing information for a specific Anthropic model."""
        model_name = model.replace("anthropic:", "") if model.startswith("anthropic:") else model
        return self.pricing_data.get(model_name)
    
    async def calculate_cost(self, model: str, usage: Dict[str, Any]) -> ModelCost:
        """Calculate cost based on Anthropic usage data."""
        pricing = await self.get_model_pricing(model)
        if not pricing:
            logger.warning(f"No pricing data for Anthropic model {model}")
            return ModelCost(0, 0, 0.0)
        
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        
        input_cost = (input_tokens / 1_000_000) * pricing.get("input_cost_per_1m", 0.0)
        output_cost = (output_tokens / 1_000_000) * pricing.get("output_cost_per_1m", 0.0)
        total_cost = input_cost + output_cost
        
        return ModelCost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_cost_usd=total_cost
        )
    
    async def get_ordered_models(self, max_model: str) -> List[str]:
        """Get Anthropic models ordered by cost (expensive to cheap)."""
        # Use config data (Anthropic doesn't have public models API)
        if not self.pricing_data:
            logger.warning("No Anthropic models available in config")
            return [max_model]
        
        # Extract model costs and sort
        model_costs = []
        for model_name, pricing in self.pricing_data.items():
            if pricing:
                total_cost = pricing.get("input_cost_per_1m", 0) + pricing.get("output_cost_per_1m", 0)
                model_costs.append((f"anthropic:{model_name}", total_cost))
        
        # Sort by cost (expensive first) and filter to max_model and below
        model_costs.sort(key=lambda x: x[1], reverse=True)
        max_model_name = max_model.replace("anthropic:", "")
        max_cost = next((cost for name, cost in model_costs if name.endswith(max_model_name)), float('inf'))
        
        filtered_models = [name for name, cost in model_costs if cost <= max_cost]
        return filtered_models
    
    def _get_api_key(self) -> str:
        """Get Anthropic API key from environment."""
        import os
        return os.getenv("ANTHROPIC_API_KEY", "")
    
    async def update_pricing(self) -> bool:
        """Update pricing from Anthropic API."""
        logger.info("Anthropic pricing update requires manual configuration - using config file data")
        return True