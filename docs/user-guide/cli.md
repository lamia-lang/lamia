# CLI Usage

The Lamia CLI provides a powerful command-line interface for running automation workflows and managing your projects.

## Basic Commands

### Running Workflows

Execute a `.hu` workflow file:

```bash
lamia run workflow.hu
```

With custom configuration:

```bash
lamia run workflow.hu --config config.yaml
```

### Project Management

Initialize a new project:

```bash
lamia init my-project
```

Validate configuration:

```bash
lamia validate-config config.yaml
```

Check project status:

```bash
lamia status
```

## Command Reference

### `lamia run`

Execute a workflow file.

**Syntax:**
```bash
lamia run <workflow_file> [options]
```

**Options:**
- `--config, -c`: Path to configuration file (default: `config.yaml`)
- `--verbose, -v`: Enable verbose logging
- `--dry-run`: Validate workflow without executing
- `--output, -o`: Output format (text, json, yaml)

**Examples:**
```bash
# Basic execution
lamia run automation.hu

# With custom config
lamia run automation.hu --config prod-config.yaml

# Dry run for validation
lamia run automation.hu --dry-run

# Verbose output
lamia run automation.hu --verbose
```

### `lamia init`

Initialize a new Lamia project.

**Syntax:**
```bash
lamia init [project_name] [options]
```

**Options:**
- `--template, -t`: Project template (basic, web, llm, full)
- `--force, -f`: Overwrite existing files

**Examples:**
```bash
# Initialize basic project
lamia init my-project

# Initialize with web automation template
lamia init web-scraper --template web

# Initialize with LLM integration template
lamia init ai-assistant --template llm
```

### `lamia validate-config`

Validate a configuration file.

**Syntax:**
```bash
lamia validate-config <config_file> [options]
```

**Options:**
- `--strict`: Enable strict validation mode
- `--format`: Output format (text, json)

**Examples:**
```bash
# Basic validation
lamia validate-config config.yaml

# Strict validation
lamia validate-config config.yaml --strict
```

### `lamia status`

Show project and environment status.

**Syntax:**
```bash
lamia status [options]
```

**Options:**
- `--check-deps`: Check all dependencies
- `--verbose`: Show detailed information

## Global Options

These options work with all commands:

- `--help, -h`: Show help information
- `--version`: Show version information
- `--quiet, -q`: Suppress output except errors
- `--log-level`: Set logging level (DEBUG, INFO, WARNING, ERROR)

## Configuration

### Configuration File Discovery

Lamia looks for configuration files in the following order:

1. File specified with `--config` option
2. `lamia.yaml` in current directory
3. `config.yaml` in current directory
4. `.lamia/config.yaml` in current directory
5. `~/.lamia/config.yaml` in home directory

### Environment Variables

Override configuration with environment variables:

```bash
export LAMIA_LOG_LEVEL=DEBUG
export LAMIA_CONFIG_PATH=/path/to/config.yaml
export OPENAI_API_KEY=your-key-here
```

## Workflow Files

Workflow files use the `.hu` extension and contain automation instructions.

### Basic Workflow Structure

```yaml
name: "Example Workflow"
description: "A sample automation workflow"

variables:
  target_url: "https://example.com"
  output_file: "results.json"

steps:
  - name: "navigate"
    action: "web.navigate"
    params:
      url: "${target_url}"

  - name: "extract_data"
    action: "web.extract"
    params:
      selector: ".content"
      
  - name: "save_results"
    action: "file.write"
    params:
      path: "${output_file}"
      content: "${extract_data.result}"
```

## Error Handling

### Common Errors

**Configuration Error:**
```
Error: Invalid configuration file 'config.yaml'
```
Solution: Run `lamia validate-config config.yaml` to check for issues.

**Workflow Not Found:**
```
Error: Workflow file 'workflow.hu' not found
```
Solution: Check the file path and ensure the file exists.

**Missing Dependencies:**
```
Error: Required adapter 'playwright' not available
```
Solution: Install missing dependencies or check your environment.

### Debug Mode

Enable debug mode for detailed error information:

```bash
lamia run workflow.hu --log-level DEBUG
```

## Examples

### Web Scraping Workflow

```bash
# Create a web scraping project
lamia init web-scraper --template web

# Run the scraping workflow
lamia run scrape-products.hu --config web-config.yaml
```

### LLM Integration Workflow

```bash
# Create an LLM project
lamia init ai-assistant --template llm

# Run with OpenAI configuration
export OPENAI_API_KEY=your-key
lamia run chat-workflow.hu
```

### File Processing Workflow

```bash
# Process files with validation
lamia run process-data.hu --config file-config.yaml --verbose
```

For more detailed examples, see the [Examples](../examples/basic.md) section.