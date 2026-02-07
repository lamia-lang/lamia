# Model Evaluation

The evaluation module helps you find the most cost-effective model that meets your validation requirements. It tests models from most expensive to least expensive, finding the cheapest one that achieves your desired pass rate.

## Quick Start

```python
import asyncio
from lamia.eval.evaluator import ModelEvaluator
from lamia.types import JSON

async def main():
    evaluator = ModelEvaluator()
    
    result = await evaluator.evaluate_prompt(
        prompt="Generate a user profile with name and age",
        return_type=JSON,
        max_model="openai:gpt-4o",
        required_pass_rate_percent=100.0
    )
    
    print(f"Best model: {result.best_model}")
    print(f"Success: {result.success}")
    if result.total_cost:
        print(f"Total cost: ${result.total_cost.total_cost_usd:.4f}")

asyncio.run(main())
```

## Model Ordering

Models are automatically ordered from most to least expensive:

| Provider | Ordering |
|----------|----------|
| **OpenAI** | Uses live API + config fallback (gpt-4o → gpt-4o-mini → gpt-3.5-turbo) |
| **Anthropic** | Uses config data (claude-4 → claude-3-opus → claude-3.5-sonnet → claude-3.5-haiku) |
| **Ollama** | Queries local installation, orders by parameter count (70b → 8b → 3b) |

## Search Strategies

| Strategy | Description |
|----------|-------------|
| `binary_search` (default) | Efficiently finds cheapest working model |
| `step_back` | Two-step-back, one-step-forward approach |

```python
result = await evaluator.evaluate_prompt(
    prompt="Create a landing page",
    return_type=HTML,
    max_model="openai:gpt-4o",
    strategy="step_back"
)
```

## Pass Rates

| Rate | Use Case |
|------|----------|
| `100.0%` (default) | Cheapest model that always works |
| `90.0%` | Allow some failures, use with retry strategies |
| `75.0%` | Creative tasks with more variation tolerance |

```python
result = await evaluator.evaluate_prompt(
    prompt="Generate creative content",
    return_type=Markdown,
    max_model="openai:gpt-4o",
    required_pass_rate_percent=90.0
)
```

## Script Evaluation

Evaluate entire workflows, not just single prompts:

```python
async def my_workflow(lamia):
    user_data = await lamia.run_async("Create user profile", JSON)
    report = await lamia.run_async(f"Create report for: {user_data.result_text}", HTML)
    return report

result = await evaluator.evaluate_script(
    script_func=my_workflow,
    max_model="openai:gpt-4o"
)
```

## Using with Existing Lamia Instance

```python
from lamia import Lamia

lamia = Lamia(("openai:gpt-4o", 3))
evaluator = ModelEvaluator(lamia_instance=lamia)

result = await evaluator.evaluate_prompt(
    prompt="Generate documentation",
    return_type=Markdown,
    max_model="anthropic:claude-3-opus-20240229"
)
```

## Evaluation Results

```python
result.best_model           # "openai:gpt-4o-mini"
result.success              # True if any model worked
result.validation_pass_rate # 100.0 for successful evaluations
result.attempts             # Details of each model attempt
result.cost                 # Cost of the best model
result.total_cost           # Total cost across all attempts
result.error_message        # Error if evaluation failed
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No models available" | Check API keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or ensure Ollama is running |
| "No pricing provider found" | Normal — evaluation works without pricing data |
| "Validation failed for all models" | Simplify prompt, allow higher max_model, or check return_type |