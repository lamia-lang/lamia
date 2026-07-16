# Lamia Model Evaluation Module

The Lamia evaluation module helps you find the most cost-effective model that meets your validation requirements. It automatically tests models from most expensive to least expensive, finding the cheapest model that achieves your desired validation pass rate.

## Quick Start

```python
import asyncio
from lamia import Lamia
from lamia.eval.evaluator import ModelEvaluator
from lamia.types import JSON

async def main():
    async with ModelEvaluator() as evaluator:
        # Find cheapest model that can generate valid JSON
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
Pass a `models` list ordered from most expensive/capable to least expensive/capable:
- **OpenAI**: e.g. gpt-4o → gpt-4o-mini → gpt-3.5-turbo
- **Anthropic**: e.g. claude-3-opus → claude-3.5-sonnet → claude-3.5-haiku  
- **Ollama**: e.g. order by parameter count (70b → 8b → 3b → 1b)

### Search Strategies
- **`binary_search`** (default): Efficiently finds the cheapest working model
- **`step_back`**: Two-step-back, one-step-forward approach

### Validation Pass Rates
- **100.0**: Returned on `result.validation_pass_rate` when a model succeeds
- **0.0**: Returned when no model succeeds

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

    # Test HTML generation  
    result = await evaluator.evaluate_prompt(
        prompt="Create a landing page",
        return_type=HTML,
        models=["openai:gpt-4o", "openai:gpt-4o-mini"],
        strategy="step_back",
    )
```

### Using Existing Lamia Instance

```python
# Use your existing Lamia configuration
lamia = Lamia(("openai:gpt-4o", 3))
evaluator = ModelEvaluator(lamia_instance=lamia)

result = await evaluator.evaluate_prompt(
    prompt="Generate documentation",
    return_type=Markdown,
    models=["anthropic:claude-3-opus-20240229", "anthropic:claude-3-5-haiku-20241022"],
)
```

### Complex Script Evaluation

```python
async def my_complex_workflow(lamia):
    """Complex workflow with multiple interconnected calls."""
    # Generate initial data
    user_data = await lamia.run_async("Create user profile", JSON)
    
    # Generate report based on user data  
    report = await lamia.run_async(f"Create report for: {user_data.result_text}", HTML)
    
    # Generate summary
    summary = await lamia.run_async(f"Summarize: {report.result_text}", Markdown)
    
    return summary

async with ModelEvaluator() as evaluator:
    # Evaluate the entire workflow
    result = await evaluator.evaluate_script(
        script_func=my_complex_workflow,
        models=["openai:gpt-4o", "openai:gpt-4o-mini"],
    )
```

### Advanced: Custom Pass Rates

```python
# Try different search strategies for cost optimization
result = await evaluator.evaluate_prompt(
    prompt="Generate creative content",
    return_type=Markdown,
    models=["openai:gpt-4o", "openai:gpt-4o-mini", "openai:gpt-3.5-turbo"],
    strategy="step_back",
)

# Use pricing info to decide: worse model + retries vs better model
if result.cost and result.cost.total_cost_usd < 0.01:
    print("Cost-effective model found!")
```

## Configuration

### Pricing and Model Data

The module uses a unified configuration file at `lamia/eval/config/models_and_pricing.json`:

```json
{
  "openai": {
    "models": [
      {
        "name": "gpt-4o",
        "input_cost_per_1m": 5.00,
        "output_cost_per_1m": 15.00
      },
      {
        "name": "gpt-4o-mini",
        "input_cost_per_1m": 0.15,
        "output_cost_per_1m": 0.60
      }
    ]
  },
  "anthropic": {
    "models": [
      {
        "name": "claude-3-opus-20240229",
        "input_cost_per_1m": 15.00,
        "output_cost_per_1m": 75.00
      }
    ]
  }
}
```

**Note**: Ollama models are not in the config file - they're queried from your local installation.

### API Keys

The evaluation module uses the same API key configuration as the main Lamia library:
- **OpenAI**: `OPENAI_API_KEY` environment variable
- **Anthropic**: `ANTHROPIC_API_KEY` environment variable  
- **Ollama**: No API key needed (local installation)

## EvaluationResult

The `evaluate_prompt()` and `evaluate_script()` methods return an `EvaluationResult` object:

```python
@dataclass
class EvaluationResult:
    minimum_working_model: Optional[str]  # "openai:gpt-4o-mini" 
    success: bool                         # True if any model worked
    validation_pass_rate: float         # 100.0 for successful evaluations
    attempts: List[ModelAttemptResult]  # Details of each model attempt
    cost: Optional[ModelCost]           # Cost of the best model
    error_message: Optional[str]        # Error if evaluation failed
```

### ModelCost

```python
@dataclass  
class ModelCost:
    input_tokens: int                   # Number of input tokens used
    output_tokens: int                  # Number of output tokens generated
    total_cost_usd: float              # Total cost in USD
```

## Best Practices

### 1. Use Appropriate Max Models
```python
# For simple tasks, start with mid-tier models
models=["openai:gpt-4o-mini", "openai:gpt-3.5-turbo"]

# For complex tasks, allow expensive models
models=["openai:gpt-4o", "openai:gpt-4o-mini", "openai:gpt-3.5-turbo"]

# For local-only evaluation
models=["ollama:llama3.2:8b"]
```

### 2. Choose Right Pass Rates
```python
# binary_search: fewer attempts when success boundary is in the middle
strategy="binary_search"

# step_back: starts from the cheapest model
strategy="step_back"
```

### 3. Reuse Lamia Instances
```python
# Reuse configuration and cached adapters
lamia = Lamia(("openai:gpt-4o", 3))  # Your app config
evaluator = ModelEvaluator(lamia_instance=lamia)
```

### 4. Handle Pricing Optionally
```python
# Evaluation works without pricing data
result = await evaluator.evaluate_prompt(...)

# Check if pricing is available
if result.cost:
    print(f"Total spent: ${result.cost.total_cost_usd:.4f}")
else:
    print("Pricing data not available")
```

## Troubleshooting

### "No models available"
- **OpenAI**: Check `OPENAI_API_KEY` environment variable
- **Anthropic**: Check `ANTHROPIC_API_KEY` environment variable
- **Ollama**: Ensure Ollama is running locally (`ollama serve`)

### "No pricing provider found"
- This is normal and expected - evaluation works without pricing
- Pricing is only needed for advanced cost optimization scenarios

### "Validation failed for all models"
- Your prompt might be too complex for the available models
- Try a simpler prompt or add more capable models to your `models` list
- Check that your return_type is appropriate for the task

### Import errors
```python
# Correct imports
from lamia.eval.evaluator import ModelEvaluator
from lamia.types import JSON, HTML, Markdown, XML, CSV
```

## Advanced Usage

### Custom Model Lists
The evaluation module automatically discovers available models, but you can influence the process:

```python
# For OpenAI: Models are fetched from API + config fallback
# For Anthropic: Models come from config file  
# For Ollama: Models are fetched from local installation

# To add new models, update the config file or install them locally (Ollama)
```

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
        
        # Use the best model for production
        if result.success:
            self.lamia.config_provider.set_model_chain([(result.minimum_working_model, 1)])
            
        return result
```

## License

This module is part of the Lamia project and follows the same licensing terms.
