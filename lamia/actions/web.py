"""Web automation actions including browser and HTTP operations with excellent IntelliSense support."""

from typing import Optional, Dict, Any, Union, Tuple, List
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
    
    Can be used globally (web.click()) or scoped to elements (field.click()).
    
    Access via: web.click(), web.type_text(), web.wait_for(), etc.
    """
    
    def __init__(self, element_handle: Optional[Any] = None):
        """Initialize WebActions, optionally scoped to an element.
        
        Args:
            element_handle: Optional Selenium WebElement or Playwright ElementHandle
                          to scope all operations to. If None, operations are global.
        """
        self._element_handle = element_handle
    
    def get_element(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> 'WebActions':
        """Get a single element as a scoped WebActions instance.
        
        Returns a new WebActions object that operates only within the found element.
        The adapter will find the element and return a handle that's used for scoping.
        
        Args:
            selector: CSS selector to find the element
            fallback_selectors: Alternative selectors to try
            timeout: Optional timeout in seconds
            
        Returns:
            New WebActions instance scoped to the found element
            
        Example:
            modal = web.get_element("div.modal")
            modal.click("button")  # Clicks button within the modal only
            
            field = web.get_element("div.form-field:nth-child(2)")
            field.get_text("label")  # Gets label within that specific field
        """
        # This will be handled by the web manager:
        # 1. Execute command to find element
        # 2. Adapter returns element handle (WebElement/ElementHandle)
        # 3. Manager wraps in new WebActions(element_handle=handle)
        command = self._create_web_command(
            WebActionType.GET_ELEMENTS,  # Reuse GET_ELEMENTS 
            selector,
            fallback_selectors,
            timeout,
            None,
            scope_element=self._element_handle
        )
        return command  # type: ignore  # Manager will return WebActions
    
    def get_elements(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> List['WebActions']:
        """Get multiple elements as scoped WebActions instances.
        
        Returns a list of WebActions objects, each scoped to one matched element.
        The adapter finds all matching elements and returns handles.
        
        Args:
            selector: CSS selector to find elements
            fallback_selectors: Alternative selectors to try
            timeout: Optional timeout in seconds
            
        Returns:
            List of WebActions instances, each scoped to one element
            
        Example:
            fields = web.get_elements("div.form-field")
            for field in fields:
                q = field.get_text("label")
                field.type_text("input", answer)
        """
        # This will be handled by the web manager:
        # 1. Execute command to find all elements
        # 2. Adapter returns list of element handles
        # 3. Manager wraps each in WebActions(element_handle=handle)
        command = self._create_web_command(
            WebActionType.GET_ELEMENTS, 
            selector, 
            fallback_selectors, 
            timeout, 
            None,
            scope_element=self._element_handle
        )
        return command  # type: ignore  # Manager will return List[WebActions]
    
    def click(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        return self._create_web_command(WebActionType.CLICK, selector, fallback_selectors, timeout, None, scope_element=self._element_handle)
        
    def type_text(self, selector: str, text: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        return self._create_web_command(WebActionType.TYPE, selector, fallback_selectors, timeout, text, scope_element=self._element_handle)
    
    def wait_for(self, selector: str, condition: str = "visible", *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        return self._create_web_command(WebActionType.WAIT, selector, fallback_selectors, timeout, condition, scope_element=self._element_handle)
    
    def get_text(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        return self._create_web_command(WebActionType.GET_TEXT, selector, fallback_selectors, timeout, None, scope_element=self._element_handle)
    
    def hover(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        return self._create_web_command(WebActionType.HOVER, selector, fallback_selectors, timeout, None, scope_element=self._element_handle)
    
    def scroll_to(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        return self._create_web_command(WebActionType.SCROLL, selector, fallback_selectors, timeout, None, scope_element=self._element_handle)
    
    def select_option(self, selector: str, option_value: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        return self._create_web_command(WebActionType.SELECT, selector, fallback_selectors, timeout, option_value, scope_element=self._element_handle)
    
    def submit_form(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        return self._create_web_command(WebActionType.SUBMIT, selector, fallback_selectors, timeout, None, scope_element=self._element_handle)
    
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
        return self._create_web_command(WebActionType.IS_VISIBLE, selector, fallback_selectors, timeout, None, scope_element=self._element_handle)
    
    def is_enabled(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        return self._create_web_command(WebActionType.IS_ENABLED, selector, fallback_selectors, timeout, None, scope_element=self._element_handle)
    
    def is_checked(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        """Check if a checkbox or radio button is checked.
        
        Args:
            selector: CSS selector for the checkbox/radio input
            fallback_selectors: Alternative selectors
            timeout: Optional timeout in seconds
            
        Returns:
            WebCommand that will return boolean
            
        Example:
            if web.is_checked("input[type='checkbox']"):
                print("Checkbox is checked")
        """
        return self._create_web_command(WebActionType.IS_CHECKED, selector, fallback_selectors, timeout, None, scope_element=self._element_handle)
    
    def get_input_type(self, selector: str = "input, select, textarea", *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        """Detect the type of an input element.
        
        Returns InputType enum value (as string): TEXT, EMAIL, TEL, NUMBER, PASSWORD, URL, 
        SEARCH, DATE, TIME, DATETIME_LOCAL, MONTH, WEEK, FILE, CHECKBOX, RADIO, COLOR, 
        RANGE, SELECT, TEXTAREA, BUTTON, SUBMIT, RESET, HIDDEN, UNKNOWN
        
        Args:
            selector: CSS selector for input element (defaults to common input types)
            fallback_selectors: Alternative selectors
            timeout: Optional timeout in seconds
            
        Returns:
            WebCommand that will return InputType enum value as string
            
        Example:
            from lamia import InputType  # Or auto-injected in .hu files
            
            field = web.get_element("div.form-field")
            input_type = field.get_input_type()
            
            if input_type == InputType.TEXT:
                field.type_text("input", "answer")
            elif input_type == InputType.FILE:
                field.upload_file("input", "~/file.pdf")
            elif input_type == InputType.CHECKBOX:
                if not field.is_checked("input"):
                    field.click("input")
        """
        return self._create_web_command(WebActionType.GET_INPUT_TYPE, selector, fallback_selectors, timeout, None, scope_element=self._element_handle)
    
    def get_attribute(self, selector: str, attribute_name: str, *fallback_selectors: str, timeout: Optional[float] = None) -> WebCommand:
        """Get an attribute value from an element.
        
        Args:
            selector: CSS selector for the element
            attribute_name: Name of the attribute to get (e.g., "href", "class", "data-id")
            fallback_selectors: Alternative selectors
            timeout: Optional timeout in seconds
            
        Returns:
            WebCommand that will return attribute value string
            
        Example:
            href = web.get_attribute("a.link", "href")
            data_id = web.get_attribute("div", "data-id")
        """
        return self._create_web_command(WebActionType.GET_ATTRIBUTE, selector, fallback_selectors, timeout, attribute_name, scope_element=self._element_handle)
    
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
        return self._create_web_command(WebActionType.UPLOAD_FILE, selector, fallback_selectors, timeout, file_path, scope_element=self._element_handle)
    
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
    
    def _create_web_command(self, action: WebActionType, selector: str, fallback_selectors: Tuple[str, ...], timeout: Optional[float] = None, value: Optional[str] = None, scope_element: Optional[Any] = None) -> WebCommand:
        fallbacks = list(fallback_selectors) if fallback_selectors else None
        
        return WebCommand(
            action=action,
            selector=selector,
            fallback_selectors=fallbacks,
            value=value,
            timeout=timeout,
            scope_element_handle=scope_element  # Pass the element handle for scoping
        )