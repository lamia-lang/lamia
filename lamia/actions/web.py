"""Web automation actions including browser and HTTP operations with excellent IntelliSense support."""

from typing import Optional, Dict, Any, Union
from lamia.types import BrowserAction, BrowserActionType, BrowserActionParams, SelectorType
from lamia.interpreter.commands import WebCommand, WebActionType

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
        
        return WebCommand(
            action=WebActionType.CLICK,
            selector=selector,
            timeout=timeout
        )
        
    
    def type_text(self, selector: str, text: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        """Type text into an input element.
        
        Args:
            selector: Primary selector for the input field
            text: Text to type into the field
            *fallback_selectors: Backup selectors if primary fails
            timeout: Optional timeout in seconds
            
        Returns:
            WebCommand configured for typing
            
        Example:
            web.type_text("input[name='username']", "john@example.com", "#username")
        """
        fallbacks = list(fallback_selectors) if fallback_selectors else None
        
        return WebCommand(
            action=WebActionType.TYPE,
            selector=selector,
            value=text,
            timeout=timeout
        )
    
    def wait_for(self, selector: str, condition: str = "visible", *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        """Wait for an element to meet a condition.
        
        Args:
            selector: Primary selector for the element
            condition: Condition to wait for (visible, clickable, present, hidden)
            *fallback_selectors: Backup selectors if primary fails
            timeout: Optional timeout in seconds
            
        Returns:
            WebCommand configured for waiting
            
        Example:
            web.wait_for(".loading-spinner", "hidden", timeout=10.0)
        """
        fallbacks = list(fallback_selectors) if fallback_selectors else None
        
        return WebCommand(
            action=WebActionType.WAIT,
            selector=selector,
            timeout=timeout
        )
    
    def get_text(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        """Get text content from an element.
        
        Args:
            selector: Primary selector for the element
            *fallback_selectors: Backup selectors if primary fails
            timeout: Optional timeout in seconds
            
        Returns:
            WebCommand configured for getting text
            
        Example:
            web.get_text(".job-title", "h1", "[data-testid='job-title']")
        """
        fallbacks = list(fallback_selectors) if fallback_selectors else None
        
        return WebCommand(
            action=WebActionType.GET_TEXT,
            selector=selector,
            timeout=timeout
        )
    
    def hover(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        """Hover over an element to reveal dropdown menus or tooltips.
        
        Args:
            selector: Primary selector for the element
            *fallback_selectors: Backup selectors if primary fails
            timeout: Optional timeout in seconds
            
        Returns:
            WebCommand configured for hovering
            
        Example:
            web.hover(".menu-item", "[data-menu='dropdown']")
        """
        fallbacks = list(fallback_selectors) if fallback_selectors else None
        
        return WebCommand(
            action=WebActionType.HOVER,
            selector=selector,
            timeout=timeout
        )
    
    def scroll_to(self, selector: str, *fallback_selectors: str) -> WebCommand:
        """Scroll the page to bring an element into view.
        
        Args:
            selector: Primary selector for the element
            *fallback_selectors: Backup selectors if primary fails
            
        Returns:
            WebCommand configured for scrolling
            
        Example:
            web.scroll_to("#footer", ".page-footer")
        """
        fallbacks = list(fallback_selectors) if fallback_selectors else None
        
        return WebCommand(
            action=WebActionType.SCROLL,
            selector=selector
        )
    
    def select_option(self, selector: str, option_value: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        """Select an option from a dropdown menu.
        
        Args:
            selector: Primary selector for the dropdown element
            option_value: Value or visible text of the option to select
            *fallback_selectors: Backup selectors if primary fails
            timeout: Optional timeout in seconds
            
        Returns:
            WebCommand configured for selecting
            
        Example:
            web.select_option("select[name='country']", "United States", "#country-select")
        """
        fallbacks = list(fallback_selectors) if fallback_selectors else None
        
        return WebCommand(
            action=WebActionType.SELECT,
            selector=selector,
            value=option_value,
            timeout=timeout
        )
    
    def submit_form(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        """Submit a form by clicking submit button or triggering form submission.
        
        Args:
            selector: Primary selector for the form or submit button
            *fallback_selectors: Backup selectors if primary fails
            timeout: Optional timeout in seconds
            
        Returns:
            WebCommand configured for form submission
            
        Example:
            web.submit_form("form#login-form", ".login-form")
        """
        fallbacks = list(fallback_selectors) if fallback_selectors else None
        
        return WebCommand(
            action=WebActionType.SUBMIT,
            selector=selector,
            timeout=timeout
        )
    
    def screenshot(self, file_path: Optional[str] = None) -> WebCommand:
        """Take a screenshot of the current page.
        
        Args:
            file_path: Optional file path to save screenshot (auto-generated if None)
            
        Returns:
            WebCommand configured for taking screenshot
            
        Example:
            web.screenshot("login_page.png")
        """
        return WebCommand(
            action=WebActionType.SCREENSHOT,
            value=file_path
        )
    
    def is_visible(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        """Check if an element is visible on the page.
        
        Args:
            selector: Primary selector for the element
            *fallback_selectors: Backup selectors if primary fails
            timeout: Optional timeout in seconds
            
        Returns:
            WebCommand configured for visibility check
            
        Example:
            web.is_visible(".error-message", "#error")
        """
        fallbacks = list(fallback_selectors) if fallback_selectors else None
        
        return WebCommand(
            action=WebActionType.IS_VISIBLE,
            selector=selector,
            timeout=timeout
        )
    
    def is_enabled(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        """Check if an element is enabled and interactive.
        
        Args:
            selector: Primary selector for the element
            *fallback_selectors: Backup selectors if primary fails
            timeout: Optional timeout in seconds
            
        Returns:
            WebCommand configured for enabled check
            
        Example:
            web.is_enabled("#submit-btn", ".submit-button")
        """
        fallbacks = list(fallback_selectors) if fallback_selectors else None
        
        return WebCommand(
            action=WebActionType.IS_ENABLED,
            selector=selector,
            timeout=timeout
        )
    
    # HTTP Operations
    def get(self, url: str, headers: Optional[Dict[str, str]] = None, timeout: Optional[float] = None) -> str:
        """Make HTTP GET request.
        
        Args:
            url: URL to request
            headers: Optional HTTP headers
            timeout: Optional timeout in seconds
            
        Returns:
            Command string for lamia.run() to execute
            
        Example:
            response = web.get("https://api.example.com/users", {"Authorization": "Bearer token"})
        """
        import json
        cmd_parts = [f"GET {url}"]
        if headers:
            cmd_parts.append(f"headers:{json.dumps(headers)}")
        if timeout:
            cmd_parts.append(f"timeout:{timeout}")
        return " ".join(cmd_parts)
    
    def post(self, url: str, data: Optional[Union[Dict[str, Any], str]] = None, 
             headers: Optional[Dict[str, str]] = None, timeout: Optional[float] = None) -> str:
        """Make HTTP POST request.
        
        Args:
            url: URL to request  
            data: Request body data (dict for JSON, str for raw)
            headers: Optional HTTP headers
            timeout: Optional timeout in seconds
            
        Returns:
            Command string for lamia.run() to execute
            
        Example:
            response = web.post("https://api.example.com/users", {"name": "John", "email": "john@example.com"})
        """
        import json
        cmd_parts = [f"POST {url}"]
        if data is not None:
            if isinstance(data, dict):
                cmd_parts.append(f"json:{json.dumps(data)}")
            else:
                cmd_parts.append(f"data:{data}")
        if headers:
            cmd_parts.append(f"headers:{json.dumps(headers)}")
        if timeout:
            cmd_parts.append(f"timeout:{timeout}")
        return " ".join(cmd_parts)
    
    def put(self, url: str, data: Optional[Union[Dict[str, Any], str]] = None,
            headers: Optional[Dict[str, str]] = None, timeout: Optional[float] = None) -> str:
        """Make HTTP PUT request.
        
        Args:
            url: URL to request
            data: Request body data (dict for JSON, str for raw)
            headers: Optional HTTP headers
            timeout: Optional timeout in seconds
            
        Returns:
            Command string for lamia.run() to execute
            
        Example:
            response = web.put("https://api.example.com/users/123", {"name": "John Updated"})
        """
        import json
        cmd_parts = [f"PUT {url}"]
        if data is not None:
            if isinstance(data, dict):
                cmd_parts.append(f"json:{json.dumps(data)}")
            else:
                cmd_parts.append(f"data:{data}")
        if headers:
            cmd_parts.append(f"headers:{json.dumps(headers)}")
        if timeout:
            cmd_parts.append(f"timeout:{timeout}")
        return " ".join(cmd_parts)
    
    def delete(self, url: str, headers: Optional[Dict[str, str]] = None, timeout: Optional[float] = None) -> str:
        """Make HTTP DELETE request.
        
        Args:
            url: URL to request
            headers: Optional HTTP headers
            timeout: Optional timeout in seconds
            
        Returns:
            Command string for lamia.run() to execute
            
        Example:
            response = web.delete("https://api.example.com/users/123")
        """
        import json
        cmd_parts = [f"DELETE {url}"]
        if headers:
            cmd_parts.append(f"headers:{json.dumps(headers)}")
        if timeout:
            cmd_parts.append(f"timeout:{timeout}")
        return " ".join(cmd_parts)
    
    def patch(self, url: str, data: Optional[Union[Dict[str, Any], str]] = None,
              headers: Optional[Dict[str, str]] = None, timeout: Optional[float] = None) -> str:
        """Make HTTP PATCH request.
        
        Args:
            url: URL to request
            data: Request body data (dict for JSON, str for raw)
            headers: Optional HTTP headers
            timeout: Optional timeout in seconds
            
        Returns:
            Command string for lamia.run() to execute
            
        Example:
            response = web.patch("https://api.example.com/users/123", {"email": "newemail@example.com"})
        """
        import json
        cmd_parts = [f"PATCH {url}"]
        if data is not None:
            if isinstance(data, dict):
                cmd_parts.append(f"json:{json.dumps(data)}")
            else:
                cmd_parts.append(f"data:{data}")
        if headers:
            cmd_parts.append(f"headers:{json.dumps(headers)}")
        if timeout:
            cmd_parts.append(f"timeout:{timeout}")
        return " ".join(cmd_parts)