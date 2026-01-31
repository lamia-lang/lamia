"""Browser automation manager with AI-powered selector resolution."""

from lamia.engine.managers import Manager
from lamia.engine.config_provider import ConfigProvider
from lamia.validation.base import ValidationResult, BaseValidator
from lamia.internal_types import BrowserAction, BrowserActionType, BrowserActionParams
from lamia.adapters.web.browser.base import BaseBrowserAdapter
from lamia.adapters.retry.factory import RetriableAdapterFactory
from lamia.interpreter.commands import WebCommand, WebActionType
from lamia.adapters.web.browser.selenium_adapter import SeleniumAdapter
from lamia.adapters.web.browser.playwright_adapter import PlaywrightAdapter
from lamia.adapters.web.driver_scope_manager import get_scope_manager
from .selector_resolution.selector_resolution_service import SelectorResolutionService
from .selector_resolution.suggestions import SelectorSuggestionService
from lamia.errors import ExternalOperationPermanentError, ExternalOperationTransientError
from .selector_resolution.all_selectors_failed_handler import AllSelectorsFailedHandler
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages browser automation with AI-powered selector resolution."""
    
    def __init__(self, config_provider: ConfigProvider, web_manager: Optional[Any] = None):
        """Initialize browser manager.
        
        Args:
            config_provider: Configuration provider
            web_manager: Optional web manager reference for WebActions execution
        """
        self.config_provider = config_provider
        self.web_manager = web_manager
        
        # Get browser configuration
        web_config = config_provider.get_web_config()
        self._browser_engine = web_config.get("browser_engine", "selenium")
        self._browser_options = web_config.get("browser_options", {})
        
        # Set defaults
        self._browser_options.setdefault("headless", False)
        self._browser_options.setdefault("timeout", 10.0)
        
        # Active session profile name (hint from session blocks)
        self._active_profile: Optional[str] = None
        # Initialize selector resolution and suggestion services when we have a browser adapter
        self._selector_resolution_service = None
        self._selector_suggestion_service = None
        self._browser_adapter = None

        self.all_selectors_failed_handler = None
    
    async def execute(self, command: WebCommand, validator: Optional[BaseValidator] = None) -> Any:
        """Execute browser command with AI selector resolution.
        
        Args:
            command: Web command containing browser action
            validator: Optional validator for response
            
        Returns:
            Result of browser action
        """
        # If a session profile is active and adapter not yet created, ensure
        # profile state is loaded before first browser command executes.
        if self._active_profile and self._browser_adapter is None:
            try:
                await self.load_session_cookies(self._active_profile)
            except Exception:
                pass
        # Selector resolution service will be created lazily when needed
        
        # Store original action type for GET_ELEMENT vs GET_ELEMENTS distinction
        original_action_type = command.action
        
        # Convert WebCommand to BrowserAction
        browser_action = self._web_command_to_browser_action(command)
        
        # Resolve selectors using AI if needed
        if self._has_selector(browser_action):
            browser_action = await self._resolve_selectors(browser_action)
        
        # Execute browser action
        result = await self._execute_browser_action(browser_action, original_action_type=original_action_type)

        # If validation is expected but the action returned no content,
        # provide the current page HTML so the validator has something to check.
        if validator is not None and result is None:
            try:
                result = await self.get_page_source()
            except Exception as e:
                logger.warning(f"Failed to fetch page source for validation: {e}")
                result = None

        return result
    
        
    
    def _web_command_to_browser_action(self, command: WebCommand) -> BrowserAction:
        """Convert WebCommand to BrowserAction."""
        action_type_mapping = {
            WebActionType.NAVIGATE: BrowserActionType.NAVIGATE,
            WebActionType.CLICK: BrowserActionType.CLICK,
            WebActionType.TYPE: BrowserActionType.TYPE,
            WebActionType.WAIT: BrowserActionType.WAIT,
            WebActionType.GET_TEXT: BrowserActionType.GET_TEXT,
            WebActionType.GET_PAGE_SOURCE: BrowserActionType.GET_PAGE_SOURCE,
            WebActionType.GET_ELEMENT: BrowserActionType.GET_ELEMENTS,  # Use same adapter method
            WebActionType.GET_ELEMENTS: BrowserActionType.GET_ELEMENTS,
            WebActionType.GET_INPUT_TYPE: BrowserActionType.GET_INPUT_TYPE,
            WebActionType.GET_OPTIONS: BrowserActionType.GET_OPTIONS,
            WebActionType.GET_ATTRIBUTE: BrowserActionType.GET_ATTRIBUTE,
            WebActionType.SCREENSHOT: BrowserActionType.SCREENSHOT,
            WebActionType.HOVER: BrowserActionType.HOVER,
            WebActionType.SCROLL: BrowserActionType.SCROLL,
            WebActionType.SELECT: BrowserActionType.SELECT,
            WebActionType.SUBMIT: BrowserActionType.SUBMIT,
            WebActionType.IS_VISIBLE: BrowserActionType.IS_VISIBLE,
            WebActionType.IS_ENABLED: BrowserActionType.IS_ENABLED,
            WebActionType.IS_CHECKED: BrowserActionType.IS_CHECKED,
            WebActionType.UPLOAD_FILE: BrowserActionType.UPLOAD_FILE,
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
                fallback_selectors=command.fallback_selectors,
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
        """Resolve selectors using AI service.
        
        Args:
            action: Browser action with selector to resolve
        """
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
                    config_provider=self.config_provider,
                    get_page_html_func=self._get_current_page_html,
                    get_browser_adapter_func=self._get_browser_adapter,
                )
            
            # Get current page URL from driver scope manager
            scope_manager = get_scope_manager()
            page_url = getattr(scope_manager, 'current_url', 'unknown')

            # Extract parent context from scope element handle
            parent_context = None
            if action.params.scope_element_handle:
                try:
                    # Get the tag name of the parent element for context
                    parent_tag = action.params.scope_element_handle.tag_name
                    if parent_tag:
                        parent_context = parent_tag.lower()
                        logger.info(f"DEBUG: Extracted parent context: {parent_context} for selector: {action.params.selector}")
                    else:
                        logger.info(f"DEBUG: Parent element has no tag name for selector: {action.params.selector}")
                except Exception as e:
                    logger.info(f"DEBUG: Failed to extract parent context for selector: {action.params.selector}, error: {e}")
            else:
                logger.info(f"DEBUG: No scope_element_handle for selector: {action.params.selector}")

            # Resolve main selector with operation context and parent scope
            resolved_selector = await self._selector_resolution_service.resolve_selector(
                selector=action.params.selector,
                page_url=page_url,
                operation_type=action.action,
                parent_context=parent_context
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
            # Check if this is an ambiguity error that should halt execution
            if "🚨 AMBIGUOUS SELECTOR:" in str(e):
                logger.warning(f"Selector resolution failed: {e}")
                # For ambiguity errors, we should NOT fall back to the original selector
                # Re-raise the error to halt execution and show the helpful message
                raise e
            else:
                logger.warning(f"Selector resolution failed: {e}")
                return action  # Return original action if resolution fails for other reasons
    
    # Define which actions use selectors and need fallback
    SELECTOR_BASED_ACTIONS = {
        BrowserActionType.CLICK,
        BrowserActionType.TYPE,
        BrowserActionType.WAIT,
        BrowserActionType.GET_TEXT,
        BrowserActionType.GET_ELEMENTS,
        BrowserActionType.GET_INPUT_TYPE,
        BrowserActionType.GET_OPTIONS,
        BrowserActionType.GET_ATTRIBUTE,
        BrowserActionType.HOVER,
        BrowserActionType.SELECT,
        BrowserActionType.IS_VISIBLE,
        BrowserActionType.IS_ENABLED,
        BrowserActionType.IS_CHECKED,
        BrowserActionType.UPLOAD_FILE,
    }

    async def _execute_browser_action(self, action: BrowserAction, original_action_type: Optional[WebActionType] = None) -> Any:
        """Execute browser action with optional selector chain fallback.
        
        Args:
            action: Browser action to execute
            original_action_type: Original WebActionType (to distinguish GET_ELEMENT vs GET_ELEMENTS)
        """
        adapter = await self._get_browser_adapter()
        
        # Check if this action uses selectors
        if action.action in self.SELECTOR_BASED_ACTIONS and action.params.fallback_selectors:
            # Use selector chain logic
            return await self._execute_with_selector_chain(action, adapter, original_action_type)
        else:
            # Direct execution (no selector chain needed)
            return await self._execute_single_action(action, adapter, original_action_type)

    async def _execute_with_selector_chain(self, action: BrowserAction, adapter: BaseBrowserAdapter, original_action_type: Optional[WebActionType] = None) -> Any:
        """Execute action with selector chain fallback."""
        params = action.params
        selectors = [params.selector] + (params.fallback_selectors or [])
        
        for i, selector in enumerate(selectors):
            try:
                # Create params with single selector
                single_params = BrowserActionParams(
                    selector=selector,
                    value=params.value,
                    timeout=params.timeout,
                    # ... copy other params
                    fallback_selectors=None  # Don't pass fallbacks down
                )
                
                # Execute with this selector
                action_with_single_selector = BrowserAction(
                    action=action.action,
                    params=single_params
                )
                return await self._execute_single_action(action_with_single_selector, adapter, original_action_type)
                
            except (ExternalOperationPermanentError, ExternalOperationTransientError) as e:
                # Auto-invalidate cache on permanent errors (page structure changed)
                if isinstance(e, ExternalOperationPermanentError) and self._selector_resolution_service:
                    await self._auto_invalidate_cache_on_error(selector, e)
                
                if i == len(selectors) - 1:
                    # All selectors failed
                    if self.all_selectors_failed_handler is None:
                        self.all_selectors_failed_handler = AllSelectorsFailedHandler(self._selector_suggestion_service, await self.get_current_url(), await self.get_page_source())
                    await self.all_selectors_failed_handler.handle_all_selectors_failed(
                        method_name=action.action,
                        selectors=selectors,
                        last_error=e
                    )
                    # if all_selectors_failed_handler is not raising error (when ai suggesting) we need to raise the original error (on the last selector for now)
                    raise e
                # Try next selector
                continue
            

    async def _auto_invalidate_cache_on_error(self, selector: str, error: Exception) -> None:
        """Auto-invalidate cache when selector causes permanent error.
        
        Args:
            selector: The selector that failed
            error: The permanent error that occurred
        """
        try:
            from .selector_resolution.selector_parser import SelectorParser, SelectorType
            from lamia.adapters.web.driver_scope_manager import get_scope_manager
            
            # Only invalidate if this was an AI-resolved selector (natural language)
            parser = SelectorParser()
            selector_type = parser.classify(selector)
            
            if selector_type == SelectorType.NATURAL_LANGUAGE:
                scope_manager = get_scope_manager()
                page_url = getattr(scope_manager, 'current_url', 'unknown')
                
                logger.warning(
                    f"⚠️  Permanent error with AI-resolved selector '{selector}': {error}\n"
                    f"   Auto-invalidating cache to force re-resolution on next attempt.\n"
                    f"   This may indicate the page structure has changed."
                )
                
                await self._selector_resolution_service.invalidate_cached_selector(
                    selector,
                    page_url
                )
        except Exception as e:
            # Don't let cache invalidation errors break the main flow
            logger.debug(f"Failed to auto-invalidate cache: {e}")
    
    async def _execute_single_action(self, action: BrowserAction, adapter, original_action_type: Optional[WebActionType] = None) -> Any:
        """Execute single action without selector chain logic."""
        # Your existing switch statement
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
        elif action.action == BrowserActionType.GET_PAGE_SOURCE:
            return await adapter.get_page_source()
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
        elif action.action == BrowserActionType.IS_CHECKED:
            return await adapter.is_checked(action.params)
        elif action.action == BrowserActionType.GET_INPUT_TYPE:
            return await adapter.get_input_type(action.params)
        elif action.action == BrowserActionType.GET_OPTIONS:
            return await adapter.get_options(action.params)
        elif action.action == BrowserActionType.GET_ATTRIBUTE:
            return await adapter.get_attribute(action.params)
        elif action.action == BrowserActionType.UPLOAD_FILE:
            return await adapter.upload_file(action.params)
        elif action.action == BrowserActionType.GET_ELEMENTS:
            # Get list of element handles from adapter
            element_handles = await adapter.get_elements(action.params)
            # Wrap each handle in a WebActions instance
            from lamia.actions.web import WebActions
            
            # Check if this was originally GET_ELEMENT (singular) - return first or None
            if original_action_type == WebActionType.GET_ELEMENT:
                # Return first element or None
                if element_handles:
                    return WebActions(element_handle=element_handles[0], executor=self.web_manager)
                else:
                    return None
            else:
                # Return list of all elements
                return [WebActions(element_handle=handle, executor=self.web_manager) for handle in element_handles]
        else:
            raise ValueError(f"Unsupported browser action: {action.action}")
    
    async def _get_browser_adapter(self) -> BaseBrowserAdapter:
        """Get browser adapter with retry capabilities (cached)."""
        if self._browser_adapter is None:
            # Get session persistence configuration - always enable session persistence
            web_config = self.config_provider.get_web_config()
            session_config = web_config.get("session_persistence", {})
            # Always enable session persistence
            session_config.setdefault("enabled", True)
            session_config.setdefault("session_timeout", 24)
            session_config.setdefault("save_cookies", True)
            session_config.setdefault("save_local_storage", True)
            
            # Create browser adapter WITHOUT loading any cookies initially
            logger.info("Creating clean browser adapter (no cookies loaded yet)")
            if self._browser_engine == "selenium":
                base_adapter = SeleniumAdapter(
                    headless=self._browser_options.get("headless", False),
                    timeout=self._browser_options.get("timeout", 10.0),
                    session_config=session_config,
                    profile_name=self._active_profile
                )
            elif self._browser_engine == "playwright":
                base_adapter = PlaywrightAdapter(
                    headless=self._browser_options.get("headless", False),
                    timeout=self._browser_options.get("timeout", 10.0),
                    session_config=session_config,
                    profile_name=self._active_profile
                )
            else:
                raise ValueError(f"Unsupported browser engine: {self._browser_engine}")
            
            # Initialize adapter
            await base_adapter.initialize()
            
            # Create selector suggestion service only if auto_suggest_selectors is enabled
            auto_suggest = web_config.get('auto_suggest_selectors', False)
            if auto_suggest:
                logger.info("Auto-suggest selectors enabled, creating suggestion service")
                self._selector_suggestion_service = self._create_selector_suggestion_service()
            else:
                logger.debug("Auto-suggest selectors disabled (default), will save debug files only")
                self._selector_suggestion_service = None
            
            # Wrap with retry capabilities and pass suggestion service
            self._browser_adapter = RetriableAdapterFactory.create_browser_adapter(
                base_adapter,
                suggestion_service=self._selector_suggestion_service
            )
        
        return self._browser_adapter

    # --- Session profile control ---
    def set_active_profile(self, profile_name: Optional[str]) -> None:
        """Set current session profile hint for adapter creation and state ops."""
        self._active_profile = profile_name

    def get_active_profile(self) -> Optional[str]:
        return self._active_profile
    
    async def save_session_cookies(self, profile_name: str):
        """Save current browser cookies for a specific session profile.
        
        Args:
            profile_name: The session profile name (e.g., "login")
        """
        try:
            # Ensure adapter knows the active profile for saving
            self._active_profile = profile_name
            adapter = await self._get_browser_adapter()
            adapter.set_profile(profile_name)
            await adapter.save_session_state()
                
        except Exception as e:
            logger.error(f"Failed to save cookies for profile '{profile_name}': {e}")

    async def load_session_cookies(self, profile_name: str) -> bool:
        """Load cookies for a specific session profile.
        
        Args:
            profile_name: The session profile name (e.g., "login")
            
        Returns:
            bool: True if cookies were loaded successfully, False if no cookies exist
        """
        try:
            # Set active profile hint so adapter is built with correct profile
            self._active_profile = profile_name
            adapter = await self._get_browser_adapter()
            # Set profile on adapter and ask it to load state transactionally
            adapter.set_profile(profile_name)
            await adapter.load_session_state()
            logger.info(f"Loaded session state for profile '{profile_name}'")
            return True
                
        except Exception as e:
            logger.error(f"Failed to load cookies for profile '{profile_name}': {e}")
            return False
    
    async def _get_current_page_html(self) -> str:
        """Get current page HTML source."""
        adapter = await self._get_browser_adapter()
        return await adapter.get_page_source()
    
    def _create_selector_suggestion_service(self) -> SelectorSuggestionService:
        """Create selector suggestion service for AI-powered suggestions.
        
        Returns:
            SelectorSuggestionService instance
        """
        from ..llm.llm_manager import LLMManager
        llm_manager = LLMManager(self.config_provider)
        
        return SelectorSuggestionService(
            llm_manager=llm_manager,
            get_page_html_func=self._get_current_page_html
        )
    
    async def get_current_url(self) -> str:
        """Get current page URL.""" 
        adapter = await self._get_browser_adapter()
        return await adapter.get_current_url()
    
    async def get_page_source(self) -> str:
        """Get current page HTML source."""
        adapter = await self._get_browser_adapter()
        return await adapter.get_page_source()
    
    @staticmethod
    def get_browser_manager_from_lamia(lamia_instance):
        """Get the BrowserManager from a Lamia instance.
        
        This is the centralized way to access browser operations from any context.
        
        Args:
            lamia_instance: The Lamia instance
            
        Returns:
            BrowserManager: The browser manager instance
            
        Raises:
            Exception: If browser manager cannot be accessed
        """
        try:
            from lamia.interpreter.command_types import CommandType
            engine = lamia_instance._engine
            web_manager = engine.manager_factory.get_manager(CommandType.WEB)
            return web_manager.browser_manager
        except Exception as e:
            raise Exception(f"Cannot access BrowserManager from Lamia instance: {e}")

    async def close(self):
        """Close browser manager and cleanup resources."""
        # Close browser adapter if it exists
        if self._browser_adapter:
            await self._browser_adapter.close()
            self._browser_adapter = None
        
        # Note: We intentionally do NOT clear the selector resolution cache here
        # The cache should persist across browser sessions to avoid repeated AI calls
        
        logger.info("BrowserManager closed")