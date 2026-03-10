# Model Evaluation

The evaluation module helps you find the most cost-effective model that meets your validation requirements. It tests models from most expensive to least expensive, finding the cheapest one that achieves your desired pass rate.

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

## Advanced usage through Python with pass rates

| Rate | Use Case |
|------|----------|
| `100.0%` (default) | Cheapest model that always works |
| `90.0%` | Allow some failures, use with retry strategies |
| `75.0%` | Creative tasks with more variation tolerance |

```python
result = await evaluator.evaluate_prompt(
    prompt="My prompt",
    return_type=Markdown[MyRepresentationType], # MyType is a pydantic model
    max_model="openai:gpt-4o",
    required_pass_rate_percent=90.0
)
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No models available" | Check API keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or ensure Ollama is running |
| "No pricing provider found" | Normal — evaluation works without pricing data |
| "Validation failed for all models" | Simplify prompt, allow higher max_model, or check return_type, give more hints with the return_type, see the [validation documentation](validation.md) on how to do this |