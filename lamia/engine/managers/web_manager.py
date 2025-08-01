from lamia.engine.managers import Manager
from lamia.engine.config_provider import ConfigProvider
from lamia.validation.base import ValidationResult, BaseValidator, TrackingContext
from lamia.types import BrowserAction, HttpAction, BrowserActionType, HttpActionType, BrowserActionParams
from lamia.adapters.web.browser.base import BaseBrowserAdapter
from lamia.adapters.web.http.base import BaseHttpAdapter
from lamia.adapters.retry.factory import RetriableAdapterFactory
from lamia.interpreter.command_types import CommandType
from lamia.interpreter.command_types import WebCommand
from lamia.adapters.web.browser.selenium_adapter import SeleniumAdapter
from lamia.adapters.web.browser.playwright_adapter import PlaywrightAdapter
from typing import Optional, Dict, Any
import requests
import logging

logger = logging.getLogger(__name__)

# Constants for default adapters
DEFAULT_BROWSER_ADAPTER = "selenium"
DEFAULT_HTTP_ADAPTER = "requests"


class WebManager(Manager):
    """Manages web adapters with retry support and routes actions to browser or HTTP adapter families."""
    
    def __init__(self, config_provider: ConfigProvider):
        self.config_provider = config_provider
        self._browser_adapters: Dict[str, BaseBrowserAdapter] = {}
        self._http_adapters: Dict[str, BaseHttpAdapter] = {}
        self._web_adapter = None  # For backward compatibility - will be initialized on first use
        
        # Get configured defaults or use constants
        web_config = config_provider.get_web_config()
        self._default_browser_adapter = web_config.get('default_browser_adapter', DEFAULT_BROWSER_ADAPTER)
        self._default_http_adapter = web_config.get('default_http_adapter', DEFAULT_HTTP_ADAPTER)
        self._browser_options = web_config.get('browser_options', {})
        self._http_options = web_config.get('http_options', {})
    
    async def execute(self, command: WebCommand, validator: Optional[BaseValidator] = None) -> ValidationResult:
        """Simple web content fetching for backward compatibility."""

        command_type = command.command_type
        if command_type == CommandType.WEB:            
            # Create navigation action
            action = BrowserAction(
                action=BrowserActionType.NAVIGATE,
                params=BrowserActionParams(value=command.url)
            )
            
            # Execute navigation
            adapter = await self._get_browser_adapter(self._default_browser_adapter)
            await self.execute_browser_action(action, adapter)
            web_content = self._web_adapter.get(command.url)
        elif command_type == CommandType.HTTP:
            adapter = await self._get_http_adapter(self._default_http_adapter)
            await self.execute_http_action(command, adapter)
        else:
            raise ValueError(f"Unsupported command type: {command_type}")
        
        execution_context = TrackingContext(
            data_provider_name="http_requests",
            command_type=CommandType.WEB,
            metadata={"url": command.url}
        )
        
        if validator:
            return await validator.validate(web_content, execution_context=execution_context)
        else:
            return ValidationResult(
                is_valid=True,
                raw_text=web_content,
                validated_text=web_content,
                execution_context=execution_context
            )
    
    async def _create_adapter_from_config(self, config_provider: ConfigProvider):
        """Create a simple HTTP adapter for backward compatibility."""
        # For backward compatibility, create a simple requests adapter
        from lamia.adapters.web.http.http_adapter import RequestsAdapter
        timeout = self._http_options.get('timeout', 30.0)
        user_agent = self._http_options.get('user_agent', 'Lamia/1.0')
        adapter = RequestsAdapter(timeout=timeout, user_agent=user_agent)
        await adapter.initialize()
        return adapter
    
    async def execute_browser_action(self, action: BrowserAction, adapter: BaseBrowserAdapter) -> Any:
        """Execute a browser action using the specified or default browser adapter with retry support."""
        
        logger.info(f"Executing {action.action} browser action using {adapter.__class__.__name__} adapter")
        
        # Route to appropriate browser adapter method - errors will bubble up for retry handling
        if action.action == BrowserActionType.NAVIGATE:
            return await adapter.navigate(action.params)
        elif action.action == BrowserActionType.CLICK:
            return await adapter.click(action.params)
        elif action.action == BrowserActionType.TYPE:
            return await adapter.type_text(action.params)
        elif action.action == BrowserActionType.WAIT:
            return await adapter.wait_for_element(action.params)
        elif action.action == BrowserActionType.GET_TEXT:
            return await adapter.get_text(action.params)
        elif action.action == BrowserActionType.GET_ATTRIBUTE:
            return await adapter.get_attribute(action.params)
        elif action.action == BrowserActionType.IS_VISIBLE:
            return await adapter.is_visible(action.params)
        elif action.action == BrowserActionType.IS_ENABLED:
            return await adapter.is_enabled(action.params)
        elif action.action == BrowserActionType.HOVER:
            return await adapter.hover(action.params)
        elif action.action == BrowserActionType.SCROLL:
            return await adapter.scroll(action.params)
        elif action.action == BrowserActionType.SELECT:
            return await adapter.select_option(action.params)
        elif action.action == BrowserActionType.SUBMIT:
            return await adapter.submit_form(action.params)
        elif action.action == BrowserActionType.SCREENSHOT:
            return await adapter.take_screenshot(action.params)
        else:
            raise ValueError(f"Unsupported browser action type: {action.action}")
    
    async def execute_http_action(self, action: HttpAction, adapter_name: Optional[str] = None) -> Any:
        """Execute an HTTP action using the specified or default HTTP adapter with retry support."""
        adapter_name = adapter_name or self._default_http_adapter
        adapter = await self._get_http_adapter(adapter_name)
        
        logger.info(f"Executing {action.action} HTTP action using {adapter_name} adapter")
        
        # Route to appropriate HTTP adapter method - errors will bubble up for retry handling
        if action.action == HttpActionType.GET:
            return await adapter.get(action.params)
        elif action.action == HttpActionType.POST:
            return await adapter.post(action.params)
        elif action.action == HttpActionType.PUT:
            return await adapter.put(action.params)
        elif action.action == HttpActionType.PATCH:
            return await adapter.patch(action.params)
        elif action.action == HttpActionType.DELETE:
            return await adapter.delete(action.params)
        elif action.action == HttpActionType.HEAD:
            return await adapter.head(action.params)
        elif action.action == HttpActionType.OPTIONS:
            return await adapter.options(action.params)
        else:
            raise ValueError(f"Unsupported HTTP action type: {action.action}")
    
    async def _get_browser_adapter(self, adapter_name: str) -> BaseBrowserAdapter:
        """Get or create a browser adapter instance with retry wrapper."""
        if adapter_name in self._browser_adapters:
            return self._browser_adapters[adapter_name]
        
        # Get browser options from config
        headless = self._browser_options.get('headless', True)
        timeout = self._browser_options.get('timeout', 10.0)
        
        # Create raw adapter with config options
        if adapter_name == "selenium":
            raw_adapter = SeleniumAdapter(headless=headless, timeout=timeout)
        elif adapter_name == "playwright":
            # Convert seconds to milliseconds for Playwright
            playwright_timeout = timeout * 1000
            raw_adapter = PlaywrightAdapter(headless=headless, timeout=playwright_timeout)
        else:
            raise ValueError(f"Unsupported browser adapter: {adapter_name}")
        
        # Initialize raw adapter
        await raw_adapter.initialize()
        
        # Wrap with retry capabilities
        retry_config = self.config_provider.get_retry_config()
        adapter_with_retries = RetriableAdapterFactory.create_browser_adapter(raw_adapter, retry_config)
        
        # Cache for reuse
        self._browser_adapters[adapter_name] = adapter_with_retries
        return adapter_with_retries
    
    async def _get_http_adapter(self, adapter_name: str) -> BaseHttpAdapter:
        """Get or create an HTTP adapter instance with retry wrapper."""
        if adapter_name in self._http_adapters:
            return self._http_adapters[adapter_name]
        
        # Get HTTP options from config
        timeout = self._http_options.get('timeout', 30.0)
        user_agent = self._http_options.get('user_agent', 'Lamia/1.0')
        
        # Create raw adapter with config options  
        if adapter_name == "requests":
            from lamia.adapters.web.http.http_adapter import RequestsAdapter
            raw_adapter = RequestsAdapter(timeout=timeout, user_agent=user_agent)
        else:
            raise ValueError(f"Unsupported HTTP adapter: {adapter_name}")
        
        # Initialize raw adapter
        await raw_adapter.initialize()
        
        # Note: HTTP adapters don't have retry wrapper yet, but could be added
        # For now, just cache the raw adapter
        self._http_adapters[adapter_name] = raw_adapter
        return raw_adapter
    
    async def close(self):
        """Close and cleanup all managed adapters."""
        for adapter in self._browser_adapters.values():
            await adapter.close()
        for adapter in self._http_adapters.values():
            await adapter.close()
        self._browser_adapters.clear()
        self._http_adapters.clear()