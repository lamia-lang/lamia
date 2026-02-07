# Lamia Documentation

Welcome to the Lamia documentation! Lamia is a comprehensive automation and validation framework for Python that provides powerful tools for data validation, web automation, and LLM integration.

## What is Lamia?

Lamia is a flexible framework designed to help developers automate complex workflows and validate data structures. It provides:

- **Validation Framework**: Robust validation system for various data types and structures
- **Web Automation**: Browser automation and web scraping capabilities
- **LLM Integration**: Support for various language models including OpenAI, Anthropic, and local models
- **File Operations**: File system operations and cloud storage adapters
- **CLI Tools**: Command-line interface for easy automation

## Key Features

### 🔍 **Validation System**
- Comprehensive validators for JSON, XML, HTML, CSV, and more
- Custom validator support
- Type-safe validation with Pydantic integration

### 🌐 **Web Automation**
- Playwright and Selenium integration
- Smart selector resolution with AI assistance
- HTTP client with retry mechanisms

### 🤖 **LLM Integration**
- Support for OpenAI GPT models
- Anthropic Claude integration
- Local LLM support (Ollama, Llama)
- Model cost tracking and evaluation

### 📁 **File Operations**
- Local file system operations
- Cloud storage support (S3, GCS)
- FTP adapter for remote file operations

### ⚙️ **Engine & Configuration**
- Flexible configuration system
- Plugin architecture
- Retry mechanisms with backoff strategies

## Quick Start

Get started with Lamia in just a few steps:

1. **Installation**
   ```bash
   pip install lamia
   ```

2. **Basic Usage**
   ```python
   from lamia import Lamia
   
   # Initialize Lamia with configuration
   lamia = Lamia("config.yaml")
   
   # Run automation workflows
   result = lamia.run("your_workflow.hu")
   ```

3. **CLI Usage**
   ```bash
   lamia run workflow.hu --config config.yaml
   ```

## Architecture Overview

Lamia is built with a modular architecture:

- **Core Engine**: Central orchestration and execution engine
- **Adapters**: Pluggable adapters for different services (LLM, storage, web)
- **Validation**: Comprehensive validation framework
- **Actions**: Pre-built actions for common operations
- **CLI**: Command-line interface for automation

## Navigation

- **[Getting Started](getting-started/installation.md)**: Installation and setup instructions
- **[User Guide](user-guide/cli.md)**: Detailed usage guides and tutorials  
- **[API Reference](reference/)**: Complete API documentation
- **[Examples](examples/basic.md)**: Code examples and use cases
- **[Development](development/contributing.md)**: Contributing and development information

## Community and Support

- **GitHub**: [Repository](https://github.com/lamia-lang/lamia)
- **Issues**: [Bug Reports & Feature Requests](https://github.com/lamia-lang/lamia/issues)
- **Documentation**: This site contains comprehensive guides and API reference

---

Ready to get started? Head over to the [Installation Guide](getting-started/installation.md) to begin using Lamia in your projects!