# Configuration

Lamia uses YAML-based configuration files to customize behavior across all components. This guide covers the configuration system in detail.

## Configuration File Structure

A typical `config.yaml` file has the following structure:

```yaml
# Core engine settings
engine:
  default_timeout: 30
  max_retries: 3
  log_level: "INFO"

# Validation settings
validation:
  strict_mode: true
  custom_validators_path: "./validators"

# LLM provider configurations
llm:
  default_provider: "openai"
  openai:
    api_key: "${OPENAI_API_KEY}"
    model: "gpt-3.5-turbo"
    temperature: 0.7
  anthropic:
    api_key: "${ANTHROPIC_API_KEY}"
    model: "claude-3-sonnet-20240229"

# Web automation settings
web:
  default_browser: "playwright"
  playwright:
    browser_type: "chromium"
    headless: true
    timeout: 30000
  selenium:
    driver_path: "/path/to/chromedriver"

# File system settings
filesystem:
  default_adapter: "local"
  s3:
    region: "us-east-1"
    bucket: "my-default-bucket"
  gcs:
    project_id: "my-project"
    bucket: "my-gcs-bucket"

# HTTP client settings
http:
  timeout: 30
  max_redirects: 5
  user_agent: "Lamia/1.0"
```

## Environment Variables

Lamia supports environment variable substitution using the `${VARIABLE_NAME}` syntax:

```yaml
llm:
  openai:
    api_key: "${OPENAI_API_KEY}"
    organization: "${OPENAI_ORG_ID}"
```

### Common Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key | For OpenAI LLM usage |
| `ANTHROPIC_API_KEY` | Anthropic API key | For Anthropic LLM usage |
| `AWS_ACCESS_KEY_ID` | AWS access key | For S3 adapter |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | For S3 adapter |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP credentials | For GCS adapter |

## Configuration Sections

### Engine Configuration

```yaml
engine:
  default_timeout: 30        # Default timeout in seconds
  max_retries: 3            # Maximum retry attempts
  log_level: "INFO"         # Logging level (DEBUG, INFO, WARNING, ERROR)
  parallel_execution: true  # Enable parallel step execution
```

### LLM Configuration

#### OpenAI Configuration
```yaml
llm:
  openai:
    api_key: "${OPENAI_API_KEY}"
    model: "gpt-3.5-turbo"     # Default model
    temperature: 0.7          # Creativity (0.0-2.0)
    max_tokens: 1000          # Maximum response tokens
    top_p: 1.0               # Nucleus sampling
    frequency_penalty: 0.0    # Repetition penalty
    presence_penalty: 0.0     # Topic diversity
```

#### Anthropic Configuration
```yaml
llm:
  anthropic:
    api_key: "${ANTHROPIC_API_KEY}"
    model: "claude-3-sonnet-20240229"
    max_tokens: 1000
    temperature: 0.7
```

#### Ollama Configuration
```yaml
llm:
  ollama:
    base_url: "http://localhost:11434"
    model: "llama2"
    temperature: 0.7
```

### Web Automation Configuration

#### Playwright Configuration
```yaml
web:
  playwright:
    browser_type: "chromium"   # chromium, firefox, webkit
    headless: true            # Run in headless mode
    timeout: 30000           # Page timeout in milliseconds
    viewport:
      width: 1280
      height: 720
    user_agent: "Custom User Agent"
```

#### Selenium Configuration
```yaml
web:
  selenium:
    driver_path: "/path/to/chromedriver"
    browser: "chrome"         # chrome, firefox, safari, edge
    headless: true
    window_size: "1280,720"
    implicit_wait: 10
```

### File System Configuration

#### Local File System
```yaml
filesystem:
  local:
    base_path: "/data"        # Base directory for operations
    create_dirs: true         # Auto-create directories
```

