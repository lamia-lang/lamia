# Selector Resolution System

The selector resolution system handles both traditional CSS/XPath selectors and AI-powered natural language selectors for web automation.

## Overview

This system allows you to use two types of selectors:

1. **Traditional Selectors**: Standard CSS selectors (`button.primary`) or XPath (`//button[@class='primary']`)
2. **AI Selectors**: Natural language descriptions (`"Sign in button"`, `"Search for products"`)

When you provide a natural language description, the AI analyzes the page HTML and returns the appropriate CSS selector.

## Architecture

```
selector_resolution/
├── selector_resolution_service.py    # Main orchestrator service
├── response_parser.py                # AI response parsing interface
├── selector_parser.py               # Selector classification
├── selector_cache.py                # Caching layer
├── ai_selector_resolver.py          # Legacy AI resolver
└── validators/                      # Validation components
    └── ai_resolved_selector_validator.py
```

## Key Components

### 1. SelectorResolutionService

The main service that orchestrates the entire resolution process:

- **Input**: Any selector (CSS, XPath, or natural language)
- **Output**: Valid CSS selector ready for browser automation
- **Features**: Caching, validation, ambiguity handling, deduction logic

```python
# Usage example
service = SelectorResolutionService(llm_manager, get_page_html_func)
resolved = await service.resolve_selector(
    selector="Sign in button", 
    page_url="https://example.com",
    operation_type="click"
)
# Returns: "button.btn-primary"
```

### 2. Response Parser Interface

Handles different AI response formats:

- **AmbiguousFormatResponseParser**: Uses `AMBIGUOUS` format for multiple matches
- **Extensible**: Can add JSON, XML, or other response formats

### 3. Caching Layer

Intelligent caching to avoid repeated AI calls:

- **Location**: `.lamia_cache/selectors/selector_resolutions.json`
- **Key Format**: `"{selector}|{page_url}"`
- **Persistence**: Survives across runs
- **Invalidation**: Automatic when selectors fail validation

## AI Selector Features

### Basic Usage

```python
# Natural language selectors
"Sign in button"
"Search input field"
"Submit form"
"Close modal"
```

### Ambiguity Handling

When multiple elements match your description, the AI returns suggestions:

```
🚨 AMBIGUOUS SELECTOR: 'Sign in'
Multiple elements match your description. Please be more specific:

Option 1: "Sign in" 
└─ Selector: button.btn-primary

Option 2: "Sign in with Google"
└─ Selector: button.google-signin

Option 3: "Sign in with Apple"
└─ Selector: button.apple-signin
```

### Deduction Logic

The system can automatically identify the "main" element when there are multiple options:

```python
# Input: "Sign in"
# AI finds: ["Sign in", "Sign in with Google", "Sign in with Apple"]
# Deduction: "Sign in" is shortest/simplest → main button
# Output: Enhanced description that excludes others
"Sign in but not the with Google, with Apple options"
```

### Operation-Specific Intelligence

The AI adapts its search based on the operation type:

- **Click**: Looks for buttons, links, clickable elements
- **Type**: Focuses on input fields, textareas
- **Select**: Searches for dropdown menus
- **Hover**: Finds hoverable elements

## Cache Management

### Cache Location

```
.lamia_cache/selectors/selector_resolutions.json
```

### Cache Structure

```json
{
  "Sign in button|https://example.com": "button.btn-primary",
  "Search input|https://shop.com": "input[name='query']"
}
```

### Cache Operations

```python
# Check cache size
service.get_cache_size()

# Clear all cache (use sparingly!)
await service.clear_cache()

# Invalidate specific selector
await service.invalidate_cached_selector("Sign in", "https://example.com")
```

### ⚠️ Cache Management Rules

**DO:**
- Let the cache persist across runs
- Only invalidate when selectors stop working
- Monitor cache size for performance

**DON'T:**
- Delete cache files manually unless debugging
- Clear cache for model/config changes
- Remove working cached selectors

## Troubleshooting

