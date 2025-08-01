# Web Automation Module

The Lamia web automation module provides a unified interface for browser automation and HTTP client operations. It supports multiple browser engines and HTTP clients with intelligent adapter management and configuration.

## Features

- 🌐 **Multiple Browser Engines**: Selenium and Playwright support
- 🔄 **HTTP Client Support**: Requests library integration  
- 🧹 **Clean State Management**: Fresh adapters for each operation
- ⚙️ **Configurable Options**: Timeout, headless mode, user agents
- 🔄 **Retry Support**: Built-in retry logic for browser operations
- 📝 **Type Safety**: Full type annotations and validation

## Architecture

```
lamia/adapters/web/
├── browser/                    # Browser automation adapters
│   ├── base.py                # Abstract base class
│   ├── selenium_adapter.py    # Selenium WebDriver implementation
│   └── playwright_adapter.py  # Playwright implementation
├── http/                      # HTTP client adapters  
│   ├── base.py               # Abstract base class
│   └── http_adapter.py       # Requests library implementation
└── README.md                 # This file
```

## Configuration

Configure web automation through the `web_config` section in your `config.yaml`:

```yaml
# Web automation configuration
web_config:
  browser_engine: selenium           # Browser automation engine: selenium, playwright
  http_client: requests             # HTTP client library: requests
  browser_options:
    headless: true                  # Run browsers in headless mode
    timeout: 10.0                   # Default timeout in seconds for browser operations
  http_options:
    timeout: 30.0                   # Default timeout in seconds for HTTP requests
    user_agent: "Lamia/1.0"        # User agent string for HTTP requests
```

### Configuration Options

#### Browser Engines

| Engine | Description | Installation |
|--------|-------------|--------------|
| `selenium` | Traditional WebDriver-based automation (default) | `pip install selenium` |
| `playwright` | Modern, fast browser automation | `pip install playwright` |

#### HTTP Clients  

| Client | Description | Installation |
|--------|-------------|--------------|
| `requests` | Python requests library (default) | Built-in |

#### Browser Options

- **`headless`** (boolean): Run browsers without visible window (recommended for production)
- **`timeout`** (float): Default timeout for browser operations in seconds

#### HTTP Options

- **`timeout`** (float): Default timeout for HTTP requests in seconds
- **`user_agent`** (string): Custom user agent string for HTTP requests

## Adding New HTTP Clients

1. Create adapter class inheriting from `BaseHttpAdapter`  
2. Implement all abstract methods
3. Add to `SUPPORTED_HTTP_CLIENTS`
4. Update adapter creation logic

## Best Practices

1. **Use headless mode** in production for better performance
2. **Set appropriate timeouts** based on target website characteristics
3. **Use persistent sessions** only when necessary (login flows, etc.)
4. **Always clean up** adapters in finally blocks or context managers
5. **Configure user agents** appropriately for your use case
6. **Test with both engines** to find the best fit for your workflow 