"""Playwright adapter for browser automation."""

from .base import BaseBrowserAdapter
from lamia.types import BrowserActionParams, SelectorType
from ..session_manager import SessionManager
import logging
from typing import Optional, Dict, Any, List
import time
import asyncio
import json

try:
    from playwright.async_api import async_playwright, Browser, Page, Playwright, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

logger = logging.getLogger(__name__)


class PlaywrightAdapter(BaseBrowserAdapter):
    """Playwright adapter for browser automation."""
    
    def __init__(self, headless: bool = True, timeout: float = 10000.0, session_config: Optional[Dict[str, Any]] = None, profile_name: Optional[str] = None):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.headless = headless
        self.default_timeout = timeout
        self.initialized = False
        
        # Session persistence setup
        self.session_manager = SessionManager(session_config) if session_config else None
        self.profile_name = profile_name or "default"
        self.use_persistent_context = False
        
        if self.session_manager and self.session_manager.enabled:
            self.use_persistent_context = True
            logger.info(f"Session persistence enabled for profile: {self.profile_name}")
    
    async def initialize(self) -> None:
        """Initialize the Playwright browser."""
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright not installed. Please install with: pip install playwright")
        
        logger.info("PlaywrightAdapter: Initializing Chromium browser...")
        
        try:
            self.playwright = await async_playwright().start()
            
            if self.use_persistent_context and self.session_manager:
                # Use persistent context for session management
                user_data_dir = self.session_manager.get_profile_session_dir(self.profile_name)
                
                self.context = await self.playwright.chromium.launch_persistent_context(
                    user_data_dir=str(user_data_dir),
                    headless=self.headless,
                    args=['--no-sandbox', '--disable-dev-shm-usage']
                )
                self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
                logger.info(f"PlaywrightAdapter: Using persistent context for profile: {self.profile_name}")
            else:
                # Standard browser initialization
                self.browser = await self.playwright.chromium.launch(
                    headless=self.headless,
                    args=['--no-sandbox', '--disable-dev-shm-usage']
                )
                self.context = await self.browser.new_context()
                self.page = await self.context.new_page()
                
                # Load existing cookies if session persistence is enabled
                if self.session_manager and self.session_manager.enabled:
                    await self._load_session_data()
            
            self.page.set_default_timeout(self.default_timeout)
            self.initialized = True
            logger.info("PlaywrightAdapter: Chromium browser initialized")
        except Exception as e:
            logger.error(f"PlaywrightAdapter: Failed to initialize Chromium browser: {e}")
            raise
    
    async def close(self) -> None:
        """Close the browser."""
        logger.info("PlaywrightAdapter: Closing browser...")
        try:
            # Save session data before closing
            if self.session_manager and self.session_manager.enabled and not self.use_persistent_context:
                await self._save_session_data()
            
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.warning(f"Warning during browser cleanup: {e}")
        finally:
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None
            self.initialized = False
        logger.info("PlaywrightAdapter: Browser closed")
    
    def _get_playwright_selector(self, selector: str, selector_type: SelectorType) -> str:
        """Convert selector to Playwright format."""
        if selector_type == SelectorType.CSS:
            return selector
        elif selector_type == SelectorType.XPATH:
            return f"xpath={selector}"
        elif selector_type == SelectorType.ID:
            return f"id={selector.lstrip('#')}"
        elif selector_type == SelectorType.CLASS_NAME:
            return f".{selector.lstrip('.')}"
        elif selector_type == SelectorType.TAG_NAME:
            return selector
        elif selector_type == SelectorType.NAME:
            return f"[name='{selector}']"
        elif selector_type == SelectorType.LINK_TEXT:
            return f"text={selector}"
        elif selector_type == SelectorType.PARTIAL_LINK_TEXT:
            return f"text*={selector}"
        else:
            # Default to CSS selector
            return selector
    
    async def _find_element_with_fallbacks(self, params: BrowserActionParams):
        """Find element using primary selector and fallbacks."""
        selectors = [params.selector] + (params.fallback_selectors or [])
        timeout = params.timeout * 1000 if params.timeout else self.default_timeout
        
        for selector in selectors:
            try:
                playwright_selector = self._get_playwright_selector(selector, params.selector_type)
                element = await self.page.wait_for_selector(playwright_selector, timeout=timeout)
                logger.debug(f"Found element with selector: {selector}")
                return element
            except Exception:
                logger.debug(f"Selector failed: {selector}")
                continue
        
        # If all selectors failed
        raise Exception(f"Could not find element with any of the selectors: {selectors}")
    
    async def navigate(self, params: BrowserActionParams) -> None:
        """Navigate to a URL."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        url = params.value
        logger.info(f"PlaywrightAdapter: Navigate to {url}")
        await self.page.goto(url)
    
    async def click(self, params: BrowserActionParams) -> None:
        """Click an element."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        logger.info(f"PlaywrightAdapter: Click element {params.selector}")
        playwright_selector = self._get_playwright_selector(params.selector, params.selector_type)
        timeout = params.timeout * 1000 if params.timeout else self.default_timeout
        
        await self.page.click(playwright_selector, timeout=timeout)
        logger.info(f"PlaywrightAdapter: Successfully clicked {params.selector}")
        
        # Wait for DOM stabilization after click
        await self._wait_for_dom_stability()
    
    async def type_text(self, params: BrowserActionParams) -> None:
        """Type text into an element."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        text = params.value
        logger.info(f"PlaywrightAdapter: Type '{text}' into {params.selector}")
        playwright_selector = self._get_playwright_selector(params.selector, params.selector_type)
        timeout = params.timeout * 1000 if params.timeout else self.default_timeout
        
        await self.page.fill(playwright_selector, text, timeout=timeout)
    
    async def wait_for_element(self, params: BrowserActionParams) -> None:
        """Wait for an element to meet a condition."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        timeout = params.timeout * 1000 if params.timeout else self.default_timeout
        condition = params.wait_condition or "visible"
        
        logger.info(f"PlaywrightAdapter: Wait for {params.selector} to be {condition}")
        
        playwright_selector = self._get_playwright_selector(params.selector, params.selector_type)
        
        if condition == "visible":
            await self.page.wait_for_selector(playwright_selector, state="visible", timeout=timeout)
        elif condition == "hidden":
            await self.page.wait_for_selector(playwright_selector, state="hidden", timeout=timeout)
        elif condition == "present":
            await self.page.wait_for_selector(playwright_selector, timeout=timeout)
        elif condition == "clickable":
            element = await self.page.wait_for_selector(playwright_selector, timeout=timeout)
            await element.wait_for_element_state("stable")
    
    async def get_text(self, params: BrowserActionParams) -> str:
        """Get text content of an element."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        logger.info(f"PlaywrightAdapter: Get text from {params.selector}")
        playwright_selector = self._get_playwright_selector(params.selector, params.selector_type)
        timeout = params.timeout * 1000 if params.timeout else self.default_timeout
        
        element = await self.page.wait_for_selector(playwright_selector, timeout=timeout)
        return await element.text_content() or ""
    
    async def get_attribute(self, params: BrowserActionParams) -> str:
        """Get attribute value of an element."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        attribute_name = params.value
        logger.info(f"PlaywrightAdapter: Get attribute '{attribute_name}' from {params.selector}")
        playwright_selector = self._get_playwright_selector(params.selector, params.selector_type)
        timeout = params.timeout * 1000 if params.timeout else self.default_timeout
        
        element = await self.page.wait_for_selector(playwright_selector, timeout=timeout)
        return await element.get_attribute(attribute_name) or ""
    
    async def is_visible(self, params: BrowserActionParams) -> bool:
        """Check if an element is visible."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        try:
            playwright_selector = self._get_playwright_selector(params.selector, params.selector_type)
            element = await self.page.query_selector(playwright_selector)
            if element:
                visible = await element.is_visible()
                logger.info(f"PlaywrightAdapter: Check if {params.selector} is visible -> {visible}")
                return visible
            else:
                logger.info(f"PlaywrightAdapter: Check if {params.selector} is visible -> False (not found)")
                return False
        except Exception:
            logger.info(f"PlaywrightAdapter: Check if {params.selector} is visible -> False (error)")
            return False
    
    async def is_enabled(self, params: BrowserActionParams) -> bool:
        """Check if an element is enabled."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        try:
            playwright_selector = self._get_playwright_selector(params.selector, params.selector_type)
            element = await self.page.query_selector(playwright_selector)
            if element:
                enabled = await element.is_enabled()
                logger.info(f"PlaywrightAdapter: Check if {params.selector} is enabled -> {enabled}")
                return enabled
            else:
                logger.info(f"PlaywrightAdapter: Check if {params.selector} is enabled -> False (not found)")
                return False
        except Exception:
            logger.info(f"PlaywrightAdapter: Check if {params.selector} is enabled -> False (error)")
            return False
    
    async def hover(self, params: BrowserActionParams) -> None:
        """Hover over an element."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        logger.info(f"PlaywrightAdapter: Hover over {params.selector}")
        playwright_selector = self._get_playwright_selector(params.selector, params.selector_type)
        timeout = params.timeout * 1000 if params.timeout else self.default_timeout
        
        await self.page.hover(playwright_selector, timeout=timeout)
    
    async def scroll(self, params: BrowserActionParams) -> None:
        """Scroll to an element."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        logger.info(f"PlaywrightAdapter: Scroll to {params.selector}")
        playwright_selector = self._get_playwright_selector(params.selector, params.selector_type)
        timeout = params.timeout * 1000 if params.timeout else self.default_timeout
        
        element = await self.page.wait_for_selector(playwright_selector, timeout=timeout)
        await element.scroll_into_view_if_needed()
    
    async def select_option(self, params: BrowserActionParams) -> None:
        """Select an option from a dropdown."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        option_value = params.value
        logger.info(f"PlaywrightAdapter: Select option '{option_value}' in {params.selector}")
        playwright_selector = self._get_playwright_selector(params.selector, params.selector_type)
        timeout = params.timeout * 1000 if params.timeout else self.default_timeout
        
        await self.page.select_option(playwright_selector, value=option_value, timeout=timeout)
    
    async def submit_form(self, params: BrowserActionParams) -> None:
        """Submit a form."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        logger.info(f"PlaywrightAdapter: Submit form {params.selector}")
        playwright_selector = self._get_playwright_selector(params.selector, params.selector_type)
        
        # Find form element and submit
        form_element = await self.page.query_selector(playwright_selector)
        if form_element:
            await form_element.evaluate("form => form.submit()")
        else:
            raise Exception(f"Form not found with selector: {params.selector}")
    
    async def take_screenshot(self, params: BrowserActionParams) -> str:
        """Take a screenshot."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        file_path = params.value or f"screenshot_{int(time.time())}.png"
        logger.info(f"PlaywrightAdapter: Take screenshot -> {file_path}")
        
        await self.page.screenshot(path=file_path)
        return file_path
    
    async def _wait_for_dom_stability(self, timeout: float = 2000):
        """Wait for DOM to stabilize after a click action."""
        logger.info("PlaywrightAdapter: Waiting for DOM stability after click")
        start_time = time.time()
        
        try:
            # Wait for network idle (no network requests for 500ms)
            await self.page.wait_for_load_state("networkidle", timeout=timeout)
            elapsed = time.time() - start_time
            logger.info(f"PlaywrightAdapter: DOM stabilized in {elapsed:.2f}s")
        except Exception:
            try:
                # Fallback: wait for DOM content to be ready
                await self.page.wait_for_load_state("domcontentloaded", timeout=1000)
                elapsed = time.time() - start_time
                logger.info(f"PlaywrightAdapter: DOM content loaded in {elapsed:.2f}s")
            except Exception as e:
                # Final fallback: short sleep
                logger.warning(f"PlaywrightAdapter: DOM stability check failed ({e}), using fallback wait")
                await asyncio.sleep(0.5)
    
    async def _load_session_data(self):
        """Load session data (cookies, local storage) from files."""
        if not self.session_manager or not self.session_manager.enabled:
            return
        
        try:
            # Load cookies
            cookies = self.session_manager.load_cookies(self.profile_name)
            if cookies and self.context:
                await self.context.add_cookies(cookies)
                logger.info(f"Loaded {len(cookies)} cookies for profile: {self.profile_name}")
            
            # Update session last used time
            self.session_manager.update_last_used(self.profile_name)
            
        except Exception as e:
            logger.warning(f"Failed to load session data for profile '{self.profile_name}': {e}")
    
    async def _save_session_data(self):
        """Save session data (cookies, local storage) to files."""
        if not self.session_manager or not self.session_manager.enabled or not self.context:
            return
        
        try:
            # Save cookies
            cookies = await self.context.cookies()
            self.session_manager.save_cookies(self.profile_name, cookies)
            
            # Save local storage for each domain if we have a page
            if self.page:
                try:
                    local_storage = await self.page.evaluate("""
                        () => {
                            const storage = {};
                            for (let i = 0; i < localStorage.length; i++) {
                                const key = localStorage.key(i);
                                storage[key] = localStorage.getItem(key);
                            }
                            return storage;
                        }
                    """)
                    self.session_manager.save_local_storage(self.profile_name, local_storage)
                except Exception as e:
                    logger.debug(f"Could not save local storage: {e}")
            
            # Update session info
            self.session_manager.save_session_info(self.profile_name, {
                'browser_engine': 'playwright',
                'cookies_count': len(cookies)
            })
            
        except Exception as e:
            logger.warning(f"Failed to save session data for profile '{self.profile_name}': {e}")
    

