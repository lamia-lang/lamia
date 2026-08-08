# Lamia Model Evaluation Module

The Lamia evaluation module helps you find the most cost-effective model that can successfully complete a task. You provide an ordered list of models (most expensive/capable to least), and the evaluator tests them using a search strategy to find the cheapest model that works.

## Quick Start

```python
import asyncio
from lamia.eval.evaluator import ModelEvaluator
from lamia.types import JSON

async def main():
    async with ModelEvaluator() as evaluator:
        result = await evaluator.evaluate_prompt(
            prompt="Generate a user profile with name and age",
            return_type=JSON,
            models=["openai:gpt-4o", "openai:gpt-4o-mini", "openai:gpt-3.5-turbo"],
        )

        print(f"Best model: {result.minimum_working_model}")
        print(f"Success: {result.success}")
        print(f"Cost: {result.cost}")

asyncio.run(main())
```

## Core Concepts

### Model Ordering
You pass an explicit `models` list ordered from most expensive/capable to least expensive/capable:

```python
models=["openai:gpt-4o", "openai:gpt-4o-mini", "openai:gpt-3.5-turbo"]
```

The evaluator searches this list to find the cheapest model that succeeds. Order matters — put your most capable models first and cheapest models last.

### Search Strategies
- **`binary_search`** (default): Efficiently finds the cheapest working model via binary search
- **`step_back`**: Linear scan from cheapest to most expensive; returns the first model that passes

### Validation
A model attempt succeeds only when:
1. The task executes without exceptions
2. Lamia validation passes (validation failures raise exceptions)
3. The result is not `None`

On success, `validation_pass_rate` is `100.0`; on failure it is `0.0`.

## Usage Examples

### Basic Prompt Evaluation

```python
from lamia.eval.evaluator import ModelEvaluator
from lamia.types import JSON, HTML, Markdown

async with ModelEvaluator() as evaluator:
    # Test JSON generation
    result = await evaluator.evaluate_prompt(
        prompt="Create a product catalog entry",
        return_type=JSON,
        models=["anthropic:claude-3-opus-20240229", "anthropic:claude-3-5-haiku-20241022"],
    )

    # Test HTML generation with step_back strategy
    result = await evaluator.evaluate_prompt(
        prompt="Create a landing page",
        return_type=HTML,
        models=["openai:gpt-4o", "openai:gpt-4o-mini"],
        strategy="step_back",
    )
```

### Using Existing Lamia Instance

```python
from lamia import Lamia
from lamia.eval.evaluator import ModelEvaluator
from lamia.types import Markdown

lamia = Lamia(("openai:gpt-4o", 3))
evaluator = ModelEvaluator(lamia_instance=lamia)

result = await evaluator.evaluate_prompt(
    prompt="Generate documentation",
    return_type=Markdown,
    models=["openai:gpt-4o", "openai:gpt-4o-mini", "openai:gpt-3.5-turbo"],
)
```

### Complex Script Evaluation

```python
from lamia import Lamia
from lamia.types import JSON, HTML, Markdown

async def my_complex_workflow(lamia: Lamia):
    """Complex workflow with multiple interconnected calls."""
    user_data = await lamia.run_async("Create user profile", JSON)
    report = await lamia.run_async(f"Create report for: {user_data.result_text}", HTML)
    summary = await lamia.run_async(f"Summarize: {report.result_text}", Markdown)
    return summary

async with ModelEvaluator() as evaluator:
    result = await evaluator.evaluate_script(
        script_func=my_complex_workflow,
        models=["openai:gpt-4o", "openai:gpt-4o-mini"],
    )
```

### Choosing a Strategy

```python
models = ["openai:gpt-4o", "openai:gpt-4o-mini", "openai:gpt-3.5-turbo"]

# binary_search: fewer attempts when the cheapest working model is near the middle
result = await evaluator.evaluate_prompt(
    prompt="Generate creative content",
    return_type=Markdown,
    models=models,
    strategy="binary_search",
)

# step_back: starts from the cheapest model; good when cheap models often work
result = await evaluator.evaluate_prompt(
    prompt="Generate creative content",
    return_type=Markdown,
    models=models,
    strategy="step_back",
)

if result.cost:
    print(f"Cost: {result.cost}")
```

## API Reference

### `ModelEvaluator.evaluate_prompt`

```python
async def evaluate_prompt(
    self,
    prompt: str,
    return_type: Optional[Type[BaseType]],
    models: List[str],
    strategy: str = "binary_search",
) -> EvaluationResult
```

