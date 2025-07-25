import traceback
from typing import List, Optional, Dict, Any, Callable, Union, Type
from dataclasses import dataclass
import asyncio
import logging
from ..lamia import Lamia, LamiaResult
from ..types import BaseType
from .model_pricer import ModelPricer
from .model_cost import ModelCost
from ..engine.managers.llm.llm_manager import LLMManager
from ..command_types import CommandType

logger = logging.getLogger(__name__)

@dataclass
class EvaluationResult:
    """Result of model evaluation process."""
    best_model: Optional[str]
    success: bool
    validation_pass_rate: float
    attempts: List[Dict[str, Any]]
    cost: Optional[ModelCost] = None
    total_cost: Optional[ModelCost] = None
    error_message: Optional[str] = None

class ModelEvaluator:
    """
    Main entry point for model evaluation and optimization.
    
    Finds the most cost-effective model that can successfully complete a task
    by testing models from most expensive to least expensive using various
    search strategies.
    """
    
    def __init__(self, lamia_instance: Optional[Lamia] = None):
        # If no lamia instance provided, create a default one
        self.lamia = lamia_instance or Lamia()
        self.pricer = ModelPricer(llm_manager=self.lamia._engine.manager_factory.get_manager(CommandType.LLM))
        self._own_lamia = lamia_instance is None  # Track if we created our own instance
    
    async def cleanup(self):
        """Clean up resources."""
        if self._own_lamia and self.lamia:
            await self.lamia._engine.cleanup()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()
    
    async def evaluate_prompt(
        self,
        prompt: str,
        return_type: Optional[Type[BaseType]],
        max_model: str,
        strategy: str = "binary_search",
        required_pass_rate_percent: float = 100.0
    ) -> EvaluationResult:
        """
        Evaluate a simple prompt across models to find the most cost-effective solution.
        
        Args:
            prompt: The prompt to evaluate
            return_type: Expected return type for validation
            max_model: Maximum (most expensive) model to try
            strategy: Search strategy ("binary_search" or "step_back")
            required_pass_rate_percent: Required validation pass rate as percentage (default 100.0)
        """
        models = await self.pricer.get_ordered_models(max_model)
        attempts = []
        
        if strategy == "binary_search":
            return await self._binary_search_evaluation(prompt, return_type, models, attempts)
        else:
            return await self._step_back_evaluation(prompt, return_type, models, attempts)
    
    async def evaluate_script(
        self,
        script_func: Callable[[Lamia], Any],
        max_model: str,
        strategy: str = "binary_search"
    ) -> EvaluationResult:
        """
        Evaluate a complex script with multiple lamia calls.
        
        Args:
            script_func: Function that takes a Lamia instance and executes the script
            max_model: Maximum model to try
            strategy: Search strategy
        """
        models = await self.pricer.get_ordered_models(max_model)
        attempts = []
        
        for model in models:
            lamia = None
            try:
                lamia = Lamia((model, 1))
                result = await script_func(lamia)
                
                # If no exception, consider it successful
                cost = await self.pricer.calculate_cost(model, result)
                attempts.append({
                    "model": model,
                    "success": True,
                    "cost": cost
                })
                
                return EvaluationResult(
                    best_model=model,
                    success=True,
                    cost=cost,
                    attempts=attempts,
                    total_cost=sum([a["cost"] for a in attempts], ModelCost(0, 0, 0))
                )
                
            except Exception as e:
                attempts.append({
                    "model": model,
                    "success": False,
                    "error": str(e)
                })
                continue
            finally:
                # Cleanup lamia instance
                if lamia:
                    try:
                        await lamia._engine.cleanup()
                    except Exception:
                        pass
        
        return EvaluationResult(
            best_model=None,
            success=False,
            cost=None,
            attempts=attempts,
            total_cost=sum([a.get("cost", ModelCost(0, 0, 0)) for a in attempts], ModelCost(0, 0, 0)),
            error_message="No model succeeded"
        )
    
    async def _binary_search_evaluation(
        self, 
        prompt: str, 
        return_type: Optional[Type[BaseType]], 
        models: List[str], 
        attempts: List[Dict[str, Any]]
    ) -> EvaluationResult:
        """Binary search through models to find the cheapest working one."""
        left, right = 0, len(models) - 1
        best_model = None
        best_cost = None
        
        while left <= right:
            mid = (left + right) // 2
            model = models[mid]
            
            try:
                # Use existing lamia instance with specific model
                from lamia import LLMModel
                from lamia._internal_types.model_retry import ModelWithRetries
                llm_model = LLMModel(model)
                model_with_retries = ModelWithRetries(llm_model, 1)
                result = await self.lamia.run_async(prompt, return_type, models=[model_with_retries])
                
                logger.debug(f"Model {model} generated response: {result.result_text}")
                
                cost = await self.pricer.calculate_cost(model, result)
                attempts.append({
                    "model": model,
                    "success": True,
                    "cost": cost
                })
                
                best_model = model
                best_cost = cost
                right = mid - 1  # Try cheaper models
                
            except Exception as e:
                traceback.print_exc()
                attempts.append({
                    "model": model,
                    "success": False,
                    "error": str(e)
                })
                logger.debug(f"Model {model} failed with error: {e}")
                left = mid + 1  # Try more expensive models
        
        # Calculate total cost (sum only non-None costs)
        valid_costs = [a["cost"] for a in attempts if a.get("cost") is not None]
        total_cost = None
        if valid_costs:
            total_cost = valid_costs[0]
            for cost in valid_costs[1:]:
                total_cost = total_cost + cost
        
        return EvaluationResult(
            best_model=best_model,
            success=best_model is not None,
            validation_pass_rate=100.0 if best_model else 0.0,
            attempts=attempts,
            cost=best_cost,
            total_cost=total_cost
        )
    
    async def _step_back_evaluation(
        self, 
        prompt: str, 
        return_type: Optional[Type[BaseType]], 
        models: List[str], 
        attempts: List[Dict[str, Any]]
    ) -> EvaluationResult:
        """Two-step-back, one-step-forward evaluation strategy."""
        current_idx = len(models) - 1  # Start with cheapest
        
        while current_idx >= 0:
            model = models[current_idx]
            lamia = None
            
            try:
                lamia = Lamia((model, 1))
                result = await lamia.run_async(prompt, return_type)
                
                logger.debug(f"Model {model} generated response: {result.result_text}")
                
                cost = await self.pricer.calculate_cost(model, result)
                attempts.append({
                    "model": model,
                    "success": True,
                    "cost": cost
                })
                
                return EvaluationResult(
                    best_model=model,
                    success=True,
                    cost=cost,
                    attempts=attempts,
                    total_cost=sum([a.get("cost", ModelCost(0, 0, 0)) for a in attempts], ModelCost(0, 0, 0))
                )
                
            except Exception as e:
                attempts.append({
                    "model": model,
                    "success": False,
                    "error": str(e)
                })
                # Step back two, forward one pattern
                current_idx = max(0, current_idx - 2)
            finally:
                # Cleanup lamia instance
                if lamia:
                    try:
                        await lamia._engine.cleanup()
                    except Exception:
                        pass
        
        return EvaluationResult(
            best_model=None,
            success=False,
            cost=None,
            attempts=attempts,
            total_cost=sum([a.get("cost", ModelCost(0, 0, 0)) for a in attempts], ModelCost(0, 0, 0)),
            error_message="No model succeeded"
        )