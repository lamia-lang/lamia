"""Tests for evaluation module."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from lamia.eval.evaluator import ModelAttemptResult, ModelEvaluator, EvaluationResult, PromptTask, ScriptTask
from lamia.eval.model_cost import ModelCost
from lamia.facade.result_types import LamiaResult
from lamia.validation.base import TrackingContext
from lamia.interpreter.command_types import CommandType


def _lamia_result(
    result_text: str = "ok",
    usage: dict | None = None,
) -> LamiaResult:
    metadata = {"usage": usage} if usage is not None else None
    return LamiaResult(
        result_text=result_text,
        typed_result=result_text,
        tracking_context=TrackingContext(
            data_provider_name="test:model",
            command_type=CommandType.LLM,
            metadata=metadata,
        ),
    )


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

    def test_addition_with_non_model_cost_returns_not_implemented(self):
        """Test adding ModelCost with unsupported type returns NotImplemented."""
        cost = ModelCost(input_tokens=100, output_tokens=50)
        assert cost.__add__(42) is NotImplemented
        with pytest.raises(TypeError):
            cost + 42  # type: ignore[operator]

    def test_str_zero_tokens(self):
        """Test string representation with zero tokens."""
        cost = ModelCost(input_tokens=0, output_tokens=0)
        assert str(cost) == "0 input + 0 output tokens"

    def test_str_with_small_cost(self):
        """Test string formatting for very small monetary cost."""
        cost = ModelCost(input_tokens=1, output_tokens=1, total_cost_usd=0.000001)
        result = str(cost)
        assert "$0.000001" in result

    def test_total_tokens_large_values(self):
        """Test total_tokens with large token counts."""
        cost = ModelCost(input_tokens=1_000_000, output_tokens=2_000_000)
        assert cost.total_tokens == 3_000_000


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


class TestStepBackStrategy:
    """Test step_back strategy terminates correctly."""

    @pytest.mark.asyncio
    async def test_step_back_terminates_when_all_models_fail(self):
        """step_back must NOT loop infinitely when cheapest model fails."""
        mock_lamia = Mock()
        mock_lamia._engine = Mock()
        mock_lamia.run_async = AsyncMock(side_effect=RuntimeError("model error"))
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)

        models = ["provider:top", "provider:mid", "provider:cheap"]
        result = await evaluator.evaluate_prompt(
            prompt="test", return_type=None, models=models, strategy="step_back",
        )

        assert not result.success
        assert result.error_message == "No model succeeded"
        # step_back is a linear scan cheapest -> most expensive; every model is tried
        assert len(result.attempts) == len(models)

    @pytest.mark.asyncio
    async def test_step_back_single_model_terminates(self):
        """step_back with one model should try once and stop."""
        mock_lamia = Mock()
        mock_lamia._engine = Mock()
        mock_lamia.run_async = AsyncMock(side_effect=RuntimeError("fail"))
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)

        result = await evaluator.evaluate_prompt(
            prompt="test", return_type=None, models=["p:m"], strategy="step_back",
        )

        assert not result.success
        assert len(result.attempts) == 1


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
        call_kwargs = mock_lamia.run_async.call_args
        assert call_kwargs.kwargs.get("_full_result") is True


class TestScriptTask:
    """Test ScriptTask class."""

    @pytest.mark.asyncio
    async def test_execute(self):
        """Test script task execution."""
        mock_config_provider = Mock()
        mock_lamia = Mock()
        mock_lamia._models = []
        mock_lamia._engine = Mock()
        mock_lamia._engine.config_provider = mock_config_provider

        async def test_script(lamia):
            return "script result"

        task = ScriptTask(script_func=test_script)
        result = await task.execute("openai:gpt-4", mock_lamia)

        assert result == "script result"
        mock_config_provider.override_model_chain_with.assert_called_once()
        mock_config_provider.reset_model_chain.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_restores_models_on_exception(self):
        """Test that model chain is restored when the script function raises."""
        mock_config_provider = Mock()
        mock_lamia = Mock()
        mock_lamia._engine = Mock()
        mock_lamia._engine.config_provider = mock_config_provider

        async def failing_script(lamia):
            raise RuntimeError("script failed")

        task = ScriptTask(script_func=failing_script)

        with pytest.raises(RuntimeError, match="script failed"):
            await task.execute("openai:gpt-4", mock_lamia)

        mock_config_provider.reset_model_chain.assert_called_once()


class TestEvaluateModel:
    """Test ModelEvaluator._evaluate_model."""

    @pytest.mark.asyncio
    async def test_success_returns_attempt_with_cost(self):
        """Successful task execution returns success=True with extracted cost."""
        mock_lamia = Mock()
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)
        usage = {"prompt_tokens": 10, "completion_tokens": 5}
        result = _lamia_result(usage=usage)

        mock_task = Mock()
        mock_task.execute = AsyncMock(return_value=result)

        attempt = await evaluator._evaluate_model("test:model", mock_task)

        assert attempt.success
        assert attempt.model == "test:model"
        assert attempt.result is result
        assert attempt.error is None
        assert attempt.cost == ModelCost(input_tokens=10, output_tokens=5)

    @pytest.mark.asyncio
    async def test_exception_returns_failure(self):
        """Exceptions during task execution return success=False."""
        mock_lamia = Mock()
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)

        mock_task = Mock()
        mock_task.execute = AsyncMock(side_effect=ValueError("validation failed"))

        attempt = await evaluator._evaluate_model("test:model", mock_task)

        assert not attempt.success
        assert attempt.model == "test:model"
        assert attempt.error == "validation failed"
        assert attempt.cost is None
        assert attempt.result is None

    @pytest.mark.asyncio
    async def test_none_result_returns_failure(self):
        """None result from task returns success=False."""
        mock_lamia = Mock()
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)

        mock_task = Mock()
        mock_task.execute = AsyncMock(return_value=None)

        attempt = await evaluator._evaluate_model("test:model", mock_task)

        assert not attempt.success
        assert attempt.error == "Model returned None result"


class TestExtractCost:
    """Test ModelEvaluator._extract_cost."""

    def test_extracts_from_lamia_result_with_prompt_tokens(self):
        evaluator = ModelEvaluator(lamia_instance=Mock())
        result = _lamia_result(usage={"prompt_tokens": 100, "completion_tokens": 50})

        cost = evaluator._extract_cost(result)

        assert cost == ModelCost(input_tokens=100, output_tokens=50)

    def test_extracts_input_output_token_aliases(self):
        evaluator = ModelEvaluator(lamia_instance=Mock())
        result = _lamia_result(usage={"input_tokens": 20, "output_tokens": 30})

        cost = evaluator._extract_cost(result)

        assert cost == ModelCost(input_tokens=20, output_tokens=30)

    def test_returns_none_for_non_lamia_result(self):
        evaluator = ModelEvaluator(lamia_instance=Mock())

        assert evaluator._extract_cost("plain string") is None
        assert evaluator._extract_cost({"usage": {"prompt_tokens": 1}}) is None

    def test_returns_none_when_metadata_missing(self):
        evaluator = ModelEvaluator(lamia_instance=Mock())
        result = LamiaResult(
            result_text="ok",
            typed_result="ok",
            tracking_context=TrackingContext(
                data_provider_name="test",
                command_type=CommandType.LLM,
                metadata=None,
            ),
        )

        assert evaluator._extract_cost(result) is None

    def test_returns_none_when_usage_missing(self):
        evaluator = ModelEvaluator(lamia_instance=Mock())
        result = LamiaResult(
            result_text="ok",
            typed_result="ok",
            tracking_context=TrackingContext(
                data_provider_name="test",
                command_type=CommandType.LLM,
                metadata={"other": "data"},
            ),
        )

        assert evaluator._extract_cost(result) is None


class TestBinarySearchStrategy:
    """Test ModelEvaluator._binary_search_strategy."""

    @pytest.mark.asyncio
    async def test_all_models_succeed_finds_cheapest(self):
        mock_lamia = Mock()
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)
        models = ["expensive", "mid", "cheap"]

        async def mock_evaluate(model: str, task):
            return ModelAttemptResult(model=model, success=True, cost=ModelCost(1, 1))

        with patch.object(evaluator, "_evaluate_model", side_effect=mock_evaluate):
            result = await evaluator._binary_search_strategy(Mock(), models, [])

        assert result.success
        assert result.minimum_working_model == "cheap"
        assert result.validation_pass_rate == 100.0

    @pytest.mark.asyncio
    async def test_all_models_fail(self):
        mock_lamia = Mock()
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)
        models = ["expensive", "mid", "cheap"]

        async def mock_evaluate(model: str, task):
            return ModelAttemptResult(model=model, success=False, error="fail")

        with patch.object(evaluator, "_evaluate_model", side_effect=mock_evaluate):
            result = await evaluator._binary_search_strategy(Mock(), models, [])

        assert not result.success
        assert result.minimum_working_model is None
        assert result.error_message == "No model succeeded"
        assert result.validation_pass_rate == 0.0

    @pytest.mark.asyncio
    async def test_mixed_results_finds_cheapest_working(self):
        mock_lamia = Mock()
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)
        models = ["expensive", "mid", "cheap"]
        working = {"expensive", "mid"}

        async def mock_evaluate(model: str, task):
            success = model in working
            return ModelAttemptResult(model=model, success=success, error=None if success else "fail")

        with patch.object(evaluator, "_evaluate_model", side_effect=mock_evaluate):
            result = await evaluator._binary_search_strategy(Mock(), models, [])

        assert result.success
        assert result.minimum_working_model == "mid"

    @pytest.mark.asyncio
    async def test_single_model_success(self):
        mock_lamia = Mock()
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)

        async def mock_evaluate(model: str, task):
            return ModelAttemptResult(model=model, success=True)

        with patch.object(evaluator, "_evaluate_model", side_effect=mock_evaluate):
            result = await evaluator._binary_search_strategy(Mock(), ["only"], [])

        assert result.success
        assert result.minimum_working_model == "only"

    @pytest.mark.asyncio
    async def test_single_model_failure(self):
        mock_lamia = Mock()
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)

        async def mock_evaluate(model: str, task):
            return ModelAttemptResult(model=model, success=False, error="fail")

        with patch.object(evaluator, "_evaluate_model", side_effect=mock_evaluate):
            result = await evaluator._binary_search_strategy(Mock(), ["only"], [])

        assert not result.success
        assert result.minimum_working_model is None

    @pytest.mark.asyncio
    async def test_two_models_cheapest_works(self):
        mock_lamia = Mock()
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)
        models = ["expensive", "cheap"]

        async def mock_evaluate(model: str, task):
            return ModelAttemptResult(model=model, success=True)

        with patch.object(evaluator, "_evaluate_model", side_effect=mock_evaluate):
            result = await evaluator._binary_search_strategy(Mock(), models, [])

        assert result.success
        assert result.minimum_working_model == "cheap"

    @pytest.mark.asyncio
    async def test_two_models_only_expensive_works(self):
        mock_lamia = Mock()
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)
        models = ["expensive", "cheap"]

        async def mock_evaluate(model: str, task):
            success = model == "expensive"
            return ModelAttemptResult(model=model, success=success)

        with patch.object(evaluator, "_evaluate_model", side_effect=mock_evaluate):
            result = await evaluator._binary_search_strategy(Mock(), models, [])

        assert result.success
        assert result.minimum_working_model == "expensive"

    @pytest.mark.asyncio
    async def test_two_models_cheaper_is_tried_first(self):
        """With 2 models, the cheaper one (higher index) is the initial midpoint."""
        mock_lamia = Mock()
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)
        models = ["expensive", "cheap"]
        call_order: list[str] = []

        async def mock_evaluate(model: str, task):
            call_order.append(model)
            return ModelAttemptResult(model=model, success=True)

        with patch.object(evaluator, "_evaluate_model", side_effect=mock_evaluate):
            await evaluator._binary_search_strategy(Mock(), models, [])

        assert call_order[0] == "cheap"

    @pytest.mark.asyncio
    async def test_three_models_middle_is_tried_first(self):
        """With 3 models, the middle one is the initial midpoint."""
        mock_lamia = Mock()
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)
        models = ["expensive", "mid", "cheap"]
        call_order: list[str] = []

        async def mock_evaluate(model: str, task):
            call_order.append(model)
            return ModelAttemptResult(model=model, success=True)

        with patch.object(evaluator, "_evaluate_model", side_effect=mock_evaluate):
            await evaluator._binary_search_strategy(Mock(), models, [])

        assert call_order[0] == "mid"

    @pytest.mark.asyncio
    async def test_four_models_cheaper_midpoint_is_tried_first(self):
        """With 4 models, index 1 and 2 are both candidate midpoints — pick 2 (cheaper)."""
        mock_lamia = Mock()
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)
        models = ["m0", "m1", "m2", "m3"]  # m0 = most expensive, m3 = cheapest
        call_order: list[str] = []

        async def mock_evaluate(model: str, task):
            call_order.append(model)
            return ModelAttemptResult(model=model, success=True)

        with patch.object(evaluator, "_evaluate_model", side_effect=mock_evaluate):
            await evaluator._binary_search_strategy(Mock(), models, [])

        assert call_order[0] == "m2"


class TestStepBackStrategyExtended:
    """Extended tests for ModelEvaluator._step_back_strategy."""

    @pytest.mark.asyncio
    async def test_cheapest_model_succeeds_immediately(self):
        mock_lamia = Mock()
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)
        models = ["expensive", "mid", "cheap"]
        call_order: list[str] = []

        async def mock_evaluate(model: str, task):
            call_order.append(model)
            return ModelAttemptResult(model=model, success=model == "cheap")

        with patch.object(evaluator, "_evaluate_model", side_effect=mock_evaluate):
            result = await evaluator._step_back_strategy(Mock(), models, [])

        assert result.success
        assert result.minimum_working_model == "cheap"
        assert call_order == ["cheap"]

    @pytest.mark.asyncio
    async def test_middle_model_succeeds(self):
        mock_lamia = Mock()
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)
        models = ["m0", "m1", "m2", "m3", "m4"]
        call_order: list[str] = []

        async def mock_evaluate(model: str, task):
            call_order.append(model)
            return ModelAttemptResult(model=model, success=model == "m2")

        with patch.object(evaluator, "_evaluate_model", side_effect=mock_evaluate):
            result = await evaluator._step_back_strategy(Mock(), models, [])

        assert result.success
        assert result.minimum_working_model == "m2"
        assert call_order == ["m4", "m3", "m2"]

    @pytest.mark.asyncio
    async def test_step_back_walks_full_list_when_only_top_model_works(self):
        mock_lamia = Mock()
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)
        models = ["expensive", "mid", "cheap"]
        call_order: list[str] = []

        async def mock_evaluate(model: str, task):
            call_order.append(model)
            return ModelAttemptResult(model=model, success=model == "expensive")

        with patch.object(evaluator, "_evaluate_model", side_effect=mock_evaluate):
            result = await evaluator._step_back_strategy(Mock(), models, [])

        assert result.success
        assert result.minimum_working_model == "expensive"
        assert call_order == ["cheap", "mid", "expensive"]

    @pytest.mark.asyncio
    async def test_success_returns_immediately_without_extra_attempts(self):
        mock_lamia = Mock()
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)
        evaluate_mock = AsyncMock(
            return_value=ModelAttemptResult(model="cheap", success=True)
        )

        with patch.object(evaluator, "_evaluate_model", evaluate_mock):
            result = await evaluator._step_back_strategy(
                Mock(), ["expensive", "mid", "cheap"], []
            )

        assert result.success
        evaluate_mock.assert_called_once()


class TestModelEvaluatorCleanup:
    """Test ModelEvaluator.cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_calls_engine_when_own_lamia(self):
        mock_engine = Mock()
        mock_engine.cleanup = AsyncMock()
        mock_lamia = Mock()
        mock_lamia._engine = mock_engine

        with patch("lamia.eval.evaluator.Lamia", return_value=mock_lamia):
            evaluator = ModelEvaluator()

        assert evaluator._own_lamia
        await evaluator.cleanup()
        mock_engine.cleanup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cleanup_skips_when_external_lamia(self):
        mock_engine = Mock()
        mock_engine.cleanup = AsyncMock()
        mock_lamia = Mock()
        mock_lamia._engine = mock_engine

        evaluator = ModelEvaluator(lamia_instance=mock_lamia)
        await evaluator.cleanup()

        mock_engine.cleanup.assert_not_called()


class TestModelEvaluatorAsyncContextManager:
    """Test ModelEvaluator async context manager."""

    @pytest.mark.asyncio
    async def test_aenter_returns_self(self):
        mock_lamia = Mock()
        mock_lamia._engine = Mock()
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)

        entered = await evaluator.__aenter__()

        assert entered is evaluator

    @pytest.mark.asyncio
    async def test_aexit_calls_cleanup(self):
        mock_lamia = Mock()
        mock_lamia._engine = Mock()
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)

        with patch.object(evaluator, "cleanup", AsyncMock()) as cleanup_mock:
            await evaluator.__aexit__(None, None, None)

        cleanup_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_with_triggers_cleanup(self):
        mock_engine = Mock()
        mock_engine.cleanup = AsyncMock()
        mock_lamia = Mock()
        mock_lamia._engine = mock_engine

        with patch("lamia.eval.evaluator.Lamia", return_value=mock_lamia):
            async with ModelEvaluator() as evaluator:
                assert evaluator.lamia is mock_lamia

        mock_engine.cleanup.assert_awaited_once()
