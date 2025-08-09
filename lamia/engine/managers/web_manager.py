from lamia.engine.managers import Manager
from lamia.engine.config_provider import ConfigProvider
from lamia.validation.base import ValidationResult, BaseValidator, TrackingContext
from lamia.types import BrowserAction, HttpAction, BrowserActionType, HttpActionType, BrowserActionParams
from lamia.adapters.web.browser.base import BaseBrowserAdapter
from lamia.adapters.web.http.base import BaseHttpAdapter
from lamia.adapters.retry.factory import RetriableAdapterFactory
from lamia.interpreter.command_types import CommandType
from lamia.interpreter.commands import WebCommand, WebActionType
from lamia.adapters.web.browser.selenium_adapter import SeleniumAdapter
from lamia.adapters.web.browser.playwright_adapter import PlaywrightAdapter
from lamia.adapters.web.driver_scope_manager import get_scope_manager
from typing import Optional, Any
import logging
import inspect

logger = logging.getLogger(__name__)

# Configuration constants to avoid magic strings
class WebConfig:
    # Default providers
    DEFAULT_BROWSER_ENGINE = "selenium"
    DEFAULT_HTTP_CLIENT = "requests"
    
    # Config keys
    BROWSER_ENGINE_KEY = "browser_engine"  # instead of default_browser_adapter
    HTTP_CLIENT_KEY = "http_client"        # instead of default_http_adapter
    BROWSER_OPTIONS_KEY = "browser_options"
    HTTP_OPTIONS_KEY = "http_options"
    
    # Default values  
    DEFAULT_BROWSER_HEADLESS = False  # Changed from True to False for development
    DEFAULT_BROWSER_TIMEOUT = 10.0  # seconds
    DEFAULT_HTTP_TIMEOUT = 30.0     # seconds
    DEFAULT_USER_AGENT = "Lamia/1.0"


