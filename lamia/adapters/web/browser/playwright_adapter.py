"""Playwright adapter for browser automation."""

from .base import (
    BaseBrowserAdapter,
    DOM_STABILITY_CHECK_SCRIPT,
    DOM_STABLE_MUTATION_QUIET_MS,
    DOM_STABILITY_TRACKER_BOOTSTRAP,
)
from lamia.errors import ExternalOperationTransientError, ExternalOperationPermanentError
from lamia.internal_types import BrowserActionParams, SelectorType
from ..session_manager import SessionManager
import logging
from typing import Optional, Dict, Any, List
import time
import asyncio
import json

try:
    from playwright.async_api import (
        async_playwright,
        Browser,
        Page,
        Playwright,
        BrowserContext,
        TimeoutError as PlaywrightTimeoutError,
        Error as PlaywrightError,
    )
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
    
    def _require_selector(self, params: BrowserActionParams) -> str:
        """Ensure selector is present for selector-based actions."""
        if not params.selector:
            raise ExternalOperationPermanentError(
                "Selector is required for this browser action",
                retry_history=[]
            )
        return params.selector
    
    async def _ensure_dom_tracker(self) -> None:
        """Ensure the DOM stability tracker bootstrap script is installed."""
        if not self.page:
            return
        try:
            await self.page.evaluate(DOM_STABILITY_TRACKER_BOOTSTRAP)
        except Exception as exc:
            logger.debug(f"PlaywrightAdapter: DOM tracker bootstrap failed: {exc}")

    def _has_quiet_dom_window(self, raw_value: Any) -> bool:
        """Return True if the DOM has been mutation-free for the configured quiet window."""
        try:
            time_since_mutation = float(raw_value)
        except (TypeError, ValueError):
            time_since_mutation = float("inf")
        return time_since_mutation >= DOM_STABLE_MUTATION_QUIET_MS
    
    async def _raise_dom_classified_error(self, message: str, original_error: Exception) -> None:
        """Raise permanent or transient error based on DOM stability."""
        if await self.is_dom_stable():
            raise ExternalOperationPermanentError(
                f"{message} (DOM stable)",
                retry_history=[],
                original_error=original_error
            )
        raise ExternalOperationTransientError(
            f"{message} (DOM still changing)",
            retry_history=[],
            original_error=original_error
        )
    
    async def is_dom_stable(self) -> bool:
        """Check if DOM is currently stable (no ongoing loads/changes)."""
        if not self.initialized or not self.page:
            return False
        
        try:
            await self._ensure_dom_tracker()
            result = await self.page.evaluate(DOM_STABILITY_CHECK_SCRIPT) or {}
            return (
                bool(result.get("readyStateComplete"))
                and int(result.get("pendingFetches", 0) or 0) == 0
                and int(result.get("pendingXhrs", 0) or 0) == 0
                and self._has_quiet_dom_window(result.get("timeSinceMutation"))
            )
        except Exception:
            # Assume unstable if evaluation fails to avoid false permanent errors
            return False
    
    def _get_timeout_ms(self, params: BrowserActionParams) -> float:
        """Return timeout in milliseconds for Playwright operations."""
        return params.timeout * 1000 if params.timeout else self.default_timeout
    
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
            await self._ensure_dom_tracker()
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
        """Find element using primary selector and fallbacks.
        
        Supports scoped search if params.scope_element_handle is provided.
        """
        selectors = [params.selector] + (params.fallback_selectors or [])
        timeout = params.timeout * 1000 if params.timeout else self.default_timeout
        
        # Determine search root: scoped element or page
        search_root = params.scope_element_handle if params.scope_element_handle else self.page
        
        for selector in selectors:
            try:
                playwright_selector = self._get_playwright_selector(selector, params.selector_type)
                element = await search_root.wait_for_selector(playwright_selector, timeout=timeout)
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
        await self._ensure_dom_tracker()
    
    async def click(self, params: BrowserActionParams) -> None:
        """Click an element."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        selector = self._require_selector(params)
        logger.info(f"PlaywrightAdapter: Click element {selector}")
        playwright_selector = self._get_playwright_selector(selector, params.selector_type)
        timeout = self._get_timeout_ms(params)
        
        try:
            await self.page.click(playwright_selector, timeout=timeout)
            logger.info(f"PlaywrightAdapter: Successfully clicked {selector}")
            await self._wait_for_dom_stability()
        except PlaywrightTimeoutError as e:
            await self._raise_dom_classified_error(
                f"Element '{selector}' not clickable",
                e
            )
        except PlaywrightError as e:
            raise ExternalOperationTransientError(
                f"Click failed for '{selector}': {e}",
                retry_history=[],
                original_error=e
            )
    
    async def type_text(self, params: BrowserActionParams) -> None:
        """Type text into an element."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        text = params.value
        selector = self._require_selector(params)
        logger.info(f"PlaywrightAdapter: Type '{text}' into {selector}")
        playwright_selector = self._get_playwright_selector(selector, params.selector_type)
        timeout = self._get_timeout_ms(params)
        
        try:
            await self.page.fill(playwright_selector, text, timeout=timeout)
        except PlaywrightTimeoutError as e:
            await self._raise_dom_classified_error(
                f"Element '{selector}' not found for typing",
                e
            )
        except PlaywrightError as e:
            raise ExternalOperationTransientError(
                f"Type text failed for '{selector}': {e}",
                retry_history=[],
                original_error=e
            )
    
    async def upload_file(self, params: BrowserActionParams) -> None:
        """Upload a file to a file input element."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        if not params.value:
            raise ValueError("File path is required for upload_file action")
        
        file_path = params.value
        selector = self._require_selector(params)
        logger.info(f"PlaywrightAdapter: Upload file '{file_path}' to {selector}")
        playwright_selector = self._get_playwright_selector(selector, params.selector_type)
        timeout = self._get_timeout_ms(params)
        
        try:
            await self.page.set_input_files(playwright_selector, file_path, timeout=timeout)
        except PlaywrightTimeoutError as e:
            await self._raise_dom_classified_error(
                f"File input '{selector}' not found for upload",
                e
            )
        except PlaywrightError as e:
            raise ExternalOperationTransientError(
                f"File upload failed for '{selector}': {e}",
                retry_history=[],
                original_error=e
            )
    
    async def wait_for_element(self, params: BrowserActionParams) -> None:
        """Wait for an element to meet a condition."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        timeout = params.timeout * 1000 if params.timeout else self.default_timeout
        condition = params.wait_condition or "visible"
        
        selector = self._require_selector(params)
        logger.info(f"PlaywrightAdapter: Wait for {selector} to be {condition}")
        
        playwright_selector = self._get_playwright_selector(selector, params.selector_type)
        
        try:
            if condition == "visible":
                await self.page.wait_for_selector(playwright_selector, state="visible", timeout=timeout)
            elif condition == "hidden":
                await self.page.wait_for_selector(playwright_selector, state="hidden", timeout=timeout)
            elif condition == "present":
                await self.page.wait_for_selector(playwright_selector, timeout=timeout)
            elif condition == "clickable":
                element = await self.page.wait_for_selector(playwright_selector, timeout=timeout)
                await element.wait_for_element_state("stable")
        except PlaywrightTimeoutError as e:
            await self._raise_dom_classified_error(
                f"Condition '{condition}' not met for '{selector}'",
                e
            )
    
    async def get_text(self, params: BrowserActionParams) -> str:
        """Get text content of an element."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        selector = self._require_selector(params)
        logger.info(f"PlaywrightAdapter: Get text from {selector}")
        playwright_selector = self._get_playwright_selector(selector, params.selector_type)
        timeout = self._get_timeout_ms(params)
        
        try:
            element = await self.page.wait_for_selector(playwright_selector, timeout=timeout)
            return await element.text_content() or ""
        except PlaywrightTimeoutError as e:
            await self._raise_dom_classified_error(
                f"Element '{selector}' not found for get_text",
                e
            )
            return ""
    
    async def get_attribute(self, params: BrowserActionParams) -> str:
        """Get attribute value of an element."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        attribute_name = params.value
        selector = self._require_selector(params)
        logger.info(f"PlaywrightAdapter: Get attribute '{attribute_name}' from {selector}")
        playwright_selector = self._get_playwright_selector(selector, params.selector_type)
        timeout = self._get_timeout_ms(params)
        
        try:
            element = await self.page.wait_for_selector(playwright_selector, timeout=timeout)
            return await element.get_attribute(attribute_name) or ""
        except PlaywrightTimeoutError as e:
            await self._raise_dom_classified_error(
                f"Element '{selector}' not found for get_attribute",
                e
            )
            return ""
    
    async def is_visible(self, params: BrowserActionParams) -> bool:
        """Check if an element is visible."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        selector = self._require_selector(params)
        playwright_selector = self._get_playwright_selector(selector, params.selector_type)
        
        element = await self.page.query_selector(playwright_selector)
        if not element:
            await self._raise_dom_classified_error(
                f"Element '{selector}' not found for visibility check",
                PlaywrightError("Element not found")
            )
        
        try:
            visible = await element.is_visible()
            logger.info(f"PlaywrightAdapter: Check if {selector} is visible -> {visible}")
            return visible
        except PlaywrightError as e:
            raise ExternalOperationTransientError(
                f"Visibility check failed for '{selector}': {e}",
                retry_history=[],
                original_error=e
            )
    
    async def is_enabled(self, params: BrowserActionParams) -> bool:
        """Check if an element is enabled."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        selector = self._require_selector(params)
        playwright_selector = self._get_playwright_selector(selector, params.selector_type)
        
        element = await self.page.query_selector(playwright_selector)
        if not element:
            await self._raise_dom_classified_error(
                f"Element '{selector}' not found for enablement check",
                PlaywrightError("Element not found")
            )
        
        try:
            enabled = await element.is_enabled()
            logger.info(f"PlaywrightAdapter: Check if {selector} is enabled -> {enabled}")
            return enabled
        except PlaywrightError as e:
            raise ExternalOperationTransientError(
                f"Enablement check failed for '{selector}': {e}",
                retry_history=[],
                original_error=e
            )
    
    async def is_checked(self, params: BrowserActionParams) -> bool:
        """Check if a checkbox or radio button is checked."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        element = await self._find_element_with_fallbacks(params)
        try:
            checked = await element.is_checked()
            logger.info(f"PlaywrightAdapter: Check if element is checked -> {checked}")
            return checked
        except PlaywrightError as e:
            raise ExternalOperationTransientError(
                f"Checked state check failed: {e}",
                retry_history=[],
                original_error=e
            )
    
    async def get_input_type(self, params: BrowserActionParams) -> str:
        """Detect the type of an input element.
        
        Returns InputType enum value as string.
        """
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        from lamia.types import InputType
        
        element = await self._find_element_with_fallbacks(params)
        try:
            # Get tag name
            tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
            
            # For input elements, get the type attribute
            if tag_name == "input":
                type_value = (await element.get_attribute("type") or "text").lower()
            else:
                # For select, textarea, button - use tag name as type
                type_value = tag_name
            
            # Direct enum lookup - covers all cases
            try:
                result = InputType(type_value)
            except ValueError:
                result = InputType.UNKNOWN
            
            logger.info(f"PlaywrightAdapter: Detected input type -> {result.value}")
            return result.value
            
        except PlaywrightError as e:
            raise ExternalOperationTransientError(
                f"Input type detection failed: {e}",
                retry_history=[],
                original_error=e
            )
    
    async def get_options(self, params: BrowserActionParams) -> List[str]:
        """Get all selectable option texts from radio/checkbox/select within scope.
        
        Auto-detects and validates that exactly one option group exists.
        """
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        from lamia.errors import MultipleSelectableInputsError, NoSelectableInputError
        
        # Get scope element or use page
        search_root = params.scope_element_handle if params.scope_element_handle else self.page
        
        # Find all selectable inputs within scope
        try:
            radios = await search_root.query_selector_all("input[type='radio']")
            checkboxes = await search_root.query_selector_all("input[type='checkbox']")
            selects = await search_root.query_selector_all("select")
        except PlaywrightError as e:
            raise ExternalOperationTransientError(
                f"Failed to search for selectable inputs: {e}",
                retry_history=[],
                original_error=e
            )
        
        # Count how many types of inputs we have
        found_types = []
        elements = None
        input_type = None
        
        if radios:
            # Check if multiple radio groups (different 'name' attributes)
            radio_names = set()
            for r in radios:
                name = await r.get_attribute("name")
                if name:
                    radio_names.add(name)
            if len(radio_names) > 1:
                raise MultipleSelectableInputsError(
                    f"Found {len(radio_names)} radio button groups with different names: {radio_names}. "
                    "Please narrow the scope to target a specific radio group."
                )
            found_types.append("radio")
            elements = radios
            input_type = "radio"
        
        if checkboxes:
            # Check if multiple checkbox groups (different 'name' attributes)
            checkbox_names = set()
            for c in checkboxes:
                name = await c.get_attribute("name")
                if name:
                    checkbox_names.add(name)
            if len(checkbox_names) > 1:
                raise MultipleSelectableInputsError(
                    f"Found {len(checkbox_names)} checkbox groups with different names: {checkbox_names}. "
                    "Please narrow the scope to target a specific checkbox group."
                )
            found_types.append("checkbox")
            elements = checkboxes
            input_type = "checkbox"
        
        if selects:
            if len(selects) > 1:
                raise MultipleSelectableInputsError(
                    f"Found {len(selects)} dropdown (<select>) elements in scope. "
                    "Please narrow the scope to target a specific dropdown."
                )
            found_types.append("select")
            elements = selects[0]  # Single select element
            input_type = "select"
        
        # Validate: exactly one type
        if len(found_types) == 0:
            raise NoSelectableInputError(
                "No radio buttons, checkboxes, or dropdowns found in the current scope"
            )
        
        if len(found_types) > 1:
            raise MultipleSelectableInputsError(
                f"Found multiple input types in scope: {found_types}. "
                "Please narrow the scope to target a specific input type."
            )
        
        # Extract options from the single input group
        options = []
        
        try:
            if input_type in ["radio", "checkbox"]:
                # Get labels for each input
                for elem in elements:
                    # Try to find associated label
                    input_id = await elem.get_attribute("id")
                    if input_id:
                        label = await search_root.query_selector(f"label[for='{input_id}']")
                        if label:
                            text = await label.text_content()
                            options.append(text.strip())
                            continue
                    
                    # Try parent label
                    label = await elem.evaluate("el => el.closest('label')")
                    if label:
                        text = await elem.evaluate("el => el.closest('label').textContent")
                        options.append(text.strip())
                        continue
                    
                    # Try sibling label
                    label = await elem.evaluate("el => el.nextElementSibling?.tagName === 'LABEL' ? el.nextElementSibling : null")
                    if label:
                        text = await elem.evaluate("el => el.nextElementSibling.textContent")
                        options.append(text.strip())
                        continue
                    
                    # Last resort: use value attribute
                    value = await elem.get_attribute("value") or "Unknown option"
                    options.append(value)
            
            elif input_type == "select":
                # Get all option elements
                option_elements = await elements.query_selector_all("option")
                for opt in option_elements:
                    text = await opt.text_content()
                    if text and text.strip():
                        options.append(text.strip())
            
            logger.info(f"PlaywrightAdapter: Found {len(options)} options: {options}")
            return options
            
        except PlaywrightError as e:
            raise ExternalOperationTransientError(
                f"Failed to extract option texts: {e}",
                retry_history=[],
                original_error=e
            )
    
    async def get_elements(self, params: BrowserActionParams) -> List[Any]:
        """Get multiple elements matching selector.
        
        Returns list of Playwright ElementHandle objects for scoping.
        """
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        selector = self._require_selector(params)
        timeout = self._get_timeout_ms(params)
        
        # Use scope element if provided
        search_root = params.scope_element_handle if params.scope_element_handle else self.page
        
        # Try all selectors in fallback chain
        selectors = [selector]
        if params.fallback_selectors:
            selectors.extend(params.fallback_selectors)
        
        for sel in selectors:
            try:
                playwright_selector = self._get_playwright_selector(sel, params.selector_type)
                
                # Wait for at least one element
                await search_root.wait_for_selector(playwright_selector, timeout=timeout)
                
                # Get all matching elements
                elements = await search_root.query_selector_all(playwright_selector)
                
                logger.info(f"PlaywrightAdapter: Found {len(elements)} elements matching '{sel}'")
                return elements
                
            except PlaywrightTimeoutError:
                logger.debug(f"PlaywrightAdapter: Selector '{sel}' did not match")
                continue
        
        # All selectors failed
        return []
    
    async def hover(self, params: BrowserActionParams) -> None:
        """Hover over an element."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        selector = self._require_selector(params)
        logger.info(f"PlaywrightAdapter: Hover over {selector}")
        playwright_selector = self._get_playwright_selector(selector, params.selector_type)
        timeout = self._get_timeout_ms(params)
        
        try:
            await self.page.hover(playwright_selector, timeout=timeout)
        except PlaywrightTimeoutError as e:
            await self._raise_dom_classified_error(
                f"Element '{selector}' not found for hover",
                e
            )
    
    async def scroll(self, params: BrowserActionParams) -> None:
        """Scroll to an element."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        selector = self._require_selector(params)
        logger.info(f"PlaywrightAdapter: Scroll to {selector}")
        playwright_selector = self._get_playwright_selector(selector, params.selector_type)
        timeout = self._get_timeout_ms(params)
        
        try:
            element = await self.page.wait_for_selector(playwright_selector, timeout=timeout)
            await element.scroll_into_view_if_needed()
        except PlaywrightTimeoutError as e:
            await self._raise_dom_classified_error(
                f"Element '{selector}' not found for scroll",
                e
            )
    
    async def select_option(self, params: BrowserActionParams) -> None:
        """Select an option from a dropdown."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        option_value = params.value
        selector = self._require_selector(params)
        logger.info(f"PlaywrightAdapter: Select option '{option_value}' in {selector}")
        playwright_selector = self._get_playwright_selector(selector, params.selector_type)
        timeout = self._get_timeout_ms(params)
        
        try:
            await self.page.select_option(playwright_selector, value=option_value, timeout=timeout)
        except PlaywrightTimeoutError as e:
            await self._raise_dom_classified_error(
                f"Option '{option_value}' not found for '{selector}'",
                e
            )
    
    async def submit_form(self, params: BrowserActionParams) -> None:
        """Submit a form."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        selector = self._require_selector(params)
        logger.info(f"PlaywrightAdapter: Submit form {selector}")
        playwright_selector = self._get_playwright_selector(selector, params.selector_type)
        
        # Find form element and submit
        form_element = await self.page.query_selector(playwright_selector)
        if form_element:
            await form_element.evaluate("form => form.submit()")
        else:
            await self._raise_dom_classified_error(
                f"Form '{selector}' not found",
                PlaywrightError("Form element not found")
            )
    
    async def take_screenshot(self, params: BrowserActionParams) -> str:
        """Take a screenshot."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        file_path = params.value or f"screenshot_{int(time.time())}.png"
        logger.info(f"PlaywrightAdapter: Take screenshot -> {file_path}")
        
        await self.page.screenshot(path=file_path)
        return file_path
    
    async def get_page_source(self) -> str:
        """Get the current page HTML source."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        if self.page:
            return await self.page.content()
        else:
            return ""
        
    async def get_current_url(self) -> Optional[str]:
        """Get the current page URL."""
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        if self.page:
            return self.page.url
        else:
            return None
    
    async def _wait_for_dom_stability(self, timeout: float = 2.0, check_interval: float = 0.1):
        """Wait for DOM to stabilize after a click action."""
        logger.info("PlaywrightAdapter: Waiting for DOM stability after click")
        try:
            await self._ensure_dom_tracker()
            start_time = time.time()
            stable_checks = 0
            
            while time.time() - start_time < timeout:
                if await self.is_dom_stable():
                    stable_checks += 1
                    if stable_checks >= 3:
                        elapsed = time.time() - start_time
                        logger.info(f"PlaywrightAdapter: DOM stabilized in {elapsed:.2f}s")
                        return
                else:
                    stable_checks = 0
                
                await asyncio.sleep(check_interval)
            
            logger.warning("PlaywrightAdapter: DOM stability wait timed out, proceeding anyway")
        except Exception as e:
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

    async def execute_script(self, script: str) -> Any:
        """Execute JavaScript in the browser.
        
        Args:
            script: JavaScript code to execute
            
        Returns:
            Result of the JavaScript execution
        """
        if not self.initialized:
            raise RuntimeError("PlaywrightAdapter not initialized")
        
        try:
            return await self.page.evaluate(script)
        except Exception as e:
            logger.error(f"JavaScript execution failed: {e}")
            raise
    

