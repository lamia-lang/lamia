"""Real Selenium adapter for browser automation."""

from .base import (
    BaseBrowserAdapter,
    DOM_STABILITY_CHECK_SCRIPT,
    DOM_STABLE_MUTATION_QUIET_MS,
    DOM_STABILITY_TRACKER_BOOTSTRAP,
)
from lamia.engine.managers.web.selector_resolution.successful_selector_cache import SuccessfulSelectorCache
from lamia.errors import ExternalOperationTransientError, ExternalOperationPermanentError
from lamia.internal_types import BrowserActionParams, SelectorType
from ..session_manager import SessionManager
import logging
from typing import Optional, Dict, Any, List
import time
import json

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import Select
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

logger = logging.getLogger(__name__)


class SeleniumAdapter(BaseBrowserAdapter):
    """Real Selenium adapter for browser automation."""
    
    def __init__(self, headless: bool = True, timeout: float = 10.0, session_config: Optional[Dict[str, Any]] = None, profile_name: Optional[str] = None):
        self.driver = None
        self.headless = headless
        self.default_timeout = timeout
        self.initialized = False
        self._last_dom_snapshot: Dict[str, Any] = {}
        self._last_dom_reason: str = ""
        
        # Session persistence setup
        self.session_manager = SessionManager(session_config) if session_config else None
        
        # Use provided profile name, otherwise default
        if profile_name:
            self.profile_name = profile_name
        else:
            self.profile_name = "default"
        
        # Successful selector cache to skip directly to working selectors on repeated runs
        self.selector_cache = SuccessfulSelectorCache()
        
        print(f"TO DELETE: session_manager={self.session_manager}, enabled={self.session_manager.enabled if self.session_manager else 'N/A'}")
        if self.session_manager and self.session_manager.enabled:
            print(f"TO DELETE: Session persistence IS enabled for profile: {self.profile_name}")
            logger.info(f"Session persistence enabled for profile: {self.profile_name}")
        else:
            print(f"TO DELETE: Session persistence NOT enabled")
    
    def _require_selector(self, params: BrowserActionParams) -> str:
        """Ensure selector is provided for selector-based actions."""
        if not params.selector:
            raise ExternalOperationPermanentError(
                "Selector is required for this browser action",
                retry_history=[]
            )
        return params.selector

    def _selector_chain(self, params: BrowserActionParams) -> List[str]:
        """Return primary selector plus fallback chain, preserving order."""
        selectors: List[str] = []
        if params.selector:
            selectors.append(params.selector)
        if params.fallback_selectors:
            selectors.extend([selector for selector in params.fallback_selectors if selector])
        if not selectors:
            raise ExternalOperationPermanentError(
                "At least one selector is required for this browser action",
                retry_history=[]
            )
        return selectors
    
    def _ensure_dom_tracker(self) -> None:
        """Inject the DOM stability tracker if missing on the current page."""
        if not self.driver:
            return
        try:
            self.driver.execute_script(DOM_STABILITY_TRACKER_BOOTSTRAP)
        except Exception as exc:
            logger.debug(f"SeleniumAdapter: DOM tracker bootstrap failed: {exc}")
    
    def _raise_dom_classified_error(self, message: str, original_error: Exception) -> None:
        """Raise permanent or transient error based on DOM stability."""
        if self._is_dom_stable_sync():
            logger.info(
                "SeleniumAdapter: Raising permanent error on selector not found because DOM is stable (%s)", self._last_dom_reason
            )
            raise ExternalOperationPermanentError(
                f"{message} (DOM stable)",
                retry_history=[],
                original_error=original_error
            )
        logger.info(
            "SeleniumAdapter: Raising transient error when trying to find selector because DOM is unstable (%s)", self._last_dom_reason
        )
        raise ExternalOperationTransientError(
            f"{message} (DOM still changing)",
            retry_history=[],
            original_error=original_error
        )
    
    def _is_dom_stable_sync(self) -> bool:
        """Synchronous DOM stability check used internally across methods."""
        if not self.driver:
            return False
        
        try:
            self._ensure_dom_tracker()
            result = self.driver.execute_script(DOM_STABILITY_CHECK_SCRIPT) or {}
            self._last_dom_snapshot = result
            pending_fetches = int(result.get("pendingFetches", 0) or 0)
            pending_xhrs = int(result.get("pendingXhrs", 0) or 0)

            if pending_fetches > 0 or pending_xhrs > 0:
                self._last_dom_reason = (
                    f"pendingFetches={pending_fetches}, pendingXhrs={pending_xhrs}"
                )
                return False

            self._last_dom_reason = (
                f"pendingFetches={pending_fetches}, pendingXhrs={pending_xhrs}"
            )
            return True
        except Exception:
            self._last_dom_snapshot = {}
            self._last_dom_reason = "DOM stability probe failed"
            # Assume unstable if check fails to avoid premature permanent classification
            return False
    
    def _has_quiet_dom_window(self, raw_value: Any) -> bool:
        """Check if the DOM has been mutation-free for the configured quiet window."""
        try:
            time_since_mutation = float(raw_value)
        except (TypeError, ValueError):
            time_since_mutation = float("inf")
        return time_since_mutation >= DOM_STABLE_MUTATION_QUIET_MS
    
    async def is_dom_stable(self) -> bool:
        """Async interface for DOM stability used by manager-level logic."""
        return self._is_dom_stable_sync()
    
    async def initialize(self) -> None:
        """Initialize the Selenium WebDriver."""
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium not installed. Please install with: pip install selenium")
        
        logger.info("SeleniumAdapter: Initializing Chrome WebDriver...")
        
        # Configure Chrome options
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Do not bind Chrome to a per-profile user data dir here. We manage
        # session state (cookies/localStorage) explicitly per profile via
        # BrowserManager + SessionManager to avoid default profile leakage.
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(self.default_timeout)
            
            # Do not auto-load session here; BrowserManager orchestrates per-profile loading
            
            self.initialized = True
            logger.info("SeleniumAdapter: Chrome WebDriver initialized")
        except Exception as e:
            logger.error(f"SeleniumAdapter: Failed to initialize Chrome WebDriver: {e}")
            raise
    
    async def close(self) -> None:
        """Close the WebDriver."""
        if self.driver:
            logger.info("SeleniumAdapter: Closing WebDriver...")
            try:
                # Do not auto-save here; BrowserManager handles profile-targeted saving
                
                self.driver.quit()
            except Exception as e:
                logger.warning(f"Warning during driver cleanup: {e}")
            finally:
                self.driver = None
                self.initialized = False
            logger.info("SeleniumAdapter: WebDriver closed")
    
    def _get_by_locator(self, selector: str, selector_type: SelectorType) -> tuple:
        """Convert selector to Selenium By locator."""
        if selector_type == SelectorType.CSS:
            return (By.CSS_SELECTOR, selector)
        elif selector_type == SelectorType.XPATH:
            return (By.XPATH, selector)
        elif selector_type == SelectorType.ID:
            return (By.ID, selector.lstrip('#'))
        elif selector_type == SelectorType.CLASS_NAME:
            return (By.CLASS_NAME, selector.lstrip('.'))
        elif selector_type == SelectorType.TAG_NAME:
            return (By.TAG_NAME, selector)
        elif selector_type == SelectorType.NAME:
            return (By.NAME, selector)
        elif selector_type == SelectorType.LINK_TEXT:
            return (By.LINK_TEXT, selector)
        elif selector_type == SelectorType.PARTIAL_LINK_TEXT:
            return (By.PARTIAL_LINK_TEXT, selector)
        else:
            # Default to CSS selector
            return (By.CSS_SELECTOR, selector)
    
    def _find_element(self, params: BrowserActionParams):
        """Find element with selector chain, using cache for optimization.
        
        Cache strategy:
        1. Check if we have a cached successful selector for this chain
        2. If yes, try it first (fast path)
        3. If cached selector fails, invalidate and try full chain (skipping the failed cached one)
        4. When any selector succeeds, cache it for next time
        """
        self._require_selector(params)
        selector_chain = self._selector_chain(params)
        timeout = params.timeout or self.default_timeout
        
        # Get current URL for cache lookups
        try:
            current_url = self.driver.current_url if self.driver else ""
        except AttributeError:
            current_url = ""
        
        # Use first selector as cache key for this chain
        cache_key = selector_chain[0]
        
        # Track which selector to skip (if cached one failed)
        skip_selector: Optional[str] = None
        
        # Fast path: try cached successful selector first
        cached_selector = self.selector_cache.get_cached_selector(cache_key, current_url)
        if cached_selector:
            try:
                by, value = self._get_by_locator(cached_selector, params.selector_type)
                element = self._wait_for_presence(by, value, timeout)
                logger.debug(f"SeleniumAdapter: Cache hit - using '{cached_selector}'")
                return element, cached_selector
            except (TimeoutException, NoSuchElementException):
                # Cached selector no longer works - invalidate and try full chain
                logger.info(f"SeleniumAdapter: Cached selector '{cached_selector}' failed, trying other selectors")
                self.selector_cache.invalidate(cache_key, current_url)
                skip_selector = cached_selector  # Don't try it again in the loop below
            except WebDriverException as e:
                raise ExternalOperationTransientError(
                    f"WebDriver issue while searching for cached selector '{cached_selector}': {str(e)}",
                    retry_history=[],
                    original_error=e
                )
        
        # Full chain: try each selector in order (skipping the one that just failed from cache)
        last_error: Optional[Exception] = None
        last_selector = selector_chain[-1]

        for selector in selector_chain:
            # Skip the cached selector that already failed
            if skip_selector and selector == skip_selector:
                logger.debug(f"SeleniumAdapter: Skipping '{selector}' (already tried from cache)")
                continue
            
            try:
                by, value = self._get_by_locator(selector, params.selector_type)
                # Use scope element if provided
                element = self._wait_for_presence(by, value, timeout, scope_element=params.scope_element_handle)
                
                # Success! Cache this selector for next time
                self.selector_cache.cache_successful(cache_key, selector, current_url)
                
                if selector != selector_chain[0]:
                    logger.info(
                        "SeleniumAdapter: Primary selector '%s' failed, using fallback '%s'",
                        selector_chain[0],
                        selector,
                    )
                return element, selector
            except (TimeoutException, NoSuchElementException) as e:
                last_error = e
                last_selector = selector
                logger.debug("SeleniumAdapter: Selector '%s' did not match: %s", selector, e)
                continue
            except WebDriverException as e:
                raise ExternalOperationTransientError(
                    f"WebDriver issue while searching for '{selector}': {str(e)}",
                    retry_history=[],
                    original_error=e
                )
            except Exception as e:
                raise ExternalOperationPermanentError(f"Permanent error: {str(e)}", retry_history=[], original_error=e)

        # All selectors failed
        if last_error:
            self._raise_dom_classified_error(f"Element '{last_selector}' not found", last_error)

        raise ExternalOperationPermanentError(
            "No selector could be resolved for this browser action",
            retry_history=[]
        )

    def _wait_for_presence(self, by, value, timeout, scope_element=None):
        """Wait for element presence, optionally scoped to a parent element.
        
        Args:
            by: Selenium By locator type
            value: Locator value
            timeout: Timeout in seconds
            scope_element: Optional WebElement to search within
        """
        if scope_element:
            # Search within the scoped element
            def find_in_scope(driver):
                return scope_element.find_element(by, value)
            return WebDriverWait(self.driver, timeout).until(find_in_scope)
        else:
            # Global search
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
    
    async def navigate(self, params: BrowserActionParams) -> None:
        """Navigate to a URL."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        url = params.value
        logger.info(f"SeleniumAdapter: Navigate to {url}")
        self.driver.get(url)
        
        # Wait for page to fully load
        try:
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            logger.info(f"SeleniumAdapter: Page loaded. Current URL: {self.driver.current_url}, Title: {self.driver.title}")
            self._ensure_dom_tracker()
        except Exception as e:
            logger.warning(f"Page load wait timed out or failed: {e}")
            logger.warning(f"Current URL: {self.driver.current_url}, Title: {self.driver.title}")
    
    async def click(self, params: BrowserActionParams) -> None:
        """Click an element."""
        if not self.initialized:
            raise ExternalOperationPermanentError("SeleniumAdapter not initialized", retry_history=[])
        
        selector = self._require_selector(params)
        logger.info(f"SeleniumAdapter: Click element {selector}")
        element, active_selector = self._find_element(params)
        if active_selector != selector:
            logger.info(f"SeleniumAdapter: Using fallback selector {active_selector}")
        
        # Wait for element to be clickable
        try:
            timeout = params.timeout or self.default_timeout
            by, value = self._get_by_locator(active_selector, params.selector_type)
            WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
            
            element.click()
            logger.info(f"SeleniumAdapter: Successfully clicked {active_selector}")
            
            # Wait for DOM stabilization after click
            self._wait_for_dom_stability()
        except (TimeoutException, NoSuchElementException) as e:
            self._raise_dom_classified_error(f"Element '{active_selector}' not clickable: {str(e)}", e)
        except WebDriverException as e:
            raise ExternalOperationTransientError(f"Click failed: {str(e)}", retry_history=[], original_error=e)
        except Exception as e:
            raise ExternalOperationPermanentError(f"Click error: {str(e)}", retry_history=[], original_error=e)
    
    async def type_text(self, params: BrowserActionParams) -> None:
        """Type text into an element."""
        if not self.initialized:
            raise ExternalOperationPermanentError("SeleniumAdapter not initialized", retry_history=[])
        
        text = params.value
        element, active_selector = self._find_element(params)
        logger.info(f"SeleniumAdapter: Type '{text}' into {active_selector}")
        
        try:
            # Clear existing text and type new text
            element.clear()
            element.send_keys(text)
        except WebDriverException as e:
            raise ExternalOperationTransientError(f"Type text failed: {str(e)}", retry_history=[], original_error=e)
        except Exception as e:
            raise ExternalOperationPermanentError(f"Type text error: {str(e)}", retry_history=[], original_error=e)
    
    async def upload_file(self, params: BrowserActionParams) -> None:
        """Upload a file to a file input element."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        if not params.value:
            raise ValueError("File path is required for upload_file action")
        
        file_path = params.value
        
        # Find the file input element
        element, active_selector = self._find_element(params)
        
        logger.info(f"SeleniumAdapter: Upload file '{file_path}' to {active_selector}")
        
        try:
            # Send the file path to the input element
            # Selenium handles the file upload dialog automatically
            element.send_keys(file_path)
        except WebDriverException as e:
            raise ExternalOperationTransientError(f"File upload failed: {str(e)}", retry_history=[], original_error=e)
        except Exception as e:
            raise ExternalOperationPermanentError(f"File upload error: {str(e)}", retry_history=[], original_error=e)
    
    async def wait_for_element(self, params: BrowserActionParams) -> None:
        """Wait for an element to meet a condition."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        timeout = params.timeout or self.default_timeout
        condition = params.wait_condition or "visible"
        
        selector_chain = self._selector_chain(params)
        last_error: Optional[Exception] = None
        last_selector = selector_chain[-1]

        for selector in selector_chain:
            logger.info(f"SeleniumAdapter: Wait for {selector} to be {condition}")
            by, value = self._get_by_locator(selector, params.selector_type)
            try:
                if condition == "visible":
                    WebDriverWait(self.driver, timeout).until(
                        EC.visibility_of_element_located((by, value))
                    )
                    return
                elif condition == "clickable":
                    WebDriverWait(self.driver, timeout).until(
                        EC.element_to_be_clickable((by, value))
                    )
                    return
                elif condition == "present":
                    WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_element_located((by, value))
                    )
                    return
                elif condition == "hidden":
                    WebDriverWait(self.driver, timeout).until(
                        EC.invisibility_of_element_located((by, value))
                    )
                    return
            except (TimeoutException, NoSuchElementException) as e:
                last_error = e
                last_selector = selector
                continue
        
        if last_error:
            self._raise_dom_classified_error(
                f"Condition '{condition}' not met for '{last_selector}'",
                last_error
            )
    
    async def get_text(self, params: BrowserActionParams) -> str:
        """Get text content of an element."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        element, active_selector = self._find_element(params)
        logger.info(f"SeleniumAdapter: Get text from {active_selector}")
        return element.text
    
    async def get_elements(self, params: BrowserActionParams) -> List[Any]:
        """Get multiple elements matching selector.
        
        Returns list of Selenium WebElement objects that can be used for scoping.
        """
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        selector = self._require_selector(params)
        timeout = params.timeout or self.default_timeout
        
        # Use scope element if provided
        search_root = params.scope_element_handle if params.scope_element_handle else self.driver
        
        # Try all selectors in fallback chain
        selector_chain = [selector]
        if params.fallback_selectors:
            selector_chain.extend(params.fallback_selectors)
        
        for sel in selector_chain:
            try:
                by, value = self._get_by_locator(sel, params.selector_type)
                
                # Wait for at least one element to be present
                if params.scope_element_handle:
                    def find_in_scope(driver):
                        elements = search_root.find_elements(by, value)
                        return elements if elements else False
                    elements = WebDriverWait(self.driver, timeout).until(find_in_scope)
                else:
                    WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_element_located((by, value))
                    )
                    elements = search_root.find_elements(by, value)
                
                logger.info(f"SeleniumAdapter: Found {len(elements)} elements matching '{sel}'")
                return elements
                
            except (TimeoutException, NoSuchElementException) as e:
                logger.debug(f"SeleniumAdapter: Selector '{sel}' did not match: {e}")
                continue
        
        # All selectors failed
        raise ExternalOperationPermanentError(
            f"No elements found matching '{selector}' (or fallbacks)",
            retry_history=[]
        )
    
    async def get_attribute(self, params: BrowserActionParams) -> str:
        """Get attribute value of an element."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        attribute_name = params.value
        element, active_selector = self._find_element(params)
        logger.info(f"SeleniumAdapter: Get attribute '{attribute_name}' from {active_selector}")
        return element.get_attribute(attribute_name) or ""
    
    async def is_visible(self, params: BrowserActionParams) -> bool:
        """Check if an element is visible."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        element, active_selector = self._find_element(params)
        try:
            visible = element.is_displayed()
            logger.info(f"SeleniumAdapter: Check if {active_selector} is visible -> {visible}")
            return visible
        except WebDriverException as e:
            raise ExternalOperationTransientError(
                f"Visibility check failed for '{active_selector}': {e}",
                retry_history=[],
                original_error=e
            )
    
    async def is_enabled(self, params: BrowserActionParams) -> bool:
        """Check if an element is enabled."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        element, active_selector = self._find_element(params)
        try:
            enabled = element.is_enabled()
            logger.info(f"SeleniumAdapter: Check if {active_selector} is enabled -> {enabled}")
            return enabled
        except (NoSuchElementException, WebDriverException) as e:
            raise ExternalOperationTransientError(
                f"Enablement check failed for '{active_selector}': {e}",
                retry_history=[],
                original_error=e
            )
    
    async def hover(self, params: BrowserActionParams) -> None:
        """Hover over an element."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        element, active_selector = self._find_element(params)
        logger.info(f"SeleniumAdapter: Hover over {active_selector}")
        
        actions = ActionChains(self.driver)
        actions.move_to_element(element).perform()
    
    async def scroll(self, params: BrowserActionParams) -> None:
        """Scroll to an element."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        element, active_selector = self._find_element(params)
        logger.info(f"SeleniumAdapter: Scroll to {active_selector}")
        
        # Scroll element into view
        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
        time.sleep(0.5)  # Small delay for smooth scrolling
    
    async def select_option(self, params: BrowserActionParams) -> None:
        """Select an option from a dropdown."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        option_value = params.value
        selector = self._require_selector(params)
        element, active_selector = self._find_element(params)
        logger.info(f"SeleniumAdapter: Select option '{option_value}' in {active_selector}")
        
        select = Select(element)
        try:
            # Try to select by visible text first
            select.select_by_visible_text(option_value)
        except NoSuchElementException:
            # If that fails, try by value
            try:
                select.select_by_value(option_value)
            except NoSuchElementException as e:
                self._raise_dom_classified_error(
                    f"Option '{option_value}' not found for '{active_selector}'",
                    e
                )
    
    async def submit_form(self, params: BrowserActionParams) -> None:
        """Submit a form."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        element, active_selector = self._find_element(params)
        logger.info(f"SeleniumAdapter: Submit form {active_selector}")
        element.submit()
    
    async def take_screenshot(self, params: BrowserActionParams) -> str:
        """Take a screenshot."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        file_path = params.value or f"screenshot_{int(time.time())}.png"
        logger.info(f"SeleniumAdapter: Take screenshot -> {file_path}")
        
        self.driver.save_screenshot(file_path)
        return file_path
    
    async def get_page_source(self) -> str:
        """Get the current page HTML source."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        return self.driver.page_source
    
    def _wait_for_dom_stability(self, timeout: float = 2.0, check_interval: float = 0.1):
        """Wait for DOM to stabilize after a click action."""
        logger.info("SeleniumAdapter: Waiting for DOM stability after click")
        try:
            self._ensure_dom_tracker()
            start_time = time.time()
            stable_checks = 0
            
            while time.time() - start_time < timeout:
                if self._is_dom_stable_sync():
                    stable_checks += 1
                    if stable_checks >= 3:
                        elapsed = time.time() - start_time
                        logger.info(f"SeleniumAdapter: DOM stabilized in {elapsed:.2f}s")
                        return
                else:
                    stable_checks = 0
                
                time.sleep(check_interval)
            
            logger.warning("SeleniumAdapter: DOM stability wait timed out, proceeding anyway")
            
        except Exception as e:
            # Fallback to simple sleep if JavaScript execution fails
            logger.warning(f"SeleniumAdapter: DOM stability check failed ({e}), using fallback wait")
            time.sleep(0.5)
    
    def _load_session_data(self):
        """Load session data (cookies) from files."""
        print(f"TO DELETE: _load_session_data called with profile_name: {self.profile_name}")
        if not self.session_manager or not self.session_manager.enabled or not self.driver:
            print(f"TO DELETE: Not loading session data - session_manager: {self.session_manager}, enabled: {self.session_manager.enabled if self.session_manager else None}, driver: {bool(self.driver)}")
            return
        
        try:
            # Load and add cookies - need to navigate to domain first
            print(f"TO DELETE: About to load cookies for profile: {self.profile_name}")
            cookies = self.session_manager.load_cookies(self.profile_name)
            print(f"TO DELETE: Loaded {len(cookies) if cookies else 0} cookies")
            if cookies:
                # Group cookies by domain
                domain_cookies = {}
                for cookie in cookies:
                    domain = cookie.get('domain', '').lstrip('.')
                    if domain:
                        if domain not in domain_cookies:
                            domain_cookies[domain] = []
                        domain_cookies[domain].append(cookie)
                
                # Load cookies for each domain
                for domain, cookies_for_domain in domain_cookies.items():
                    try:
                        # Navigate to domain to set cookies
                        self.driver.get(f"https://{domain}")
                        WebDriverWait(self.driver, 10).until(
                            lambda driver: driver.execute_script("return document.readyState") == "complete"
                        )
                        
                        # Add cookies for this domain
                        for cookie in cookies_for_domain:
                            try:
                                # Keep all important cookie attributes for proper handling
                                clean_cookie = {k: v for k, v in cookie.items() 
                                              if k in ['name', 'value', 'domain', 'path', 'secure', 'httpOnly', 'expiry']}
                                self.driver.add_cookie(clean_cookie)
                            except Exception as e:
                                logger.debug(f"Could not add cookie {cookie.get('name')}: {e}")
                        
                        logger.info(f"Loaded {len(cookies_for_domain)} cookies for domain: {domain}")
                        
                        # Restore localStorage for this domain if available
                        try:
                            local_storage = self.session_manager.load_local_storage(self.profile_name)
                            if local_storage:
                                self.driver.execute_script(
                                    """
                                    var items = arguments[0];
                                    for (var k in items) {
                                        try { localStorage.setItem(k, items[k]); } catch(e) {}
                                    }
                                    """,
                                    local_storage
                                )
                                logger.info(f"Restored {len(local_storage)} localStorage items for domain: {domain}")
                        except Exception as e:
                            logger.debug(f"Could not restore localStorage for domain {domain}: {e}")
                        
                        # Refresh to activate cookies
                        self.driver.refresh()
                        WebDriverWait(self.driver, 10).until(
                            lambda driver: driver.execute_script("return document.readyState") == "complete"
                        )
                        
                    except Exception as e:
                        logger.debug(f"Could not load cookies for domain {domain}: {e}")
            
            # Give the final page time to fully render with authentication
            # This prevents race conditions where validation probe runs before page content loads
            time.sleep(2)
            logger.info(f"Session cookies loaded and page stabilized")
            
            # Update session last used time
            self.session_manager.update_last_used(self.profile_name)
            
        except Exception as e:
            logger.warning(f"Failed to load session data for profile '{self.profile_name}': {e}")
    
    def _save_session_data(self):
        """Save session data (cookies) to files."""
        if not self.session_manager or not self.session_manager.enabled or not self.driver:
            return
        
        try:
            # Save cookies
            cookies = self.driver.get_cookies()
            self.session_manager.save_cookies(self.profile_name, cookies)
            
            # Save local storage if possible
            try:
                local_storage = self.driver.execute_script("""
                    var storage = {};
                    try {
                        for (var i = 0; i < localStorage.length; i++) {
                            var key = localStorage.key(i);
                            storage[key] = localStorage.getItem(key);
                        }
                    } catch (e) {}
                    return storage;
                """)
                self.session_manager.save_local_storage(self.profile_name, local_storage)
            except Exception as e:
                logger.debug(f"Could not save local storage: {e}")
            
            # Update session info
            self.session_manager.save_session_info(self.profile_name, {
                'browser_engine': 'selenium',
                'cookies_count': len(cookies)
            })
            
        except Exception as e:
            logger.warning(f"Failed to save session data for profile '{self.profile_name}': {e}")
    
    # --- New profile/state contract ---
    def set_profile(self, profile_name: Optional[str]) -> None:
        self.profile_name = profile_name or "default"

    async def get_current_url(self) -> Optional[str]:
        """Get the current page URL."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        if self.driver:
            return self.driver.current_url
        else:
            return None

    async def load_session_state(self) -> None:
        # Ensure driver is ready
        if not self.initialized:
            return
        self._load_session_data()

    async def save_session_state(self) -> None:
        if not self.initialized:
            return
        self._save_session_data()

