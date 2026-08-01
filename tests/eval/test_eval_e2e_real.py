"""Real end-to-end eval tests using actual Anthropic API."""
import os
import pytest
from lamia import Lamia
from lamia.eval.evaluator import ModelEvaluator
from lamia.types import JSON, HTML, Markdown

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set"
    ),
]

TWO_MODELS = [
    "anthropic:claude-sonnet-4-5-20250929",
    "anthropic:claude-haiku-4-5-20251001",
]


def _make_lamia():
    return Lamia("anthropic:claude-sonnet-4-5-20250929")


class TestEvalE2EReal:

    @pytest.mark.asyncio
    async def test_simple_json(self):
        lamia = _make_lamia()
        async with ModelEvaluator(lamia_instance=lamia) as evaluator:
            result = await evaluator.evaluate_prompt(
                prompt="Return a JSON object: {\"answer\": 42}. Return ONLY valid JSON, nothing else.",
                return_type=JSON,
                models=TWO_MODELS,
                strategy="binary_search",
            )
            print(f"\n=== Simple JSON ===")
            print(f"Success: {result.success}, Min model: {result.minimum_working_model}")
            for a in result.attempts:
                print(f"  {a.model}: success={a.success}, cost={a.cost}, error={a.error}")
            assert result.success

    @pytest.mark.asyncio
    async def test_html_generation(self):
        lamia = _make_lamia()
        async with ModelEvaluator(lamia_instance=lamia) as evaluator:
            result = await evaluator.evaluate_prompt(
                prompt="Create a complete HTML5 page with a title 'Hello' and a paragraph. Return ONLY the HTML.",
                return_type=HTML,
                models=TWO_MODELS,
            )
            print(f"\n=== HTML ===")
            print(f"Success: {result.success}, Min model: {result.minimum_working_model}")
            for a in result.attempts:
                print(f"  {a.model}: success={a.success}, cost={a.cost}, error={a.error}")
            assert result.success

    @pytest.mark.asyncio
    async def test_strategy_comparison(self):
        prompt = "Return a JSON array: [1, 2, 3]. Return ONLY the JSON."
        lamia = _make_lamia()
        async with ModelEvaluator(lamia_instance=lamia) as evaluator:
            bs = await evaluator.evaluate_prompt(prompt=prompt, return_type=JSON, models=TWO_MODELS, strategy="binary_search")
            sb = await evaluator.evaluate_prompt(prompt=prompt, return_type=JSON, models=TWO_MODELS, strategy="step_back")
            print(f"\n=== Strategy Comparison ===")
            print(f"Binary: model={bs.minimum_working_model}, attempts={len(bs.attempts)}")
            print(f"StepBack: model={sb.minimum_working_model}, attempts={len(sb.attempts)}")
            assert bs.success and sb.success

    @pytest.mark.asyncio
    async def test_cost_tracking(self):
        lamia = _make_lamia()
        async with ModelEvaluator(lamia_instance=lamia) as evaluator:
            result = await evaluator.evaluate_prompt(
                prompt="Return JSON: {\"greeting\": \"hello\"}. ONLY JSON.",
                return_type=JSON, models=TWO_MODELS,
            )
            print(f"\n=== Cost Tracking ===")
            for a in result.attempts:
                print(f"  {a.model}: success={a.success}, cost={a.cost}")
                if a.success and a.cost:
                    print(f"    tokens: in={a.cost.input_tokens}, out={a.cost.output_tokens}")
            assert result.success

    @pytest.mark.asyncio
    async def test_multi_step_workflow(self):
        async def workflow(l):
            data = await l.run_async("Return JSON: {\"name\": \"test\"}. ONLY JSON.", JSON)
            summary = await l.run_async(
                f"Write one markdown sentence with **bold** emphasis summarizing: {data}",
                Markdown,
            )
            return summary

        lamia = _make_lamia()
        async with ModelEvaluator(lamia_instance=lamia) as evaluator:
            result = await evaluator.evaluate_script(script_func=workflow, models=TWO_MODELS)
            print(f"\n=== Multi-step ===")
            print(f"Success: {result.success}, Min model: {result.minimum_working_model}")
            for a in result.attempts:
                print(f"  {a.model}: success={a.success}, error={a.error}")
            assert result.success