#### S3 Configuration
```yaml
filesystem:
  s3:
    region: "us-east-1"
    bucket: "my-bucket"
    access_key_id: "${AWS_ACCESS_KEY_ID}"
    secret_access_key: "${AWS_SECRET_ACCESS_KEY}"
    endpoint_url: null        # For S3-compatible services
```

#### Google Cloud Storage
```yaml
filesystem:
  gcs:
    project_id: "my-project"
    bucket: "my-bucket"
    credentials_path: "${GOOGLE_APPLICATION_CREDENTIALS}"
```

### Validation Configuration

```yaml
validation:
  strict_mode: true           # Fail on first validation error
  custom_validators_path: "./validators"  # Path to custom validators
  max_errors: 100            # Maximum errors to collect
  continue_on_error: false   # Continue validation after errors
```

### HTTP Configuration

```yaml
http:
  timeout: 30               # Request timeout in seconds
  max_redirects: 5          # Maximum redirect follows
  verify_ssl: true          # Verify SSL certificates
  user_agent: "Lamia/1.0"   # Default User-Agent header
  headers:                  # Default headers
    "Accept": "application/json"
```

## Configuration Profiles

You can use different configuration profiles for different environments:

### Development Configuration
```yaml
# config-dev.yaml
engine:
  log_level: "DEBUG"
  
web:
  playwright:
    headless: false    # Show browser for debugging
    slow_mo: 1000     # Slow down operations
```

### Production Configuration
```yaml
# config-prod.yaml
engine:
  log_level: "WARNING"
  
web:
  playwright:
    headless: true
```

### Usage with Profiles
```bash
# Development
lamia run workflow.hu --config config-dev.yaml

# Production  
lamia run workflow.hu --config config-prod.yaml
```

## Configuration Validation

Lamia validates configuration files on startup. Common validation errors:

### Invalid YAML Syntax
```yaml
# ❌ Invalid - missing colon
engine
  timeout: 30
```

### Missing Required Fields
```yaml
# ❌ Invalid - missing API key
llm:
  openai:
    model: "gpt-3.5-turbo"
    # api_key is required
```

### Invalid Values
```yaml
# ❌ Invalid - timeout must be positive
engine:
  timeout: -1
```

## Advanced Configuration

### Custom Validators Path
```yaml
validation:
  custom_validators_path: "./my_validators"
```

### Multiple Provider Configurations
```yaml
llm:
  providers:
    openai_gpt4:
      type: "openai"
      api_key: "${OPENAI_API_KEY}"
      model: "gpt-4"
    openai_gpt35:
      type: "openai" 
      api_key: "${OPENAI_API_KEY}"
      model: "gpt-3.5-turbo"
    claude:
      type: "anthropic"
      api_key: "${ANTHROPIC_API_KEY}"
      model: "claude-3-sonnet-20240229"
```

### Conditional Configuration
```yaml
engine:
  # Use environment variable with fallback
  log_level: "${LOG_LEVEL:-INFO}"
  
  # Conditional timeouts
  timeout: "${ENVIRONMENT == 'production' ? 60 : 30}"
```

## Configuration Best Practices

1. **Use Environment Variables**: Keep sensitive data in environment variables
2. **Validate Early**: Use configuration validation in CI/CD pipelines
3. **Document Defaults**: Provide sensible defaults for all optional settings
4. **Environment Profiles**: Use different configs for dev/staging/prod
5. **Version Control**: Store configuration templates in version control
6. **Secret Management**: Use proper secret management for API keys

## Troubleshooting Configuration

### Check Configuration Loading
```python
from lamia.engine.config_provider import ConfigProvider

config = ConfigProvider("config.yaml")
print(config.get_config())  # Print loaded configuration
```

### Validate Configuration
```bash
lamia validate-config config.yaml
```

### Environment Variable Issues
```bash
# Check if environment variables are set
env | grep -E "(OPENAI|ANTHROPIC|AWS)"
```

For more help with configuration, see the [API Reference](../reference/) or check our [GitHub Issues](https://github.com/your-username/lamia/issues).