| Parameter | Description |
|-----------|-------------|
| `prompt` | The prompt to evaluate |
| `return_type` | Expected return type for validation (e.g. `JSON`, `HTML`) |
| `models` | Model names ordered most to least expensive/capable |
| `strategy` | `"binary_search"` or `"step_back"` |

### `ModelEvaluator.evaluate_script`

```python
async def evaluate_script(
    self,
    script_func: Callable[[Lamia], Any],
    models: List[str],
    strategy: str = "binary_search",
) -> EvaluationResult
```

| Parameter | Description |
|-----------|-------------|
| `script_func` | Async function that receives a `Lamia` instance and runs the workflow |
| `models` | Model names ordered most to least expensive/capable |
| `strategy` | `"binary_search"` or `"step_back"` |

## EvaluationResult

Both `evaluate_prompt()` and `evaluate_script()` return an `EvaluationResult`:

```python
@dataclass
class EvaluationResult:
    minimum_working_model: Optional[str]  # Cheapest model that succeeded
    success: bool                         # True if any model worked
    validation_pass_rate: float           # 100.0 on success, 0.0 on failure
    attempts: List[ModelAttemptResult]    # Details of each model attempt
    cost: Optional[ModelCost]             # Cost of the best (minimum working) model
    error_message: Optional[str]          # Error if evaluation failed
```

### ModelAttemptResult

```python
@dataclass
class ModelAttemptResult:
    model: str
    success: bool
    cost: Optional[ModelCost] = None
    result: Any = None
    error: Optional[str] = None
```

### ModelCost

```python
@dataclass
class ModelCost:
    input_tokens: int
    output_tokens: int
    total_cost_usd: float = 0.0  # Monetary cost when pricing is available
```

## Best Practices

### 1. Order Models Correctly
```python
# Most capable first, cheapest last
models=["openai:gpt-4o", "openai:gpt-4o-mini", "openai:gpt-3.5-turbo"]
```

### 2. Pick the Right Strategy
```python
# Fewer total attempts when success boundary is in the middle of the list
strategy="binary_search"

# Fast path when the cheapest model often works
strategy="step_back"
```

### 3. Reuse Lamia Instances
```python
lamia = Lamia(("openai:gpt-4o", 3))
evaluator = ModelEvaluator(lamia_instance=lamia)
```

### 4. Use the Async Context Manager
```python
async with ModelEvaluator() as evaluator:
    result = await evaluator.evaluate_prompt(...)
# Resources are cleaned up automatically
```

### 5. Handle Pricing Optionally
```python
result = await evaluator.evaluate_prompt(...)

if result.cost:
    print(f"Tokens: {result.cost.input_tokens} in, {result.cost.output_tokens} out")
    if result.cost.total_cost_usd > 0:
        print(f"Cost: ${result.cost.total_cost_usd:.4f}")
```

## API Keys

The evaluation module uses the same API key configuration as the main Lamia library:
- **OpenAI**: `OPENAI_API_KEY` environment variable
- **Anthropic**: `ANTHROPIC_API_KEY` environment variable
- **Ollama**: No API key needed (local installation)

## Troubleshooting

### "Models list cannot be empty"
Pass at least one model in the `models` parameter.

### A model always fails / authentication errors
- **OpenAI**: check the `OPENAI_API_KEY` environment variable is set
- **Anthropic**: check the `ANTHROPIC_API_KEY` environment variable is set
- **Ollama**: ensure Ollama is running locally (`ollama serve`)

### "No model succeeded"
- Your prompt or script may be too complex for the models in your list
- Try adding more capable models at the start of the list
- Check that your `return_type` is appropriate for the task

### Import errors
```python
from lamia.eval.evaluator import ModelEvaluator
from lamia.types import JSON, HTML, Markdown, XML, CSV
```

## Advanced Usage

### Integration with Existing Workflows
```python
class MyApp:
    def __init__(self):
        self.lamia = Lamia(my_config)
        self.evaluator = ModelEvaluator(lamia_instance=self.lamia)

    async def optimize_task(self, task_prompt, return_type):
        """Find the best model for a specific task."""
        result = await self.evaluator.evaluate_prompt(
            prompt=task_prompt,
            return_type=return_type,
            models=["openai:gpt-4o", "openai:gpt-4o-mini", "openai:gpt-3.5-turbo"],
        )

        if result.success:
            self.lamia.config_provider.set_model_chain(
                [(result.minimum_working_model, 1)]
            )

        return result
```

## License

This module is part of the Lamia project and follows the same licensing terms.
