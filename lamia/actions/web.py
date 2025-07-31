"""Browser automation actions with excellent IntelliSense support."""

from typing import Optional
from lamia.types import BrowserAction, BrowserActionType, BrowserActionParams, SelectorType


def _detect_selector_type(selector: str) -> SelectorType:
    """Auto-detect selector type from selector string."""
    if selector.startswith("//"):
        return SelectorType.XPATH
    elif selector.startswith("#"):
        return SelectorType.ID
    elif selector.startswith(".") and " " not in selector and "[" not in selector:
        return SelectorType.CLASS_NAME
    elif ":" in selector and ("contains" in selector or "nth-child" in selector):
        return SelectorType.CSS
    elif "[" in selector and "]" in selector:
        return SelectorType.CSS
    elif " " not in selector and "." not in selector and "#" not in selector and "[" not in selector:
        return SelectorType.TAG_NAME
    else:
        return SelectorType.CSS  # Default to CSS


class WebActions:
    """Browser automation actions with excellent IntelliSense support.
    
    Access via: web.click(), web.type_text(), web.wait_for(), etc.
    """
    
    def click(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> BrowserAction:
        """Click an element with fallback selectors.
        
        Args:
            selector: Primary CSS selector, XPath, or ID (auto-detected)
            *fallback_selectors: Backup selectors if primary fails
            timeout: Optional timeout in seconds
            
        Returns:
            BrowserAction configured for clicking
            
        Example:
            web.click("#submit-btn", ".submit-button", "button[type='submit']")
        """
        fallbacks = list(fallback_selectors) if fallback_selectors else None
        
        return BrowserAction(
            action=BrowserActionType.CLICK,
            params=BrowserActionParams(
                selector=selector,
                selector_type=_detect_selector_type(selector),
                fallback_selectors=fallbacks,
                timeout=timeout
            )
        )
    
    def type_text(self, selector: str, text: str, *fallback_selectors: str, timeout: Optional[float] = None) -> BrowserAction:
        """Type text into an input element.
        
        Args:
            selector: Primary selector for the input field
            text: Text to type into the field
            *fallback_selectors: Backup selectors if primary fails
            timeout: Optional timeout in seconds
            
        Returns:
            BrowserAction configured for typing
            
        Example:
            web.type_text("input[name='username']", "john@example.com", "#username")
        """
        fallbacks = list(fallback_selectors) if fallback_selectors else None
        
        return BrowserAction(
            action=BrowserActionType.TYPE,
            params=BrowserActionParams(
                selector=selector,
                selector_type=_detect_selector_type(selector),
                fallback_selectors=fallbacks,
                value=text,
                timeout=timeout
            )
        )
    
    def wait_for(self, selector: str, condition: str = "visible", *fallback_selectors: str, timeout: Optional[float] = None) -> BrowserAction:
        """Wait for an element to meet a condition.
        
        Args:
            selector: Primary selector for the element
            condition: Condition to wait for (visible, clickable, present, hidden)
            *fallback_selectors: Backup selectors if primary fails
            timeout: Optional timeout in seconds
            
        Returns:
            BrowserAction configured for waiting
            
        Example:
            web.wait_for(".loading-spinner", "hidden", timeout=10.0)
        """
        fallbacks = list(fallback_selectors) if fallback_selectors else None
        
        return BrowserAction(
            action=BrowserActionType.WAIT,
            params=BrowserActionParams(
                selector=selector,
                selector_type=_detect_selector_type(selector),
                fallback_selectors=fallbacks,
                wait_condition=condition,
                timeout=timeout
            )
        )
    
    def get_text(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> BrowserAction:
        """Get text content from an element.
        
        Args:
            selector: Primary selector for the element
            *fallback_selectors: Backup selectors if primary fails
            timeout: Optional timeout in seconds
            
        Returns:
            BrowserAction configured for getting text
            
        Example:
            web.get_text(".job-title", "h1", "[data-testid='job-title']")
        """
        fallbacks = list(fallback_selectors) if fallback_selectors else None
        
        return BrowserAction(
            action=BrowserActionType.GET_TEXT,
            params=BrowserActionParams(
                selector=selector,
                selector_type=_detect_selector_type(selector),
                fallback_selectors=fallbacks,
                timeout=timeout
            )
        )
    
    def hover(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> BrowserAction:
        """Hover over an element to reveal dropdown menus or tooltips.
        
        Args:
            selector: Primary selector for the element
            *fallback_selectors: Backup selectors if primary fails
            timeout: Optional timeout in seconds
            
        Returns:
            BrowserAction configured for hovering
            
        Example:
            web.hover(".menu-item", "[data-menu='dropdown']")
        """
        fallbacks = list(fallback_selectors) if fallback_selectors else None
        
        return BrowserAction(
            action=BrowserActionType.HOVER,
            params=BrowserActionParams(
                selector=selector,
                selector_type=_detect_selector_type(selector),
                fallback_selectors=fallbacks,
                timeout=timeout
            )
        )
    
    def scroll_to(self, selector: str, *fallback_selectors: str) -> BrowserAction:
        """Scroll the page to bring an element into view.
        
        Args:
            selector: Primary selector for the element
            *fallback_selectors: Backup selectors if primary fails
            
        Returns:
            BrowserAction configured for scrolling
            
        Example:
            web.scroll_to("#footer", ".page-footer")
        """
        fallbacks = list(fallback_selectors) if fallback_selectors else None
        
        return BrowserAction(
            action=BrowserActionType.SCROLL,
            params=BrowserActionParams(
                selector=selector,
                selector_type=_detect_selector_type(selector),
                fallback_selectors=fallbacks
            )
        )
    
    def select_option(self, selector: str, option_value: str, *fallback_selectors: str, timeout: Optional[float] = None) -> BrowserAction:
        """Select an option from a dropdown menu.
        
        Args:
            selector: Primary selector for the dropdown element
            option_value: Value or visible text of the option to select
            *fallback_selectors: Backup selectors if primary fails
            timeout: Optional timeout in seconds
            
        Returns:
            BrowserAction configured for selecting
            
        Example:
            web.select_option("select[name='country']", "United States", "#country-select")
        """
        fallbacks = list(fallback_selectors) if fallback_selectors else None
        
        return BrowserAction(
            action=BrowserActionType.SELECT,
            params=BrowserActionParams(
                selector=selector,
                selector_type=_detect_selector_type(selector),
                fallback_selectors=fallbacks,
                value=option_value,
                timeout=timeout
            )
        )
    
    def submit_form(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> BrowserAction:
        """Submit a form by clicking submit button or triggering form submission.
        
        Args:
            selector: Primary selector for the form or submit button
            *fallback_selectors: Backup selectors if primary fails
            timeout: Optional timeout in seconds
            
        Returns:
            BrowserAction configured for form submission
            
        Example:
            web.submit_form("form#login-form", ".login-form")
        """
        fallbacks = list(fallback_selectors) if fallback_selectors else None
        
        return BrowserAction(
            action=BrowserActionType.SUBMIT,
            params=BrowserActionParams(
                selector=selector,
                selector_type=_detect_selector_type(selector),
                fallback_selectors=fallbacks,
                timeout=timeout
            )
        )
    
    def screenshot(self, file_path: Optional[str] = None) -> BrowserAction:
        """Take a screenshot of the current page.
        
        Args:
            file_path: Optional file path to save screenshot (auto-generated if None)
            
        Returns:
            BrowserAction configured for taking screenshot
            
        Example:
            web.screenshot("login_page.png")
        """
        return BrowserAction(
            action=BrowserActionType.SCREENSHOT,
            params=BrowserActionParams(value=file_path)
        )
    
    def is_visible(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> BrowserAction:
        """Check if an element is visible on the page.
        
        Args:
            selector: Primary selector for the element
            *fallback_selectors: Backup selectors if primary fails
            timeout: Optional timeout in seconds
            
        Returns:
            BrowserAction configured for visibility check
            
        Example:
            web.is_visible(".error-message", "#error")
        """
        fallbacks = list(fallback_selectors) if fallback_selectors else None
        
        return BrowserAction(
            action=BrowserActionType.IS_VISIBLE,
            params=BrowserActionParams(
                selector=selector,
                selector_type=_detect_selector_type(selector),
                fallback_selectors=fallbacks,
                timeout=timeout
            )
        )
    
    def is_enabled(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> BrowserAction:
        """Check if an element is enabled and interactive.
        
        Args:
            selector: Primary selector for the element
            *fallback_selectors: Backup selectors if primary fails
            timeout: Optional timeout in seconds
            
        Returns:
            BrowserAction configured for enabled check
            
        Example:
            web.is_enabled("#submit-btn", ".submit-button")
        """
        fallbacks = list(fallback_selectors) if fallback_selectors else None
        
        return BrowserAction(
            action=BrowserActionType.IS_ENABLED,
            params=BrowserActionParams(
                selector=selector,
                selector_type=_detect_selector_type(selector),
                fallback_selectors=fallbacks,
                timeout=timeout
            )
        )