class WebManager(Manager[WebCommand]):
    """Manages web adapters with retry support and routes actions to browser or HTTP adapter families."""
    
    def __init__(self, config_provider: ConfigProvider):
        self.config_provider = config_provider
        # Changed: No more caching adapters - create fresh ones for each URL
        self._web_adapter = None  # For backward compatibility - will be initialized on first use
        
        # Get configured defaults or use constants
        web_config = config_provider.get_web_config()
        
        self._browser_engine = web_config.get(
            WebConfig.BROWSER_ENGINE_KEY, 
            WebConfig.DEFAULT_BROWSER_ENGINE
        )
        self._http_client = web_config.get(
            WebConfig.HTTP_CLIENT_KEY, 
            WebConfig.DEFAULT_HTTP_CLIENT
        )
        self._browser_options = web_config.get(WebConfig.BROWSER_OPTIONS_KEY, {})
        self._http_options = web_config.get(WebConfig.HTTP_OPTIONS_KEY, {})
        
    
    async def execute(self, command: WebCommand, validator: Optional[BaseValidator] = None) -> ValidationResult:
        """Simple web content fetching for backward compatibility."""
        from lamia.types import HttpActionParams

        command_type = command.command_type
        web_content = ""
        
        if command_type == CommandType.WEB:            
            # Handle different web action types
            if command.action == WebActionType.NAVIGATE:
                # Navigation action
                action = BrowserAction(
                    action=BrowserActionType.NAVIGATE,
                    params=BrowserActionParams(value=command.url)
                )
            elif command.action == WebActionType.CLICK:
                # Click action
                action = BrowserAction(
                    action=BrowserActionType.CLICK,
                    params=BrowserActionParams(
                        selector=command.selector,
                        timeout=command.timeout
                    )
                )
            elif command.action == WebActionType.TYPE:
                # Type action
                action = BrowserAction(
                    action=BrowserActionType.TYPE,
                    params=BrowserActionParams(
                        selector=command.selector,
                        value=command.value,
                        timeout=command.timeout
                    )
                )
            elif command.action == WebActionType.WAIT:
                # Wait action
                action = BrowserAction(
                    action=BrowserActionType.WAIT,
                    params=BrowserActionParams(
                        selector=command.selector,
                        timeout=command.timeout
                    )
                )
            elif command.action == WebActionType.GET_TEXT:
                # Get text action
                action = BrowserAction(
                    action=BrowserActionType.GET_TEXT,
                    params=BrowserActionParams(
                        selector=command.selector,
                        timeout=command.timeout
                    )
                )
            elif command.action == WebActionType.HOVER:
                # Hover action
                action = BrowserAction(
                    action=BrowserActionType.HOVER,
                    params=BrowserActionParams(
                        selector=command.selector,
                        timeout=command.timeout
                    )
                )
            elif command.action == WebActionType.SCROLL:
                # Scroll action
                action = BrowserAction(
                    action=BrowserActionType.SCROLL,
                    params=BrowserActionParams(
                        selector=command.selector
                    )
                )
            elif command.action == WebActionType.SELECT:
                # Select action
                action = BrowserAction(
                    action=BrowserActionType.SELECT,
                    params=BrowserActionParams(
                        selector=command.selector,
                        value=command.value,
                        timeout=command.timeout
                    )
                )
            elif command.action == WebActionType.SUBMIT:
                # Submit action
                action = BrowserAction(
                    action=BrowserActionType.SUBMIT,
                    params=BrowserActionParams(
                        selector=command.selector,
                        timeout=command.timeout
                    )
                )
            elif command.action == WebActionType.SCREENSHOT:
                # Screenshot action
                action = BrowserAction(
                    action=BrowserActionType.SCREENSHOT,
                    params=BrowserActionParams(
                        value=command.value
                    )
                )
            elif command.action == WebActionType.IS_VISIBLE:
                # Is visible action
                action = BrowserAction(
                    action=BrowserActionType.IS_VISIBLE,
                    params=BrowserActionParams(
                        selector=command.selector,
                        timeout=command.timeout
                    )
                )
            elif command.action == WebActionType.IS_ENABLED:
                # Is enabled action
                action = BrowserAction(
                    action=BrowserActionType.IS_ENABLED,
                    params=BrowserActionParams(
                        selector=command.selector,
                        timeout=command.timeout
                    )
                )
            else:
                raise ValueError(f"Unsupported web action: {command.action}")
            
            # Execute browser action using scope-managed driver
            await self.execute_browser_action(action)
            
        elif command_type == CommandType.HTTP:
            adapter = await self._create_http_adapter(self._http_client)
            # Assuming command has proper HTTP action params
            web_content = await self.execute_http_action(command, adapter)
            await adapter.close()
        else:
            raise ValueError(f"Unsupported command type: {command_type}")
        
        execution_context = TrackingContext(
            data_provider_name="web_automation",
            command_type=command_type,
            metadata={"url": command.url}
        )
        
        if validator:
            return await validator.validate(web_content, execution_context=execution_context)
        else:
            return ValidationResult(
                is_valid=True,
                raw_text=str(web_content),
                validated_text=str(web_content),
                execution_context=execution_context
            )
    
    async def _create_adapter_from_config(self, config_provider: ConfigProvider):
        """Create a simple HTTP adapter for backward compatibility."""
        # For backward compatibility, create a simple requests adapter
        from lamia.adapters.web.http.http_adapter import RequestsAdapter
        timeout = self._http_options.get('timeout', WebConfig.DEFAULT_HTTP_TIMEOUT)
        user_agent = self._http_options.get('user_agent', WebConfig.DEFAULT_USER_AGENT)
        adapter = RequestsAdapter(timeout=timeout, user_agent=user_agent)
        await adapter.initialize()
        return adapter
    
    async def execute_browser_action(self, action: BrowserAction, adapter: Optional[BaseBrowserAdapter] = None) -> Any:
        """Execute a browser action using scope-managed driver or provided adapter."""
        
        # Use provided adapter or get scope-managed driver
        if adapter is None:
            adapter = await self._get_scoped_driver()
        
        logger.info(f"Executing {action.action} browser action using {adapter.__class__.__name__} adapter")
        
        # Route to appropriate browser adapter method - errors will bubble up for retry handling
        if action.action == BrowserActionType.NAVIGATE:
            return await adapter.navigate(action.params)
        elif action.action == BrowserActionType.CLICK:
            print("Clicking")
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
    
    async def execute_http_action(self, action: HttpAction, adapter: BaseHttpAdapter) -> Any:
        """Execute an HTTP action using the specified or default HTTP adapter with retry support."""
        
        logger.info(f"Executing {action.action} HTTP action using {adapter.__class__.__name__} adapter")
        
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
    
    async def _create_browser_adapter(self, engine_name: str) -> BaseBrowserAdapter:
        """Create a fresh browser adapter instance with retry wrapper for each URL."""
        
        # Get browser options from config
        headless = self._browser_options.get('headless', WebConfig.DEFAULT_BROWSER_HEADLESS)
        timeout = self._browser_options.get('timeout', WebConfig.DEFAULT_BROWSER_TIMEOUT)
        
        logger.info(f"Creating browser adapter with headless={headless}, timeout={timeout}")
        
        # Create raw adapter with config options
        if engine_name == "selenium":
            raw_adapter = SeleniumAdapter(headless=headless, timeout=timeout)
        elif engine_name == "playwright":
            # Convert seconds to milliseconds for Playwright
            playwright_timeout = timeout * 1000
            raw_adapter = PlaywrightAdapter(headless=headless, timeout=playwright_timeout)
        else:
            raise ValueError(f"Unsupported browser engine: {engine_name}")
        
        # Initialize raw adapter
        await raw_adapter.initialize()
        
        # Wrap with retry capabilities
        retry_config = self.config_provider.get_retry_config()
        adapter_with_retries = RetriableAdapterFactory.create_browser_adapter(raw_adapter, retry_config)
        
        return adapter_with_retries
    
    async def _create_http_adapter(self, client_name: str) -> BaseHttpAdapter:
        """Create a fresh HTTP adapter instance for each request."""
        
        # Get HTTP options from config
        timeout = self._http_options.get('timeout', WebConfig.DEFAULT_HTTP_TIMEOUT)
        user_agent = self._http_options.get('user_agent', WebConfig.DEFAULT_USER_AGENT)
        
        # Create raw adapter with config options  
        if client_name == "requests":
            from lamia.adapters.web.http.http_adapter import RequestsAdapter
            raw_adapter = RequestsAdapter(timeout=timeout, user_agent=user_agent)
        else:
            raise ValueError(f"Unsupported HTTP client: {client_name}")
        
        # Initialize raw adapter
        await raw_adapter.initialize()
        
        # Note: HTTP adapters don't have retry wrapper yet, but could be added
        return raw_adapter
    
    async def _get_scoped_driver(self) -> BaseBrowserAdapter:
        """Get browser driver based on current execution scope."""
        scope_manager = get_scope_manager()
        
        # Determine scope based on call stack
        scope_type, scope_id = self._detect_execution_scope()
        
        # Create adapter factory for this configuration
        async def adapter_factory():
            return await self._create_browser_adapter(self._browser_engine)
        
        return await scope_manager.get_driver(scope_type, scope_id, adapter_factory)
    
    def _detect_execution_scope(self) -> tuple[str, Optional[str]]:
        """Detect current execution scope from call stack."""
        frame = inspect.currentframe()
        try:
            hu_functions = []
            module_level_hu = False
            
            # Walk up the call stack to find .hu file execution context
            while frame:
                frame = frame.f_back
                if not frame:
                    break
                    
                filename = frame.f_code.co_filename
                if filename.endswith('.hu'):
                    function_name = frame.f_code.co_name
                    
                    if function_name == '<module>':
                        # Module level .hu execution
                        module_level_hu = True
                    else:
                        # Function level .hu execution
                        hu_functions.append(function_name)
            
            # Determine scope based on .hu file execution context
            if module_level_hu and not hu_functions:
                # Direct module-level execution (no functions involved)
                return ('global', None)
            elif hu_functions:
                # Function-based execution - use the outermost .hu function as scope
                # This ensures all nested function calls share the same driver
                outermost_function = hu_functions[-1]  # Last in list = outermost in stack
                scope_id = f"hu_function.{outermost_function}"
                return ('function', scope_id)
            else:
                # No .hu context found, default to global
                return ('global', None)
                
        finally:
            del frame
    
    async def create_browser_session(self, engine_name: Optional[str] = None) -> BaseBrowserAdapter:
        """Create a new browser session for interactive automation.
        
        This method allows users to create and manage their own browser sessions
        for complex automation workflows that require persistent state.
        """
        engine = engine_name or self._browser_engine
        return await self._create_browser_adapter(engine)
    
    async def create_http_session(self, client_name: Optional[str] = None) -> BaseHttpAdapter:
        """Create a new HTTP session for multiple requests.
        
        This method allows users to create and manage their own HTTP sessions
        for workflows that benefit from connection reuse.
        """
        client = client_name or self._http_client
        return await self._create_http_adapter(client)
    
    async def close(self):
        """Close and cleanup any remaining resources."""
        # Cleanup scope-managed drivers
        scope_manager = get_scope_manager()
        await scope_manager.cleanup_all()
        
        # Backward compatibility cleanup
        if self._web_adapter:
            await self._web_adapter.close()
            self._web_adapter = None