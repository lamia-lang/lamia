# LSG-3: Project Structure Guide

This guide defines conventions for organizing Lamia projects --
folder layout, naming, and how to structure multi-agent workflows.

## Basic project layout

A minimal Lamia project:

```
my-project/
  config.yaml       # LLM configuration (models, keys)
  main.lm           # Entry point
  summarize.hu      # A prompt template
```

Run with `lamia main.lm` from the project root.

## Recommended layout for larger projects

```
my-project/
  config.yaml
  orchestrator.lm           # Main workflow entry point
  team/                      # Agent prompt templates
    researcher.hu
    developer.hu
    reviewer.hu
    qa_analyst.hu
  models/                    # Pydantic models for validation, one file or multiple files
    schemas.lm
  data/                      # Input data, fixtures
    requirements.txt
  output/                    # Generated artifacts (gitignored)
    report.html
```

### Key conventions

- **`config.yaml`** at project root -- contains model configuration
- **`orchestrator.lm`** as the main entry point for multi-agent workflows
- **`team/`** directory for agent `.hu` files
- **`models/`** for shared Pydantic model definitions
- **`data/`** for input files referenced via `{@...}`
- **`output/`** for generated files (add to `.gitignore`)

## Naming conventions

### Files

| Type | Convention | Examples |
|---|---|---|
| `.hu` files | `snake_case`, verb-first | `review_code.hu`, `draft_email.hu` |
| `.lm` files | `snake_case` | `orchestrator.lm`, `pipeline.lm` |
| Directories | `snake_case` | `team/`, `models/`, `data/` |

### Agent names (`.hu` filenames)

Since `.hu` filenames become callable function names, choose names
that read naturally at the call site:

```python
# Good -- reads like natural function calls
analysis = researcher(topic="market trends") -> JSON[Analysis]
code = developer(specs=analysis) -> TEXT
feedback = reviewer(code=code, specs=analysis) -> JSON[Review]

# Bad -- unclear what these do
result1 = agent1(input="market trends") -> JSON[Analysis]
output = worker(data=result1) -> TEXT
```

Use role-based names for agents (`researcher`, `developer`, `reviewer`)
and action-based names for utility prompts (`summarize`, `extract`,
`translate`).

## Multi-agent workflows

### The orchestrator pattern

For projects with multiple agents, use a single `orchestrator.lm`
as the entry point that coordinates the workflow:

```python
# orchestrator.lm

# Pipeline: research -> develop -> review
prd = product_manager(brief=brief) -> JSON[PRD]
code = developer(specs=prd) -> JSON[Implementation]
review = reviewer(code=code, specs=prd) -> JSON[Review]

if not review.approved:
    code = developer(specs=prd, feedback=review.findings) -> JSON[Implementation]
```

### Agent composition

Agents (`.hu` files) cannot call other agents directly.
All orchestration flows through `.lm` files:

```
orchestrator.lm
  -> calls researcher.hu
  -> passes result to developer.hu
  -> passes result to reviewer.hu
  -> loops if review fails
```

This keeps each agent focused on a single responsibility and makes
the workflow visible in one place.

### File usage

Use either relative or absolute `{@filepath}` paths or use Lamia's file context manager `with files("~/Documents/")` to inject file contents into the prompt from the `.lm` file invoker:

```
# team/developer.hu
You are implementing features based on the project requirements.

Requirements:
{@../data/requirements.txt}

Implement the following specifications:
{specs}
```

or 

```python
# orchestrator.lm
with files("data/"):
    code = developer(specs=prd) -> JSON[Implementation]
```

where devleoper.hu is:

```python
# team/developer.hu
You are implementing features based on the project requirements.

Requirements:
{@requirements.txt}

Implement the following specifications:
{specs}
```

## Configuration

### config.yaml

The most important part for configuration is the model chain. Define the model chain in the first line of the config.yaml file. It is recommended to have at least one fallback model in the model chain.

```yaml
models:
  - openai:gpt-4
  - anthropic:sonnet-4    # fallback
```

Override per-function only when a specific task needs a different
model (e.g., a cheaper model, a model that is fine-tuned for the task, etc.):

```python
def classify(models="openai:gpt-4o-mini"):
    "Classify the sentiment of: {text}"
```

## Scaling up

### When a project grows

As projects grow, split orchestration into focused pipelines:

```
my-project/
  config.yaml
  pipelines/
    research.lm              # Research pipeline
    implementation.lm        # Implementation pipeline
    review.lm                # Review pipeline
  team/
    researcher.hu
    developer.hu
    reviewer.hu
    qa_analyst.hu
  models/
    research_models.py
    implementation_models.py
  data/
    ...
```

### Function/File name conflics

Per project basis `.lm` functions and `.hu` file names (which are function names) must be unique.

### Avoid these patterns

- **`.hu` files in the project root** mixed with `.lm` files, instead
  group agents under `team/` or a descriptive directory
- **Deeply nested directories** - keep the tree shallow (2-3 levels max)
- **Generic names** - `agent.hu`, `process.lm`, `data.py` say nothing
  about what they do
- **Pydantic models inside `.lm` files** for large projects - 
  extract to `models/` when shared across multiple `.lm` files
