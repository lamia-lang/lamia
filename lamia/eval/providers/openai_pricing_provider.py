from typing import Optional, Dict, Any, List
import json
import logging
from pathlib import Path
from ..pricing_provider import PricingProvider
from ..model_cost import ModelCost
from ...engine.managers.llm.llm_manager import LLMManager
from lamia import LLMModel

logger = logging.getLogger(__name__)

class OpenAIPricingProvider(PricingProvider):
    """Pricing provider for OpenAI models."""
    
    def __init__(self, config_path: Path, llm_manager: Optional[LLMManager] = None):
        self.config_path = config_path
        self.pricing_data = self._load_pricing_config()
        self.llm_manager = llm_manager
    
    @classmethod
    def name(cls) -> str:
        return "openai"
    
    def _load_pricing_config(self) -> Dict[str, Dict[str, float]]:
        """Load pricing configuration from unified config file."""
        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}")
            return {}
            
        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
                openai_models = data.get("openai", {}).get("models", [])
                
                # Convert list format to dict format for easier lookup
                pricing_dict = {}
                for model in openai_models:
                    pricing_dict[model["name"]] = {
                        "input_cost_per_1m": model["input_cost_per_1m"],
                        "output_cost_per_1m": model["output_cost_per_1m"]
                    }
                return pricing_dict
        except Exception as e:
            logger.error(f"Failed to load OpenAI pricing config: {e}")
            return {}
    
    async def get_model_pricing(self, model: str) -> Optional[Dict[str, float]]:
        """Get pricing information for a specific OpenAI model."""
        model_name = model.replace("openai:", "") if model.startswith("openai:") else model
        return self.pricing_data.get(model_name)
    
    async def calculate_cost(self, model: str, usage: Dict[str, Any]) -> ModelCost:
        """Calculate cost based on OpenAI usage data."""
        pricing = await self.get_model_pricing(model)
        if not pricing:
            logger.warning(f"No pricing data for OpenAI model {model}")
            return ModelCost(0, 0, 0.0)
        
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        
        input_cost = (input_tokens / 1_000_000) * pricing.get("input_cost_per_1m", 0.0)
        output_cost = (output_tokens / 1_000_000) * pricing.get("output_cost_per_1m", 0.0)
        total_cost = input_cost + output_cost
        
        return ModelCost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_cost_usd=total_cost
        )
    
    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Get available OpenAI models from API."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self._get_api_key()}"}
                async with session.get("https://api.openai.com/v1/models", headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("data", [])
                    else:
                        logger.error(f"Failed to fetch OpenAI models: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Error fetching OpenAI models: {e}")
            return []
    
    async def _get_adapter(self):
        """Get OpenAI adapter via LLM manager."""
        if not self.llm_manager:
            raise RuntimeError("LLM manager not provided to OpenAI pricing provider")
        
        # Create a dummy LLMModel for OpenAI to get the adapter
        model = LLMModel("openai:gpt-3.5-turbo")  # Any valid OpenAI model
        return await self.llm_manager.create_adapter_from_config(model)
    
    async def get_available_models(self) -> List[str]:
        """Get available OpenAI models from API via adapter."""
        try:
            adapter = await self._get_adapter()
            return await adapter.get_available_models()
        except Exception as e:
            logger.error(f"Error fetching OpenAI models: {e}")
            return []
    
    async def get_ordered_models(self, max_model: str) -> List[str]:
        """Get OpenAI models ordered by cost (expensive to cheap)."""
        # Try to get models from API first
        api_models = await self.get_available_models()
        
        # Get pricing info from config
        config_models = list(self.pricing_data.keys())
        
        # Use API models if available, otherwise fall back to config
        available_models = api_models if api_models else config_models
        
        if not available_models:
            logger.warning("No OpenAI models available from API or config")
            return [max_model]
        
        # Filter to chat completion models and get pricing
        chat_models = [m for m in available_models if "gpt" in m and "instruct" not in m]
        
        model_costs = []
        for model in chat_models:
            pricing = await self.get_model_pricing(model)
            if pricing:
                cost_per_1m = pricing.get("input_cost_per_1m", 0) + pricing.get("output_cost_per_1m", 0)
                model_costs.append((model, cost_per_1m))
        
        # Sort by cost (expensive first) and filter to max_model and below
        model_costs.sort(key=lambda x: x[1], reverse=True)
        max_model_name = max_model.replace("openai:", "")
        max_cost = next((cost for name, cost in model_costs if name == max_model_name), float('inf'))
        
        filtered_models = [(name, cost) for name, cost in model_costs if cost <= max_cost]
        return [f"openai:{name}" for name, _ in filtered_models]
    
    async def update_pricing(self) -> bool:
        """Update pricing from OpenAI API."""
        # OpenAI doesn't have a public pricing API, so we'd need to scrape or maintain manually
        logger.info("OpenAI pricing update requires manual configuration - using config file data")
        return True