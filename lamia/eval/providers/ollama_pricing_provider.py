from typing import Optional, Dict, Any, List
import json
import logging
import aiohttp
from pathlib import Path
from ..pricing_provider import PricingProvider
from ..model_cost import ModelCost
from ...engine.managers.llm.llm_manager import LLMManager

logger = logging.getLogger(__name__)

class OllamaPricingProvider(PricingProvider):
    """Pricing provider for Ollama models."""
    
    def __init__(self, config_path: Path, llm_manager: Optional[LLMManager] = None):
        self.config_path = config_path
        self.pricing_data = self._load_pricing_config()
        self.llm_manager = llm_manager
    
    @classmethod
    def name(cls) -> str:
        return "ollama"
    
    def _load_pricing_config(self) -> Dict[str, Dict[str, float]]:
        """Load pricing configuration from unified config file."""
        # Ollama models are free, so we don't need pricing config
        # But we keep this method for interface consistency
        return {}
    
    async def get_model_pricing(self, model: str) -> Optional[Dict[str, float]]:
        """Get pricing information for a specific Ollama model."""
        # Ollama models are free
        return {"input_cost_per_1m": 0.0, "output_cost_per_1m": 0.0}
    
    async def calculate_cost(self, model: str, usage: Dict[str, Any]) -> Optional[ModelCost]:
        """Calculate cost for Ollama models (free)."""
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        
        return ModelCost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_cost_usd=0.0
        )
    
    async def _get_adapter(self):
        """Get raw Ollama adapter without retry wrapping."""
        if not self.llm_manager:
            raise RuntimeError("LLM manager not provided to Ollama pricing provider")
        
        from lamia import LLMModel
        model = LLMModel("ollama:llama3.2:1b")  # Any valid Ollama model
        # Always create a fresh adapter for pricing provider to avoid session conflicts
        return await self.llm_manager.create_adapter_from_config(model, with_retries=False)
    
    async def get_available_models(self) -> List[str]:
        """Get available models from local Ollama installation via adapter."""
        adapter = None
        try:
            adapter = await self._get_adapter()
            # The adapter will auto-start Ollama if not running
            models = await adapter.get_available_models()
            logger.info(f"Raw Ollama models from adapter: {models}")
            return models
        except Exception as e:
            logger.error(f"Error fetching Ollama models via adapter: {e}")
            return []
        finally:
            # Close the fresh adapter to prevent unclosed session warnings
            if adapter:
                try:
                    await adapter.close()
                except Exception as e:
                    logger.debug(f"Error closing adapter: {e}")
    
    def _extract_family_name(self, model_name: str) -> str:
        """Extract model family name (e.g., 'llama3.2:1b' -> 'llama3.2')."""
        if ':' in model_name:
            return model_name.split(':')[0]
        return model_name
    
    def _extract_param_count_from_details(self, model_details: Dict[str, Any]) -> int:
        """Extract parameter count from model details."""
        # Try to get size from model details
        size = model_details.get("size", 0)
        if size > 0:
            # Convert bytes to approximate parameter count (rough estimation)
            # Typical model: ~4 bytes per parameter for fp32, ~2 for fp16
            return max(1, int(size / (2 * 1024 * 1024 * 1024)))  # Assume fp16, convert to billions
        
        # Fallback to name parsing
        model_name = model_details.get("name", "")
        return self._extract_param_count_from_name(model_name)
    
    def _extract_param_count_from_name(self, model_name: str) -> int:
        """Extract parameter count from model name for sorting."""
        name_lower = model_name.lower()
        
        # Extract parameter count from model name (e.g., "llama3.1:70b" -> 70)
        if ':' in name_lower:
            size_part = name_lower.split(':')[-1]
            if 'b' in size_part and size_part != 'latest':
                try:
                    param_str = size_part.replace('b', '')
                    return int(float(param_str))
                except ValueError:
                    pass
        
        return 1  # Default for unknown models
    
    async def get_ordered_models(self, max_model: str) -> List[str]:
        """Get Ollama models ordered by parameter count (largest to smallest)."""
        adapter = None
        try:
            adapter = await self._get_adapter()
            model_details = await adapter.get_model_details()
            
            if not model_details:
                logger.warning("No Ollama models found")
                return [max_model]
            
            # Extract family name from max_model (e.g., "ollama:llama3.2" -> "llama3.2")
            max_model_clean = max_model.replace("ollama:", "")
            target_family = self._extract_family_name(max_model_clean)
            logger.info(f"Looking for models in family: {target_family}")
            
            # Filter to models in the same family
            family_models = []
            for model_detail in model_details:
                model_name = model_detail["name"]
                model_family = self._extract_family_name(model_name)
                
                if model_family == target_family:
                    param_count = self._extract_param_count_from_details(model_detail)
                    family_models.append((f"ollama:{model_name}", param_count, model_detail))
                    logger.info(f"Found family model: {model_name} -> {param_count}B params, size: {model_detail.get('size', 0)} bytes")
            
            if not family_models:
                logger.warning(f"No models found in family {target_family}")
                return [max_model]
            
            # Sort by parameter count (largest first)
            family_models.sort(key=lambda x: x[1], reverse=True)
            ordered_models = [name for name, _, _ in family_models]
            
            logger.info(f"Ordered models in {target_family} family: {[(name, count) for name, count, _ in family_models]}")
            return ordered_models
            
        except Exception as e:
            logger.error(f"Error getting ordered models: {e}")
            return [max_model]
        finally:
            # Close the fresh adapter to prevent unclosed session warnings
            if adapter:
                try:
                    await adapter.close()
                except Exception as e:
                    logger.debug(f"Error closing adapter: {e}")
    
    async def update_pricing(self) -> bool:
        """Update pricing from local Ollama installation."""
        logger.info("Ollama pricing update not implemented - using config file data")
        return True