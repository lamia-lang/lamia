"""Real end-to-end eval tests for scripts, HTML/Markdown generation, and model differentiation."""

import os

import pytest
from pydantic import BaseModel, Field

from lamia import Lamia
from lamia.eval.evaluator import EvaluationResult, ModelEvaluator
from lamia.types import HTML, JSON, Markdown

# Ordered from MOST EXPENSIVE to LEAST EXPENSIVE (required by ModelEvaluator)
TWO_MODELS = [
    "anthropic:claude-sonnet-4-5-20250929",
    "anthropic:claude-haiku-4-5-20251001",
]

CHEAP_MODELS = [
    "anthropic:claude-haiku-4-5-20251001",
]

DEFAULT_LAMIA_MODEL = "anthropic:claude-sonnet-4-5-20250929"

HTML_PROMPT = (
    "Create a complete HTML5 page with a header, navigation bar, main content section "
    "with a table of 3 products (name, price, description), and a footer. "
    "Use semantic HTML elements."
)

MARKDOWN_PROMPT = (
    "Write a technical README for a Python library called 'dataforge' that processes CSV files. "
    "Include: installation, quickstart, API reference with 3 functions, and examples."
)


class RequiredSecretCode(BaseModel):
    access_code: str = Field(pattern=r"^SECRET-42$")


def _require_anthropic_api_key() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set — skipping real API e2e tests")


def _log_eval_result(label: str, result: EvaluationResult) -> None:
    print(f"\n=== {label} ===")
    print(f"  success: {result.success}")
    print(f"  minimum_working_model: {result.minimum_working_model}")
    print(f"  attempts: {len(result.attempts)}")
    for attempt in result.attempts:
        cost_str = "no cost"
        if attempt.cost is not None:
            cost_str = (
                f"input={attempt.cost.input_tokens}, "
                f"output={attempt.cost.output_tokens}"
            )
        status = "OK" if attempt.success else "FAIL"
        error = f" ({attempt.error})" if attempt.error else ""
        print(f"    [{status}] {attempt.model} cost=[{cost_str}]{error}")
    if result.error_message:
        print(f"  error_message: {result.error_message}")


async def _multi_step_workflow(lamia: Lamia):
    user = await lamia.run_async(
        "Create a JSON user profile with name, age, email", JSON
    )
    report = await lamia.run_async(
        f"Create an HTML report summarizing this user: {user}", HTML
    )
    return report


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_html_generation():
    """Evaluate which model can generate a valid HTML page."""
    _require_anthropic_api_key()
    lamia = Lamia(DEFAULT_LAMIA_MODEL)
    async with ModelEvaluator(lamia_instance=lamia) as evaluator:
        result = await evaluator.evaluate_prompt(
            prompt=HTML_PROMPT,
            return_type=HTML,
            models=TWO_MODELS,
        )
        _log_eval_result("HTML generation", result)
        assert result.success, f"Eval failed: {result.error_message}"
        assert result.minimum_working_model is not None
        successful = [a for a in result.attempts if a.success]
        assert len(successful) >= 1


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_markdown_generation():
    """Evaluate which model can generate a valid Markdown README."""
    _require_anthropic_api_key()
    lamia = Lamia(DEFAULT_LAMIA_MODEL)
    async with ModelEvaluator(lamia_instance=lamia) as evaluator:
        result = await evaluator.evaluate_prompt(
            prompt=MARKDOWN_PROMPT,
            return_type=Markdown,
            models=TWO_MODELS,
        )
        _log_eval_result("Markdown generation", result)
        assert result.success, f"Eval failed: {result.error_message}"
        assert result.minimum_working_model is not None
        successful = [a for a in result.attempts if a.success]
        assert len(successful) >= 1


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_evaluate_script_multi_step_workflow():
    """evaluate_script flow — multi-step workflow with JSON then HTML."""
    _require_anthropic_api_key()
    lamia = Lamia(DEFAULT_LAMIA_MODEL)
    async with ModelEvaluator(lamia_instance=lamia) as evaluator:
        result = await evaluator.evaluate_script(
            script_func=_multi_step_workflow,
            models=TWO_MODELS,
        )
        _log_eval_result("multi-step script workflow", result)
        assert result.success, f"Script eval failed: {result.error_message}"
        assert result.minimum_working_model is not None


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_all_models_fail_gracefully():
    """When validation fails for all models, eval returns success=False with error_message."""
    _require_anthropic_api_key()
    lamia = Lamia(CHEAP_MODELS[0])
    async with ModelEvaluator(lamia_instance=lamia) as evaluator:
        result = await evaluator.evaluate_prompt(
            prompt=(
                "Return JSON with access_code set to 'WRONG-99'. "
                "Return ONLY valid JSON, no markdown."
            ),
            return_type=JSON[RequiredSecretCode, False],
            models=CHEAP_MODELS,
            strategy="step_back",
        )
        _log_eval_result("all models fail gracefully", result)
        assert not result.success
        assert result.minimum_working_model is None
        assert result.error_message == "No model succeeded"
        assert len(result.attempts) >= 1
        assert all(not a.success for a in result.attempts)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_cost_tracking_verification():
    """Verify result.attempts have cost information from real API responses."""
    _require_anthropic_api_key()
    lamia = Lamia(DEFAULT_LAMIA_MODEL)
    async with ModelEvaluator(lamia_instance=lamia) as evaluator:
        result = await evaluator.evaluate_prompt(
            prompt=(
                "Return JSON with a single field 'status' set to 'ok'. "
                "Return ONLY valid JSON, no markdown."
            ),
            return_type=JSON,
            models=TWO_MODELS,
            strategy="binary_search",
        )
        _log_eval_result("cost tracking verification", result)
        assert result.success, f"Eval failed: {result.error_message}"
        successful_attempts = [a for a in result.attempts if a.success]
        assert len(successful_attempts) >= 1
        for attempt in successful_attempts:
            assert attempt.cost is not None, f"No cost for {attempt.model}"
            assert attempt.cost.input_tokens > 0, (
                f"input_tokens should be > 0 for {attempt.model}, got {attempt.cost.input_tokens}"
            )
            assert attempt.cost.output_tokens > 0, (
                f"output_tokens should be > 0 for {attempt.model}, got {attempt.cost.output_tokens}"
            )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_strategy_comparison_binary_search_vs_step_back():
    """Compare binary_search and step_back on a stable JSON task."""
    _require_anthropic_api_key()
    stable_prompt = (
        "Return JSON with a single field 'status' set to 'ok'. "
        "Return ONLY valid JSON, no markdown."
    )
    lamia = Lamia(DEFAULT_LAMIA_MODEL)
    async with ModelEvaluator(lamia_instance=lamia) as evaluator:
        binary_result = await evaluator.evaluate_prompt(
            prompt=stable_prompt,
            return_type=JSON,
            models=TWO_MODELS,
            strategy="binary_search",
        )
        step_back_result = await evaluator.evaluate_prompt(
            prompt=stable_prompt,
            return_type=JSON,
            models=TWO_MODELS,
            strategy="step_back",
        )
        _log_eval_result("strategy comparison — binary_search", binary_result)
        _log_eval_result("strategy comparison — step_back", step_back_result)
        assert binary_result.success, f"Binary search failed: {binary_result.error_message}"
        assert step_back_result.success, f"Step back failed: {step_back_result.error_message}"
        assert binary_result.minimum_working_model == step_back_result.minimum_working_model
        print(
            f"\n  binary_search attempts: {len(binary_result.attempts)}, "
            f"step_back attempts: {len(step_back_result.attempts)}"
        )
