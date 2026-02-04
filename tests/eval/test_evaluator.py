"""Tests for evaluation module."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from lamia.eval.evaluator import ModelEvaluator, EvaluationResult, PromptTask, ScriptTask
from lamia.eval.model_cost import ModelCost


class TestModelCost:
    """Test ModelCost class."""
    
    def test_initialization(self):
        """Test ModelCost initialization."""
        cost = ModelCost(
            input_tokens=100,
            output_tokens=50
        )
        
        assert cost.input_tokens == 100
        assert cost.output_tokens == 50
        assert cost.total_cost_usd == 0.0
    
    def test_initialization_with_cost(self):
        """Test ModelCost initialization with monetary cost."""
        cost = ModelCost(
            input_tokens=100,
            output_tokens=50,
            total_cost_usd=0.003
        )
        
        assert cost.input_tokens == 100
        assert cost.output_tokens == 50
        assert cost.total_cost_usd == 0.003
    
    def test_total_tokens(self):
        """Test total_tokens property."""
        cost = ModelCost(input_tokens=100, output_tokens=50)
        assert cost.total_tokens == 150
    
    def test_zero_factory(self):
        """Test ModelCost.zero() factory."""
        cost = ModelCost.zero()
        
        assert cost.input_tokens == 0
        assert cost.output_tokens == 0
        assert cost.total_cost_usd == 0.0
    
    def test_addition(self):
        """Test adding two ModelCost objects."""
        cost1 = ModelCost(input_tokens=100, output_tokens=50, total_cost_usd=0.01)
        cost2 = ModelCost(input_tokens=200, output_tokens=100, total_cost_usd=0.02)
        
        total = cost1 + cost2
        
        assert total.input_tokens == 300
        assert total.output_tokens == 150
        assert total.total_cost_usd == 0.03
    
    def test_addition_with_none(self):
        """Test adding ModelCost with None."""
        cost = ModelCost(input_tokens=100, output_tokens=50, total_cost_usd=0.01)
        
        result = cost + None
        
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.total_cost_usd == 0.01
    
    def test_str_with_cost(self):
        """Test string representation with cost."""
        cost = ModelCost(input_tokens=100, output_tokens=50, total_cost_usd=0.003)
        result = str(cost)
        assert "$0.003" in result
        assert "100 input" in result
        assert "50 output" in result
    
    def test_str_without_cost(self):
        """Test string representation without cost."""
        cost = ModelCost(input_tokens=100, output_tokens=50)
        result = str(cost)
        assert "$" not in result
        assert "100 input" in result
        assert "50 output" in result


class TestEvaluationResult:
    """Test EvaluationResult dataclass."""
    
    def test_success_result(self):
        """Test successful evaluation result."""
        result = EvaluationResult(
            minimum_working_model="openai:gpt-3.5-turbo",
            success=True,
            validation_pass_rate=100.0,
            attempts=[{"model": "openai:gpt-3.5-turbo", "success": True}]
        )
        
        assert result.success
        assert result.minimum_working_model == "openai:gpt-3.5-turbo"
        assert result.validation_pass_rate == 100.0
    
    def test_failure_result(self):
        """Test failed evaluation result."""
        result = EvaluationResult(
            minimum_working_model=None,
            success=False,
            validation_pass_rate=0.0,
            attempts=[],
            error_message="No model succeeded"
        )
        
        assert not result.success
        assert result.minimum_working_model is None
        assert result.error_message == "No model succeeded"


class TestModelEvaluator:
    """Test ModelEvaluator class."""
    
    def test_initialization_with_lamia(self):
        """Test evaluator initialization with provided lamia instance."""
        mock_lamia = Mock()
        mock_lamia._engine = Mock()
        
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)
        
        assert evaluator.lamia == mock_lamia
        assert not evaluator._own_lamia
    
    @pytest.mark.asyncio
    async def test_evaluate_prompt_empty_models(self):
        """Test that empty models list raises error."""
        mock_lamia = Mock()
        mock_lamia._engine = Mock()
        
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)
        
        with pytest.raises(ValueError, match="Models list cannot be empty"):
            await evaluator.evaluate_prompt(
                prompt="test prompt",
                return_type=None,
                models=[]
            )
    
    @pytest.mark.asyncio
    async def test_evaluate_script_empty_models(self):
        """Test that empty models list raises error for script."""
        mock_lamia = Mock()
        mock_lamia._engine = Mock()
        
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)
        
        async def dummy_script(lamia):
            return "result"
        
        with pytest.raises(ValueError, match="Models list cannot be empty"):
            await evaluator.evaluate_script(
                script_func=dummy_script,
                models=[]
            )


class TestPromptTask:
    """Test PromptTask class."""
    
    @pytest.mark.asyncio
    async def test_execute(self):
        """Test prompt task execution."""
        mock_lamia = Mock()
        mock_lamia.run_async = AsyncMock(return_value="test result")
        
        task = PromptTask(prompt="test prompt", return_type=None)
        result = await task.execute("openai:gpt-4", mock_lamia)
        
        assert result == "test result"
        mock_lamia.run_async.assert_called_once()


class TestScriptTask:
    """Test ScriptTask class."""
    
    @pytest.mark.asyncio
    async def test_execute(self):
        """Test script task execution."""
        mock_lamia = Mock()
        mock_lamia._models = []
        
        async def test_script(lamia):
            return "script result"
        
        task = ScriptTask(script_func=test_script)
        result = await task.execute("openai:gpt-4", mock_lamia)
        
        assert result == "script result"
        # Verify models were restored
        assert mock_lamia._models == []
