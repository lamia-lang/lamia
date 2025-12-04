"""Web automation actions including browser and HTTP operations with excellent IntelliSense support."""

from typing import Optional, Dict, Any, Union, Tuple
from lamia.internal_types import BrowserAction, BrowserActionType, BrowserActionParams, SelectorType
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
    
    def click(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        return self._create_web_command(WebActionType.CLICK, selector, fallback_selectors, timeout, None)
        
    def type_text(self, selector: str, text: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        return self._create_web_command(WebActionType.TYPE, selector, fallback_selectors, timeout, text)
    
    def wait_for(self, selector: str, condition: str = "visible", *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        return self._create_web_command(WebActionType.WAIT, selector, fallback_selectors, timeout, condition)
    
    def get_text(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        return self._create_web_command(WebActionType.GET_TEXT, selector, fallback_selectors, timeout, None)
    
    def hover(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        return self._create_web_command(WebActionType.HOVER, selector, fallback_selectors, timeout, None)
    
    def scroll_to(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        return self._create_web_command(WebActionType.SCROLL, selector, fallback_selectors, timeout, None)
    
    def select_option(self, selector: str, option_value: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        return self._create_web_command(WebActionType.SELECT, selector, fallback_selectors, timeout, option_value)
    
    def submit_form(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        return self._create_web_command(WebActionType.SUBMIT, selector, fallback_selectors, timeout, None)
    
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
        return self._create_web_command(WebActionType.IS_VISIBLE, selector, fallback_selectors, timeout, None)
    
    def is_enabled(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        return self._create_web_command(WebActionType.IS_ENABLED, selector, fallback_selectors, timeout, None)
    
    def upload_file(self, file_path: str, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        """Upload a file to a file input element.
        
        Args:
            file_path: Absolute path to the file to upload
            selector: CSS selector for the file input element (usually input[type='file'])
            fallback_selectors: Alternative selectors to try if the primary selector fails
            timeout: Optional timeout in seconds
            
        Returns:
            WebCommand configured for file upload
            
        Example:
            web.upload_file("/Users/john/Documents/resume.pdf", "input[type='file']")
            web.upload_file("/path/to/file.pdf", "input[name='file']", "input[type='file']", ".file-input")
        """
        return self._create_web_command(WebActionType.UPLOAD_FILE, selector, fallback_selectors, timeout, file_path)
    
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
    
    def _create_web_command(self, action: WebActionType, selector: str, fallback_selectors: Tuple[str, ...], timeout: Optional[float] = None, value: Optional[str] = None) -> WebCommand:
        fallbacks = list(fallback_selectors) if fallback_selectors else None
        
        return WebCommand(
            action=action,
            selector=selector,
            fallback_selectors=fallbacks,
            value=value,
            timeout=timeout
        )