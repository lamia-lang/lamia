"""Real Selenium adapter for browser automation."""

from .base import BaseBrowserAdapter
from lamia.errors import ExternalOperationTransientError, ExternalOperationPermanentError
from lamia.types import BrowserActionParams, SelectorType
import logging
from typing import Optional
import time

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
    
    def __init__(self, headless: bool = True, timeout: float = 10.0):
        self.driver = None
        self.headless = headless
        self.default_timeout = timeout
        self.initialized = False
    
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
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(self.default_timeout)
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
        """Find element with single selector, translating exceptions to semantic types."""
        timeout = params.timeout or self.default_timeout
        
        try:
            by, value = self._get_by_locator(params.selector, params.selector_type)
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except (TimeoutException, NoSuchElementException) as e:
            # Selector-related errors - let retry handler exhaust retries, then try next selector
            raise ExternalOperationTransientError(f"Element '{params.selector}' not found: {str(e)}", retry_history=[], original_error=e)
        except WebDriverException as e:
            # Browser/driver issues - retry same selector
            raise ExternalOperationTransientError(f"WebDriver issue: {str(e)}", retry_history=[], original_error=e)
        except Exception as e:
            # Other permanent failures
            raise ExternalOperationPermanentError(f"Permanent error: {str(e)}", retry_history=[], original_error=e)
    
    async def navigate(self, params: BrowserActionParams) -> None:
        """Navigate to a URL."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        url = params.value
        logger.info(f"SeleniumAdapter: Navigate to {url}")
        self.driver.get(url)
    
    async def click(self, params: BrowserActionParams) -> None:
        """Click an element."""
        if not self.initialized:
            raise ExternalOperationPermanentError("SeleniumAdapter not initialized", retry_history=[])
        
        logger.info(f"SeleniumAdapter: Click element {params.selector}")
        
        element = self._find_element(params)
        
        # Wait for element to be clickable
        try:
            timeout = params.timeout or self.default_timeout
            by, value = self._get_by_locator(params.selector, params.selector_type)
            WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
            
            element.click()
            logger.info(f"SeleniumAdapter: Successfully clicked {params.selector}")
        except (TimeoutException, NoSuchElementException) as e:
            raise ExternalOperationTransientError(f"Element '{params.selector}' not clickable: {str(e)}", retry_history=[], original_error=e)
        except WebDriverException as e:
            raise ExternalOperationTransientError(f"Click failed: {str(e)}", retry_history=[], original_error=e)
        except Exception as e:
            raise ExternalOperationPermanentError(f"Click error: {str(e)}", retry_history=[], original_error=e)
    
    async def type_text(self, params: BrowserActionParams) -> None:
        """Type text into an element."""
        if not self.initialized:
            raise ExternalOperationPermanentError("SeleniumAdapter not initialized", retry_history=[])
        
        text = params.value
        logger.info(f"SeleniumAdapter: Type '{text}' into {params.selector}")
        
        element = self._find_element(params)
        
        try:
            # Clear existing text and type new text
            element.clear()
            element.send_keys(text)
        except WebDriverException as e:
            raise ExternalOperationTransientError(f"Type text failed: {str(e)}", retry_history=[], original_error=e)
        except Exception as e:
            raise ExternalOperationPermanentError(f"Type text error: {str(e)}", retry_history=[], original_error=e)
    
    async def wait_for_element(self, params: BrowserActionParams) -> None:
        """Wait for an element to meet a condition."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        timeout = params.timeout or self.default_timeout
        condition = params.wait_condition or "visible"
        
        logger.info(f"SeleniumAdapter: Wait for {params.selector} to be {condition}")
        
        by, value = self._get_by_locator(params.selector, params.selector_type)
        
        if condition == "visible":
            WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located((by, value))
            )
        elif condition == "clickable":
            WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
        elif condition == "present":
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
        elif condition == "hidden":
            WebDriverWait(self.driver, timeout).until(
                EC.invisibility_of_element_located((by, value))
            )
    
    async def get_text(self, params: BrowserActionParams) -> str:
        """Get text content of an element."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        logger.info(f"SeleniumAdapter: Get text from {params.selector}")
        element = self._find_element(params)
        return element.text
    
    async def get_attribute(self, params: BrowserActionParams) -> str:
        """Get attribute value of an element."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        attribute_name = params.value
        logger.info(f"SeleniumAdapter: Get attribute '{attribute_name}' from {params.selector}")
        element = self._find_element(params)
        return element.get_attribute(attribute_name) or ""
    
    async def is_visible(self, params: BrowserActionParams) -> bool:
        """Check if an element is visible."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        try:
            element = self._find_element(params)
            visible = element.is_displayed()
            logger.info(f"SeleniumAdapter: Check if {params.selector} is visible -> {visible}")
            return visible
        except NoSuchElementException:
            logger.info(f"SeleniumAdapter: Check if {params.selector} is visible -> False (not found)")
            return False
    
    async def is_enabled(self, params: BrowserActionParams) -> bool:
        """Check if an element is enabled."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        try:
            element = self._find_element(params)
            enabled = element.is_enabled()
            logger.info(f"SeleniumAdapter: Check if {params.selector} is enabled -> {enabled}")
            return enabled
        except NoSuchElementException:
            logger.info(f"SeleniumAdapter: Check if {params.selector} is enabled -> False (not found)")
            return False
    
    async def hover(self, params: BrowserActionParams) -> None:
        """Hover over an element."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        logger.info(f"SeleniumAdapter: Hover over {params.selector}")
        element = self._find_element(params)
        
        actions = ActionChains(self.driver)
        actions.move_to_element(element).perform()
    
    async def scroll(self, params: BrowserActionParams) -> None:
        """Scroll to an element."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        logger.info(f"SeleniumAdapter: Scroll to {params.selector}")
        element = self._find_element(params)
        
        # Scroll element into view
        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
        time.sleep(0.5)  # Small delay for smooth scrolling
    
    async def select_option(self, params: BrowserActionParams) -> None:
        """Select an option from a dropdown."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        option_value = params.value
        logger.info(f"SeleniumAdapter: Select option '{option_value}' in {params.selector}")
        element = self._find_element(params)
        
        select = Select(element)
        try:
            # Try to select by visible text first
            select.select_by_visible_text(option_value)
        except NoSuchElementException:
            # If that fails, try by value
            select.select_by_value(option_value)
    
    async def submit_form(self, params: BrowserActionParams) -> None:
        """Submit a form."""
        if not self.initialized:
            raise RuntimeError("SeleniumAdapter not initialized")
        
        logger.info(f"SeleniumAdapter: Submit form {params.selector}")
        element = self._find_element(params)
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