# Model Evaluation

The evaluation module helps you find the most cost-effective model that meets your validation requirements. It tests models from most capable to least capable, finding the cheapest one that passes validation.

## Quick Start

```bash
lamia eval <your_script.lm>
```


## Search Strategies

| Strategy | Description |
|----------|-------------|
| `binary_search` (default) | Efficiently finds cheapest working model |
| `step_back` | Tests from cheapest up to most expensive model |


With both strategies, the eval extracts all LLM prompts from the script and evaluates them one by one.
The evaluation stops on the first prompt where no model in the range succeeds. But if at least one model passes for a prompt, it moves on to the next prompt.

## Python API

Use `ModelEvaluator` when you want to evaluate prompts or scripts directly from Python:

```python
import asyncio
from lamia.eval.evaluator import ModelEvaluator
from lamia.types import JSON

async def main():
    async with ModelEvaluator() as evaluator:
        result = await evaluator.evaluate_prompt(
            prompt="Generate a user profile with name and age",
            return_type=JSON,
            models=[
                "openai:gpt-4o",           # most capable (tried first in binary search)
                "openai:gpt-4o-mini",
                "openai:gpt-3.5-turbo",    # cheapest
            ],
            strategy="binary_search",
        )

        print(f"Minimum working model: {result.minimum_working_model}")
        print(f"Success: {result.success}")
        if result.cost:
            print(f"Cost: {result.cost}")

asyncio.run(main())
```

Models must be ordered from **most capable to least capable** (most expensive first). The evaluator finds the cheapest model in the list that passes validation.

For scripts with multiple `lamia.run_async()` calls, use `evaluate_script()`:

```python
from lamia import Lamia
from lamia.eval.evaluator import ModelEvaluator
from lamia.types import JSON, HTML

async def my_workflow(lamia: Lamia):
    user_data = await lamia.run_async("Create user profile", JSON)
    return await lamia.run_async(f"Create report for: {user_data.result_text}", HTML)

async with ModelEvaluator() as evaluator:
    result = await evaluator.evaluate_script(
        script_func=my_workflow,
        models=["openai:gpt-4o", "openai:gpt-4o-mini"],
    )
```

### Result object

`evaluate_prompt()` and `evaluate_script()` return an `EvaluationResult`:

| Attribute | Description |
|-----------|-------------|
| `minimum_working_model` | Cheapest model that passed validation, or `None` |
| `success` | Whether any model succeeded |
| `validation_pass_rate` | `100.0` if a model succeeded, `0.0` otherwise |
| `attempts` | List of `ModelAttemptResult` for each model tried |
| `cost` | Token usage for the winning model (`ModelCost`), or `None` |
| `error_message` | Error description when all models fail |

Each attempt in `result.attempts` has `model`, `success`, `cost`, `result`, and `error` fields.

For structured validation, pass a Lamia type as `return_type` — for example `JSON`, `HTML`, or `JSON[MyModel]` where `MyModel` is a Pydantic model (see [validation documentation](validation.md)).

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No models available" | Check API keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or ensure Ollama is running |
| "No pricing provider found" | Normal — evaluation works without pricing data |
| "Validation failed for all models" | Simplify prompt, include more capable models in your `models` list, or check `return_type`; add hints to your return type — see the [validation documentation](validation.md) on how to do this |
