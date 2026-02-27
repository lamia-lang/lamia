# Configuration

You don't need to know every detail of the configuration file. The only part that you need to know is the model_chain section where you configure the default and fallback models.

In a folder where you want to run Lamia, you can run `lamia init`. It will ask you a few questions and create a config.yaml file for you.
```bash
lamia init
```

After running this command, Lamia will create a config.yaml file for you. Let's see what is inside.

## Configuration File Structure

Lamia uses YAML-based configuration files to customize behavior across all components. This guide covers the configuration system in detail.


A typical `config.yaml` file has the following structure:

```yaml
# Core engine settings
engine:
  default_timeout: 30
  max_retries: 3
  log_level: "INFO"

# LLM provider configurations
model_chain:
  - name: "anthropic:claude-3-haiku-20240307" # primary model/provider
    max_retries: 2
#    temperature: 0.3          # cooler than provider default
#    max_tokens: 500
  - name: "openai"
    max_retries: 1
    temperature: 0.2

# Web automation settings
web_config:
  browser_engine: selenium          # Browser automation engine: selenium, playwright
  http_client: requests             # HTTP client library: requests
  browser_options:
    headless: false                 # Run browsers in headless mode
    timeout: 10.0                   # Default timeout in seconds for browser operations
  http_options:
    timeout: 30.0                   # Default timeout in seconds for HTTP requests
    user_agent: "Bot/1.0"           # User agent string for HTTP requests
```

## Environment Variables

Lamia supports environment variable substitution using the `${VARIABLE_NAME}` syntax:

### Common Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key | For OpenAI LLM usage |
| `ANTHROPIC_API_KEY` | Anthropic API key | For Anthropic LLM usage |

## Configuration Sections

### Engine Configuration

```yaml
engine:
  default_timeout: 30        # Default timeout in seconds
  max_retries: 3            # Maximum retry attempts
  log_level: "INFO"         # Logging level (DEBUG, INFO, WARNING, ERROR)
  parallel_execution: true  # Enable parallel step execution
```

### LLM Configuration for advanced users

#### Anthropic Configuration:

The most important thing to take away from this for non-advanced LLM users is that you can set/change the default model with the default_model property. The default model is used when you don't specify a model, for example, when you specify 'anthropic' the 'anthropic:<default_model>' will be selected.

```yaml
  # Anthropic Configuration
  anthropic:
    enabled: true
    default_model: claude-3-opus-20240229
    models:
      - name: claude-3-opus-20240229
        temperature: 0.2           # Make Claude more factual
        max_tokens: 4000
      - claude-3-sonnet-20240229   # Uses provider defaults
      - name: claude-3-haiku-20240307
        temperature: 0.4
      - claude-2.1
      - claude-2.0
    temperature: 0.7     # Higher = more creative, Lower = more focused
    max_tokens: 1000    # Maximum length of response
    top_k: 50          # Limit vocabulary for sampling
    top_p: 1.0         # Alternative to temperature for sampling
```


## Configuration Profiles

You can use different configuration profiles for different environments:

### Usage with Profiles
```bash
# Development
lamia run workflow.hu --config config-dev.yaml

# Production  
lamia run workflow.hu --config config-prod.yaml
```


## Configuration Best Practices

1. **Use Environment Variables**: Keep sensitive data in environment variables
2. **Reasonable Defaults**: Provide sensible defaults for all optional settings