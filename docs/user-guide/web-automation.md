# Web Automation

Lamia provides browser automation and HTTP client operations for web-based tasks. You can use traditional CSS/XPath selectors or natural language descriptions powered by AI.

## Web Actions

Use the `web` object in `.hu` files:

```python
# Navigation
web.navigate("https://example.com")

# Click, type, hover
web.click("#login-button")
web.type_text("#username", "user@example.com")
web.hover(".dropdown-menu")

# Get information
text = web.get_text(".result")
visible = web.is_visible(".modal")
enabled = web.is_enabled("button.submit")

# Wait and scroll
web.wait_for(".loading", "hidden")
web.scroll_to("#footer")

# Forms
web.select_option("#country", "US")
web.submit_form("#login-form")
web.upload_file("/path/to/resume.pdf", "input[type='file']")

# Screenshots
web.screenshot("page.png")
```

## Scoped Elements

Work within specific page elements:

```python
# Single element
modal = web.get_element("div.modal")
modal.click("button.close")
modal.type_text("input", "search term")

# Multiple elements
fields = web.get_elements("div.form-field")
for field in fields:
    label = field.get_text("label")
    input_type = field.get_input_type()
    
    if input_type == InputType.TEXT:
        field.type_text("input", "answer")
    elif input_type == InputType.CHECKBOX:
        if not field.is_checked("input"):
            field.click("input")

# Get selectable options (radio, checkbox, dropdown)
options = field.get_options()  # Returns: ["Option A", "Option B", "Option C"]
```

## AI-Powered Selectors

Instead of CSS/XPath, describe elements in natural language:

```python
# Natural language selectors
web.click("Sign in button")
web.type_text("Search input field", "lamia framework")
web.wait_for("Loading spinner", "hidden")
```

### How It Works

1. Lamia detects the selector is natural language (not CSS/XPath)
2. AI analyzes the page and returns the matching CSS selector

### Writing Good AI Selectors

```python
# Good — clear and specific
"Sign in button"
"Search input field"
"Close modal button"
"Primary submit button"

# Bad — too vague
"button"
"click here"
"the thing"
```

### Ambiguity Handling

When multiple elements match, Lamia shows options:

```
AMBIGUOUS SELECTOR: 'Sign in'
Multiple elements match. Please be more specific:

Option 1: "Sign in"          → button.btn-primary
Option 2: "Sign in with Google" → button.google-signin
Option 3: "Sign in with Apple"  → button.apple-signin
```

### Mixing Selector Types

Use both in the same script:

```python
web.click("button.submit")              # CSS selector
web.click("Sign in button")             # AI selector
web.type_text("//input[@name='email']", # XPath selector
              "user@example.com")
web.type_text("Email input field",      # AI selector
              "user@example.com")
```

## Configuration

In `config.yaml`:

```yaml
web_config:
  browser_engine: selenium        # selenium or playwright
  http_client: requests           # HTTP client library
  browser_options:
    headless: true                # Run without visible window
    timeout: 10.0                 # Default timeout in seconds
  http_options:
    timeout: 30.0                 # HTTP request timeout
    user_agent: "Lamia/1.0"      # User agent string
```

### Browser Engines

| Engine | Description |
|--------|-------------|
| `selenium` | Traditional WebDriver-based automation (default) |
| `playwright` | Modern, fast browser automation |

## Selector Cache

AI selector resolutions are cached to avoid repeated LLM calls:

```
.lamia_cache/selectors/selector_resolutions.json
```

```bash
# Clear cache if selectors stop working
rm -rf .lamia_cache/selectors/
```

## Troubleshooting

### AI returns wrong selector
- Use more specific descriptions
- Check if the page structure changed
- Clear the selector cache and retry

### Ambiguous selector errors
- Add distinguishing details: "Primary sign in button" instead of "Sign in"
- Use CSS selectors for elements that are easy to target

### Slow AI responses
- Use stronger/faster models in your model chain
- Cached selectors are instant on repeat runs