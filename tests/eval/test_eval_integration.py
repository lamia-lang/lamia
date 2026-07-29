"""Integration-style tests for the evaluation module with mocked Lamia."""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from lamia.eval.evaluator import ModelEvaluator
from lamia.eval.model_cost import ModelCost
from lamia.facade.result_types import LamiaResult
from lamia.validation.base import TrackingContext
from lamia.interpreter.command_types import CommandType


MODELS = ["openai:expensive", "openai:mid", "openai:cheap"]
WORKING_MODELS = {"openai:expensive", "openai:mid"}


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


def _model_from_run_async_call(*args, **kwargs) -> str:
    models = kwargs.get("models")
    if models:
        return models[0].model.name
    return ""


def _make_run_async_side_effect(
    working_models: set[str],
    usage_by_model: dict[str, dict] | None = None,
):
    usage_by_model = usage_by_model or {}

    async def run_async(*args, **kwargs):
        model = _model_from_run_async_call(*args, **kwargs)
        if model not in working_models:
            raise ValueError(f"Model {model} failed validation")
        usage = usage_by_model.get(model, {"prompt_tokens": 10, "completion_tokens": 5})
        return _lamia_result(result_text=f"result from {model}", usage=usage)

    return run_async


def _make_mock_lamia(run_async_side_effect):
    mock_config_provider = Mock()
    mock_config_provider._chain: list = []

    def override_model_chain_with(chain):
        mock_config_provider._chain = list(chain)

    def reset_model_chain():
        mock_config_provider._chain = []

    mock_config_provider.override_model_chain_with = Mock(side_effect=override_model_chain_with)
    mock_config_provider.reset_model_chain = Mock(side_effect=reset_model_chain)
    mock_lamia = Mock()
    mock_lamia._engine = Mock()
    mock_lamia._engine.config_provider = mock_config_provider
    mock_lamia._engine.cleanup = AsyncMock()
    mock_lamia.run_async = AsyncMock(side_effect=run_async_side_effect)
    return mock_lamia


class TestBinarySearchIntegration:
    """Full binary_search flow through evaluate_prompt."""

    @pytest.mark.asyncio
    async def test_finds_boundary_model(self):
        mock_lamia = _make_mock_lamia(_make_run_async_side_effect(WORKING_MODELS))
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)

        result = await evaluator.evaluate_prompt(
            prompt="test prompt",
            return_type=None,
            models=MODELS,
            strategy="binary_search",
        )

        assert result.success
        assert result.minimum_working_model == "openai:mid"
        assert result.validation_pass_rate == 100.0
        assert result.error_message is None
        assert len(result.attempts) == 2
        attempted_models = {a.model for a in result.attempts}
        assert attempted_models == {"openai:mid", "openai:cheap"}


class TestStepBackIntegration:
    """Full step_back flow through evaluate_prompt."""

    @pytest.mark.asyncio
    async def test_cheapest_model_succeeds_immediately(self):
        mock_lamia = _make_mock_lamia(_make_run_async_side_effect({"openai:cheap"}))
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)

        result = await evaluator.evaluate_prompt(
            prompt="test prompt",
            return_type=None,
            models=MODELS,
            strategy="step_back",
        )

        assert result.success
        assert result.minimum_working_model == "openai:cheap"
        assert len(result.attempts) == 1
        assert result.attempts[0].success
        mock_lamia.run_async.assert_awaited_once()


