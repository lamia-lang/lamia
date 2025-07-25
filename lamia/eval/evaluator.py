import traceback
from typing import List, Optional, Dict, Any, Callable, Union, Type, Protocol
from dataclasses import dataclass
import logging
from ..lamia import Lamia, LamiaResult
from ..types import BaseType
from .model_pricer import ModelPricer
from .model_cost import ModelCost
from ..engine.managers.llm.llm_manager import LLMManager
from ..command_types import CommandType
from lamia import LLMModel
from lamia._internal_types.model_retry import ModelWithRetries

logger = logging.getLogger(__name__)

@dataclass
class EvaluationResult:
    """Result of model evaluation process."""
    minimum_working_model: Optional[str]
    success: bool
    validation_pass_rate: float
    attempts: List[Dict[str, Any]]
    cost: Optional[ModelCost] = None
    error_message: Optional[str] = None

class EvaluationTask(Protocol):
    """Protocol for evaluation tasks (prompt or script)."""
    async def execute(self, model: str, lamia: Lamia) -> Any:
        """Execute the task using the given model and lamia instance."""

@dataclass
class PromptTask:
    """Task for evaluating a prompt."""
    prompt: str
    return_type: Optional[Type[BaseType]]
    
    async def execute(self, model: str, lamia: Lamia) -> Any:
        llm_model = LLMModel(model)
        model_with_retries = ModelWithRetries(llm_model, 1)
        return await lamia.run_async(self.prompt, self.return_type, models=[model_with_retries])

@dataclass
class ScriptTask:
    """Task for evaluating a script function."""
    script_func: Callable[[Lamia], Any]
    
    async def execute(self, model: str, lamia: Lamia) -> Any:
        # Update lamia to use the specific model for this evaluation
        llm_model = LLMModel(model)
        model_with_retries = ModelWithRetries(llm_model, 1)
        
        # Temporarily set the model for this script execution
        original_models = lamia._models
        lamia._models = [model_with_retries]
        try:
            return await self.script_func(lamia)
        finally:
            # Restore original models
            lamia._models = original_models

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
    ) -> EvaluationResult:
        """
        Evaluate a simple prompt across models to find the most cost-effective solution.
        
        Args:
            prompt: The prompt to evaluate
            return_type: Expected return type for validation
            max_model: Maximum (most expensive) model to try
            strategy: Search strategy ("binary_search" or "step_back")
        """
        task = PromptTask(prompt, return_type)
        return await self._evaluate_task(task, max_model, strategy)
    
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
        task = ScriptTask(script_func)
        return await self._evaluate_task(task, max_model, strategy)
    
    async def _evaluate_task(
        self,
        task: EvaluationTask,
        max_model: str,
        strategy: str = "binary_search"
    ) -> EvaluationResult:
        """Evaluate a task using the specified strategy."""
        models = await self.pricer.get_ordered_models(max_model)
        attempts = []
        
        if strategy == "binary_search":
            return await self._binary_search_strategy(task, models, attempts)
        else:
            return await self._step_back_strategy(task, models, attempts)
    
    async def _binary_search_strategy(
        self, 
        task: EvaluationTask,
        models: List[str], 
        attempts: List[Dict[str, Any]]
    ) -> EvaluationResult:
        """Binary search through models to find the cheapest working one."""
        best_model = None
        best_cost = None
        left, right = 0, len(models) - 1
        
        while left <= right:
            mid = (left + right) // 2
            model = models[mid]
            
            attempt = await self._evaluate_model(model, task)
            attempts.append(attempt)
            
            if attempt["success"]:
                best_model = model
                best_cost = attempt["cost"]
                right = mid - 1  # Try cheaper models
            else:
                left = mid + 1  # Try more expensive models
        
        return EvaluationResult(
            minimum_working_model=best_model,
            success=best_model is not None,
            validation_pass_rate=100.0 if best_model else 0.0,
            attempts=attempts,
            cost=best_cost if best_model else None,
            error_message=None if best_model else "No model succeeded"
        )

    async def _step_back_strategy(
        self, 
        task: EvaluationTask,
        models: List[str], 
        attempts: List[Dict[str, Any]]
    ) -> EvaluationResult:
        """Two-step-back, one-step-forward evaluation strategy."""
        current_idx = len(models) - 1
        
        while current_idx >= 0:
            model = models[current_idx]
            
            attempt = await self._evaluate_model(model, task)
            attempts.append(attempt)
            
            if attempt["success"]:
                return EvaluationResult(
                    minimum_working_model=model,
                    success=True,
                    validation_pass_rate=100.0,
                    cost=attempt["cost"],
                    attempts=attempts
                )
            
            current_idx = max(0, current_idx - 2)
        
        return EvaluationResult(
            minimum_working_model=None,
            success=False,
            validation_pass_rate=0.0,
            cost=None,
            attempts=attempts,
            error_message="No model succeeded"
        )
    
    async def _evaluate_model(self, model: str, task: EvaluationTask) -> Dict[str, Any]:
        """Atomic evaluation function for a single model and task."""
        try:
            result = await task.execute(model, self.lamia)
            
            logger.debug(f"Model {model} generated response: {getattr(result, 'result_text', str(result))}")
            
            cost = await self.pricer.calculate_cost(model, result)
            return {
                "model": model,
                "success": True,
                "cost": cost,
                "result": result
            }
            
        except Exception as e:
            traceback.print_exc()
            logger.debug(f"Model {model} failed with error: {e}")
            return {
                "model": model,
                "success": False,
                "error": str(e)
            }

