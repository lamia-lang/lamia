# Lamia Model Evaluation Module

The Lamia evaluation module helps you find the most cost-effective model that meets your validation requirements. It automatically tests models from most expensive to least expensive, finding the cheapest model that achieves your desired validation pass rate.

## Quick Start

```python
import asyncio
from lamia import Lamia
from lamia.eval.evaluator import ModelEvaluator
from lamia.types import JSON

async def main():
    # Create evaluator
    evaluator = ModelEvaluator()
    
    # Find cheapest model that can generate valid JSON
    result = await evaluator.evaluate_prompt(
        prompt="Generate a user profile with name and age",
        return_type=JSON,
        max_model="openai:gpt-4o",  # Don't go more expensive than this
        required_pass_rate_percent=100.0  # Require 100% validation success
    )
    
    print(f"Best model: {result.minimum_working_model}")
    print(f"Success: {result.success}")
    print(f"Total cost: {result.total_cost}")

asyncio.run(main())
```

## Core Concepts

### Model Ordering
Models are automatically ordered from most expensive to least expensive:
- **OpenAI**: Uses live API + config fallback (gpt-4o → gpt-4o-mini → gpt-3.5-turbo)
- **Anthropic**: Uses config data (claude-4 → claude-3-opus → claude-3.5-sonnet → claude-3.5-haiku)  
- **Ollama**: Queries local installation, orders by parameter count (70b → 8b → 3b → 1b)

### Search Strategies
- **`binary_search`** (default): Efficiently finds the cheapest working model
- **`step_back`**: Two-step-back, one-step-forward approach

### Validation Pass Rates
- **100.0%** (default): Find cheapest model that always works
- **85.0%**: Find cheapest model that works 85% of the time (useful with retry strategies)

## Usage Examples

### Basic Prompt Evaluation

```python
from lamia.eval.evaluator import ModelEvaluator
from lamia.types import JSON, HTML, Markdown

evaluator = ModelEvaluator()

# Test JSON generation
result = await evaluator.evaluate_prompt(
    prompt="Create a product catalog entry",
    return_type=JSON,
    max_model="anthropic:claude-3-opus-20240229"
)

# Test HTML generation  
result = await evaluator.evaluate_prompt(
    prompt="Create a landing page",
    return_type=HTML,
    max_model="openai:gpt-4o",
    strategy="step_back"
)
```

### Using Existing Lamia Instance

```python
# Use your existing Lamia configuration
evaluator = ModelEvaluator()

result = await evaluator.evaluate_prompt(
    prompt="Generate documentation",
    return_type=Markdown,
    max_model="anthropic:claude-3-opus-20240229"
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

# Evaluate the entire workflow
result = await evaluator.evaluate_script(
    script_func=my_complex_workflow,
    max_model="openai:gpt-4o"
)
```

### Advanced: Custom Pass Rates

```python
# Accept 90% pass rate for cost optimization
result = await evaluator.evaluate_prompt(
    prompt="Generate creative content",
    return_type=Markdown,
    max_model="openai:gpt-4o",
    required_pass_rate_percent=90.0  # Allow 10% failures
)

# Use pricing info to decide: worse model + retries vs better model
if result.total_cost and result.total_cost.total_cost_usd < 0.01:
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
    best_model: Optional[str]           # "openai:gpt-4o-mini" 
    success: bool                       # True if any model worked
    validation_pass_rate: float         # 100.0 for successful evaluations
    attempts: List[Dict[str, Any]]      # Details of each model attempt
    cost: Optional[ModelCost]           # Cost of the best model
    total_cost: Optional[ModelCost]     # Total cost across all attempts
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
max_model="openai:gpt-4o-mini"

# For complex tasks, allow expensive models
max_model="openai:gpt-4o" 

# For local-only evaluation
max_model="ollama:llama3.2:8b"
```

### 2. Choose Right Pass Rates
```python
# Critical applications - require perfection
required_pass_rate_percent=100.0

# Cost-sensitive applications - allow some failures
required_pass_rate_percent=85.0

# Creative tasks - more tolerance for variation
required_pass_rate_percent=75.0
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
if result.total_cost:
    print(f"Total spent: ${result.total_cost.total_cost_usd:.4f}")
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
- Try a simpler prompt or allow a higher max_model
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
            max_model="openai:gpt-4o"
        )
        
        # Use the best model for production
        if result.success:
            self.lamia.config_provider.set_model_chain([(result.best_model, 1)])
            
        return result
```

## License

This module is part of the Lamia project and follows the same licensing terms.