class TestEvaluateScriptIntegration:
    """Full evaluate_script flow."""

    @pytest.mark.asyncio
    async def test_script_evaluation_end_to_end(self):
        call_log: list[str] = []

        async def run_async(*args, **kwargs):
            models = kwargs.get("models")
            if models:
                model = models[0].model.name
            elif mock_lamia._engine.config_provider._chain:
                model = mock_lamia._engine.config_provider._chain[0].model.name
            else:
                model = ""
            call_log.append(model)
            if model == "openai:cheap":
                raise ValueError("cheap model failed")
            return _lamia_result(result_text=f"script output from {model}")

        mock_lamia = _make_mock_lamia(run_async)

        async def my_script(lamia):
            response = await lamia.run_async("do work", None)
            return response

        evaluator = ModelEvaluator(lamia_instance=mock_lamia)
        result = await evaluator.evaluate_script(
            script_func=my_script,
            models=["openai:expensive", "openai:cheap"],
            strategy="binary_search",
        )

        assert result.success
        assert result.minimum_working_model == "openai:expensive"
        mock_lamia._engine.config_provider.reset_model_chain.assert_called()
        assert "openai:expensive" in call_log


class TestAsyncContextManagerIntegration:
    """Evaluator async context manager with full evaluation."""

    @pytest.mark.asyncio
    async def test_async_with_runs_evaluation_and_cleans_up(self):
        mock_engine = Mock()
        mock_engine.cleanup = AsyncMock()
        mock_lamia = _make_mock_lamia(_make_run_async_side_effect(WORKING_MODELS))
        mock_lamia._engine = mock_engine

        with patch("lamia.eval.evaluator.Lamia", return_value=mock_lamia):
            async with ModelEvaluator() as evaluator:
                result = await evaluator.evaluate_prompt(
                    prompt="test",
                    return_type=None,
                    models=MODELS,
                )
                assert result.success

        mock_engine.cleanup.assert_awaited_once()


class TestCostAccumulationIntegration:
    """Cost tracking across evaluation attempts."""

    @pytest.mark.asyncio
    async def test_costs_tracked_per_attempt(self):
        usage_by_model = {
            "openai:expensive": {"prompt_tokens": 100, "completion_tokens": 50},
            "openai:mid": {"prompt_tokens": 80, "completion_tokens": 40},
            "openai:cheap": {"prompt_tokens": 60, "completion_tokens": 30},
        }
        mock_lamia = _make_mock_lamia(
            _make_run_async_side_effect(WORKING_MODELS, usage_by_model)
        )
        evaluator = ModelEvaluator(lamia_instance=mock_lamia)

        result = await evaluator.evaluate_prompt(
            prompt="test",
            return_type=None,
            models=MODELS,
            strategy="binary_search",
        )

        assert result.success
        assert result.cost == ModelCost(input_tokens=80, output_tokens=40)

        successful_attempts = [a for a in result.attempts if a.success]
        assert len(successful_attempts) == 1
        assert successful_attempts[0].cost == ModelCost(input_tokens=80, output_tokens=40)

        failed_attempts = [a for a in result.attempts if not a.success]
        assert len(failed_attempts) == 1
        assert failed_attempts[0].cost is None


class TestStrategyComparisonIntegration:
    """Compare binary_search vs step_back on the same task."""

    @pytest.mark.asyncio
    async def test_both_strategies_find_same_minimum_model(self):
        models = [f"openai:m{i}" for i in range(8)]
        working_models = {"openai:m0"}
        mock_lamia = _make_mock_lamia(_make_run_async_side_effect(working_models))

        binary_evaluator = ModelEvaluator(lamia_instance=mock_lamia)
        binary_result = await binary_evaluator.evaluate_prompt(
            prompt="test",
            return_type=None,
            models=models,
            strategy="binary_search",
        )

        mock_lamia.run_async.reset_mock()
        step_back_evaluator = ModelEvaluator(lamia_instance=mock_lamia)
        step_back_result = await step_back_evaluator.evaluate_prompt(
            prompt="test",
            return_type=None,
            models=models,
            strategy="step_back",
        )

        assert binary_result.minimum_working_model == "openai:m0"
        assert step_back_result.minimum_working_model == "openai:m0"
        assert binary_result.success
        assert step_back_result.success
        assert len(binary_result.attempts) < len(step_back_result.attempts)
