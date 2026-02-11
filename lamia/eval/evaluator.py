import traceback
from typing import List, Optional, Dict, Any, Callable, Union, Type, Protocol
from dataclasses import dataclass
import logging
from lamia import Lamia
from ..types import BaseType
from .model_cost import ModelCost
from lamia import LLMModel
from lamia._internal_types.model_retry import ModelWithRetries

logger = logging.getLogger(__name__)


@dataclass
class ModelAttemptResult:
    """Typed result of a model evaluation attempt."""
    model: str
    success: bool
    cost: Optional[ModelCost] = None
    result: Any = None
    error: Optional[str] = None


@dataclass
class EvaluationResult:
    """Result of model evaluation process."""
    minimum_working_model: Optional[str]
    success: bool
    validation_pass_rate: float
    attempts: List[ModelAttemptResult]
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
    
    Models should be provided as a list ordered from most expensive/capable
    to least expensive/capable.
    """
    
    def __init__(self, lamia_instance: Optional[Lamia] = None):
        # If no lamia instance provided, create a default one
        self.lamia = lamia_instance or Lamia()
        self._own_lamia = lamia_instance is None  # Track if we created our own instance
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        if self._own_lamia and self.lamia:
            await self.lamia._engine.cleanup()
    
    async def __aenter__(self) -> "ModelEvaluator":
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.cleanup()
    
    async def evaluate_prompt(
        self,
        prompt: str,
        return_type: Optional[Type[BaseType]],
        models: List[str],
        strategy: str = "binary_search",
    ) -> EvaluationResult:
        """
        Evaluate a simple prompt across models to find the most cost-effective solution.
        
        Args:
            prompt: The prompt to evaluate
            return_type: Expected return type for validation
            models: List of model names ordered from most to least expensive/capable
                   (e.g., ["openai:gpt-4", "openai:gpt-3.5-turbo"])
            strategy: Search strategy ("binary_search" or "step_back")
        """
        if not models:
            raise ValueError("Models list cannot be empty")
        
        task = PromptTask(prompt, return_type)
        return await self._evaluate_task(task, models, strategy)
    
    async def evaluate_script(
        self,
        script_func: Callable[[Lamia], Any],
        models: List[str],
        strategy: str = "binary_search"
    ) -> EvaluationResult:
        """
        Evaluate a complex script with multiple lamia calls.
        
        Args:
            script_func: Function that takes a Lamia instance and executes the script
            models: List of model names ordered from most to least expensive/capable
            strategy: Search strategy
        """
        if not models:
            raise ValueError("Models list cannot be empty")
        
        task = ScriptTask(script_func)
        return await self._evaluate_task(task, models, strategy)
    
    async def _evaluate_task(
        self,
        task: EvaluationTask,
        models: List[str],
        strategy: str = "binary_search"
    ) -> EvaluationResult:
        """Evaluate a task using the specified strategy."""
        attempts: List[ModelAttemptResult] = []

        logger.info(f"Evaluating models: {models}")
        
        if strategy == "binary_search":
            return await self._binary_search_strategy(task, models, attempts)
        else:
            return await self._step_back_strategy(task, models, attempts)
    
    async def _binary_search_strategy(
        self, 
        task: EvaluationTask,
        models: List[str], 
        attempts: List[ModelAttemptResult]
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
            
            if attempt.success:
                best_model = model
                best_cost = attempt.cost
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
        attempts: List[ModelAttemptResult]
    ) -> EvaluationResult:
        """Two-step-back, one-step-forward evaluation strategy."""
        current_idx = len(models) - 1
        
        while current_idx >= 0:
            model = models[current_idx]
            
            attempt = await self._evaluate_model(model, task)
            attempts.append(attempt)
            
            if attempt.success:
                return EvaluationResult(
                    minimum_working_model=model,
                    success=True,
                    validation_pass_rate=100.0,
                    cost=attempt.cost,
                    attempts=attempts
                )
            
            if current_idx == 0:
                break  # Most-capable model failed, nothing left to try
            current_idx = max(0, current_idx - 2)
        
        return EvaluationResult(
            minimum_working_model=None,
            success=False,
            validation_pass_rate=0.0,
            cost=None,
            attempts=attempts,
            error_message="No model succeeded"
        )
    
    async def _evaluate_model(self, model: str, task: EvaluationTask) -> ModelAttemptResult:
        """Atomic evaluation function for a single model and task.
        
        Returns success only if:
        1. The task executes without exceptions
        2. The result passes validation (lamia.run_async raises on validation failure)
        3. The result is not None
        
        Any validation failure in lamia.run_async will raise an exception,
        which is caught and returned as success=False.
        """
        try:
            result = await task.execute(model, self.lamia)
            
            # Check if result is None - this indicates the model didn't produce valid output
            if result is None:
                logger.debug(f"Model {model} returned None result")
                return ModelAttemptResult(
                    model=model,
                    success=False,
                    error="Model returned None result"
                )
            
            logger.debug(f"Model {model} generated response: {getattr(result, 'result_text', str(result))}")
            
            # TODO: Implement cost calculation when pricing is added
            # For now, extract token usage if available and create a basic ModelCost
            cost = self._extract_cost(result)
            
            return ModelAttemptResult(
                model=model,
                success=True,
                cost=cost,
                result=result
            )
            
        except Exception as e:
            traceback.print_exc()
            logger.debug(f"Model {model} failed with error: {e}")
            return ModelAttemptResult(
                model=model,
                success=False,
                error=str(e)
            )
    
    def _extract_cost(self, result: Any) -> Optional[ModelCost]:
        """Extract cost information from result if available.
        
        TODO: Implement actual cost calculation when pricing is added.
        For now, just extracts token counts without monetary cost.
        """
        try:
            # Try to get usage from tracking context
            if hasattr(result, 'tracking_context'):
                metadata = result.tracking_context.metadata
                if metadata and isinstance(metadata, dict):
                    usage = metadata.get("usage", {})
                    if usage and isinstance(usage, dict):
                        input_tokens = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
                        output_tokens = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
                        return ModelCost(
                            input_tokens=input_tokens,
                            output_tokens=output_tokens
                        )
        except Exception as e:
            logger.debug(f"Could not extract cost: {e}")
        
        return None