### Common Issues

1. **AI returns explanatory text instead of selectors**
   - **Cause**: Weak AI model (e.g., `llama3.2:1b`)
   - **Solution**: Use stronger model like `llama3.2:latest` or `claude-3-haiku`

2. **Ambiguous selector errors**
   - **Cause**: Multiple elements match description
   - **Solution**: Use more specific descriptions or suggested options

3. **Cache misses for similar selectors**
   - **Cause**: Page URL changes or slight selector variations
   - **Solution**: Cache keys include URL, ensure consistent page URLs

4. **Slow AI responses**
   - **Cause**: Large HTML, complex pages, weak models
   - **Solution**: Use faster models, check network connectivity

### Debugging

```python
# Enable debug logging
import logging
logging.getLogger('lamia.engine.managers.web.selector_resolution').setLevel(logging.DEBUG)

# Check what's in cache
service.get_cache_size()

# Test selector classification
from lamia.engine.managers.web.selector_resolution.selector_parser import SelectorParser
parser = SelectorParser()
selector_type = parser.classify("your selector here")
```

## Mixing Traditional and AI Selectors

You can mix both types in the same automation:

```python
# Traditional CSS selector
web.click("button.submit")

# AI selector  
web.click("Sign in button")

# Traditional XPath
web.type("//input[@name='email']", "user@example.com")

# AI selector with context
web.type("Email input field", "user@example.com")
```

## Best Practices

### Writing Good AI Selectors

**Good Examples:**
```python
"Sign in button"           # Clear intent
"Search input field"       # Specific element type
"Close modal button"       # Context + action
"Primary submit button"    # Distinguishing attributes
```

**Avoid:**
```python
"button"                   # Too generic
"click here"              # Ambiguous action
"the thing"               # No clear target
"red button"              # Visual attributes may vary
```

### Performance Optimization

1. **Use cache-friendly selectors**: Consistent descriptions across runs
2. **Be specific**: Reduces ambiguity and AI processing time  
3. **Mix approaches**: Use CSS for stable elements, AI for dynamic content
4. **Monitor cache hit rate**: High cache hits = better performance

### Error Handling

```python
try:
    await web.click("Sign in button")
except ValueError as e:
    if "🚨 AMBIGUOUS SELECTOR:" in str(e):
        # Handle ambiguity - show options to user
        print("Multiple sign-in options found:")
        print(e)
    else:
        # Other resolution errors
        print(f"Selector resolution failed: {e}")
```

## Configuration

### AI Model Selection

In `config.yaml`:

```yaml
model_chain:
  - name: "ollama"
    default_model: llama3.2:latest  # Use stronger models
  - name: "anthropic:claude-3-haiku-20240307"  # Fallback
```

### Cache Settings

```python
# Disable caching (not recommended)
service = SelectorResolutionService(llm_manager, cache_enabled=False)

# Custom response parser
service = SelectorResolutionService(
    llm_manager, 
    response_parser=MyCustomParser()
)
```

## Testing

The system includes comprehensive tests that mock AI calls:

```bash
# Run selector resolution tests
pytest tests/engine/managers/web/selector_resolution/ -v

# No real AI calls are made during testing
```

## Migration from Legacy

If you have existing automations using the old AI selector system:

1. **No code changes needed**: API remains compatible
2. **Better caching**: Improved performance and reliability
3. **Ambiguity handling**: Better error messages and suggestions
4. **Validation**: Automatic selector validation prevents runtime errors

## Contributing

When extending the selector resolution system:

1. **Add tests**: All AI interactions must be mocked
2. **Update interfaces**: Use the `ResponseParser` interface for new formats
3. **Preserve cache**: Never delete cache in code unless explicitly requested
4. **Document changes**: Update this README for new features

## Support

For issues with selector resolution:

1. Check cache contents and size
2. Verify AI model configuration
3. Enable debug logging
4. Test with traditional selectors to isolate AI issues
5. Check page HTML structure and element availability
