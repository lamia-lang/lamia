"""Browser automation manager with AI-powered selector resolution."""

from lamia.engine.managers import Manager
from lamia.engine.config_provider import ConfigProvider
from lamia.validation.base import ValidationResult, BaseValidator
from lamia.types import BrowserAction, BrowserActionType, BrowserActionParams
from lamia.adapters.web.browser.base import BaseBrowserAdapter
from lamia.adapters.retry.factory import RetriableAdapterFactory
from lamia.interpreter.commands import WebCommand, WebActionType
from lamia.adapters.web.browser.selenium_adapter import SeleniumAdapter
from lamia.adapters.web.browser.playwright_adapter import PlaywrightAdapter
from lamia.adapters.web.driver_scope_manager import get_scope_manager
from .selector_resolution.selector_resolution_service import SelectorResolutionService
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages browser automation with AI-powered selector resolution."""
    
    def __init__(self, config_provider: ConfigProvider):
        """Initialize browser manager.
        
        Args:
            config_provider: Configuration provider
        """
        self.config_provider = config_provider
        
        # Get browser configuration
        web_config = config_provider.get_web_config()
        self._browser_engine = web_config.get("browser_engine", "selenium")
        self._browser_options = web_config.get("browser_options", {})
        
        # Set defaults
        self._browser_options.setdefault("headless", False)
        self._browser_options.setdefault("timeout", 10.0)
        
        # Initialize selector resolution service when we have a browser adapter
        self._selector_resolution_service = None
        self._browser_adapter = None
    
    async def execute(self, command: WebCommand, validator: Optional[BaseValidator] = None) -> Any:
        """Execute browser command with AI selector resolution.
        
        Args:
            command: Web command containing browser action
            validator: Optional validator for response
            
        Returns:
            Result of browser action
        """
        # Selector resolution service will be created lazily when needed
        
        # Convert WebCommand to BrowserAction
        browser_action = self._web_command_to_browser_action(command)
        
        # Resolve selectors using AI if needed
        if self._has_selector(browser_action):
            browser_action = await self._resolve_selectors(browser_action)
        
        # Execute browser action
        return await self._execute_browser_action(browser_action)
    
    def _web_command_to_browser_action(self, command: WebCommand) -> BrowserAction:
        """Convert WebCommand to BrowserAction."""
        action_type_mapping = {
            WebActionType.NAVIGATE: BrowserActionType.NAVIGATE,
            WebActionType.CLICK: BrowserActionType.CLICK,
            WebActionType.TYPE: BrowserActionType.TYPE,
            WebActionType.WAIT: BrowserActionType.WAIT,
            WebActionType.GET_TEXT: BrowserActionType.GET_TEXT,
            WebActionType.SCREENSHOT: BrowserActionType.SCREENSHOT,
            WebActionType.HOVER: BrowserActionType.HOVER,
            WebActionType.SCROLL: BrowserActionType.SCROLL,
            WebActionType.SELECT: BrowserActionType.SELECT,
            WebActionType.SUBMIT: BrowserActionType.SUBMIT,
            WebActionType.IS_VISIBLE: BrowserActionType.IS_VISIBLE,
            WebActionType.IS_ENABLED: BrowserActionType.IS_ENABLED,
        }
        
        browser_action_type = action_type_mapping.get(command.action)
        if not browser_action_type:
            raise ValueError(f"Unsupported web action: {command.action}")
        
        # Create BrowserActionParams - get value from command.url for navigation, command.value for input
        if browser_action_type == BrowserActionType.NAVIGATE:
            params = BrowserActionParams(value=command.url)
        else:
            params = BrowserActionParams(
                selector=command.selector,
                value=command.value
            )
        
        return BrowserAction(
            action=browser_action_type,
            params=params
        )
    
    def _has_selector(self, action: BrowserAction) -> bool:
        """Check if action requires a selector."""
        return action.params.selector is not None
    
    async def _resolve_selectors(self, action: BrowserAction) -> BrowserAction:
        """Resolve selectors using AI service."""
        try:
            # Check if selector needs AI resolution
            from .selector_resolution.selector_parser import SelectorParser, SelectorType
            parser = SelectorParser()
            selector_type = parser.classify(action.params.selector)
            
            # Only resolve if it's natural language
            if selector_type != SelectorType.NATURAL_LANGUAGE:
                return action
                
            # Create LLM manager and selector resolution service lazily
            if not self._selector_resolution_service:
                logger.info("BrowserManager: Creating LLM manager and selector resolution service for natural language selector")
                from ..llm.llm_manager import LLMManager
                llm_manager = LLMManager(self.config_provider)
                self._selector_resolution_service = SelectorResolutionService(
                    llm_manager,
                    get_page_html_func=self._get_current_page_html,
                    cache_enabled=True
                )
            
            # Get current page URL from driver scope manager
            scope_manager = get_scope_manager()
            page_url = getattr(scope_manager, 'current_url', 'unknown')
            
            # Resolve main selector
            resolved_selector = await self._selector_resolution_service.resolve_selector(
                selector=action.params.selector,
                page_url=page_url
            )
            
            # Create new action with resolved selector
            new_params = BrowserActionParams(
                selector=resolved_selector,
                value=action.params.value
            )
            
            return BrowserAction(
                action=action.action,
                params=new_params
            )
        except Exception as e:
            logger.warning(f"Selector resolution failed: {e}")
            return action  # Return original action if resolution fails
    
    async def _execute_browser_action(self, action: BrowserAction) -> Any:
        """Execute browser action using appropriate adapter."""
        # Get browser adapter (this will create it if needed)
        adapter = await self._get_browser_adapter()
        
        
        # Execute action using adapter
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
        elif action.action == BrowserActionType.SCREENSHOT:
            return await adapter.take_screenshot(action.params)
        elif action.action == BrowserActionType.HOVER:
            return await adapter.hover(action.params)
        elif action.action == BrowserActionType.SCROLL:
            return await adapter.scroll(action.params)
        elif action.action == BrowserActionType.SELECT:
            return await adapter.select_option(action.params)
        elif action.action == BrowserActionType.SUBMIT:
            return await adapter.submit_form(action.params)
        elif action.action == BrowserActionType.IS_VISIBLE:
            return await adapter.is_visible(action.params)
        elif action.action == BrowserActionType.IS_ENABLED:
            return await adapter.is_enabled(action.params)
        else:
            raise ValueError(f"Unsupported browser action: {action.action}")
    
    async def _get_browser_adapter(self) -> BaseBrowserAdapter:
        """Get browser adapter with retry capabilities (cached)."""
        if self._browser_adapter is None:
            # Create base adapter
            if self._browser_engine == "selenium":
                base_adapter = SeleniumAdapter(
                    headless=self._browser_options.get("headless", False),
                    timeout=self._browser_options.get("timeout", 10.0)
                )
            elif self._browser_engine == "playwright":
                base_adapter = PlaywrightAdapter(
                    headless=self._browser_options.get("headless", False),
                    timeout=self._browser_options.get("timeout", 10.0)
                )
            else:
                raise ValueError(f"Unsupported browser engine: {self._browser_engine}")
            
            # Initialize adapter
            await base_adapter.initialize()
            
            # Wrap with retry capabilities
            self._browser_adapter = RetriableAdapterFactory.create_browser_adapter(base_adapter)
        
        return self._browser_adapter
    
    async def _get_current_page_html(self) -> str:
        """Get current page HTML source."""
        adapter = await self._get_browser_adapter()
        return await adapter.get_page_source()
    
    async def close(self):
        """Close browser manager and cleanup resources."""
        # Close browser adapter if it exists
        if self._browser_adapter:
            await self._browser_adapter.close()
            self._browser_adapter = None
        
        # Clear selector resolution cache if available
        if self._selector_resolution_service:
            await self._selector_resolution_service.clear_cache()
        
        logger.info("BrowserManager closed")