"""Web automation actions including browser and HTTP operations with excellent IntelliSense support."""

from typing import Optional, Dict, Any, Union, Tuple, List
from lamia.internal_types import BrowserAction, BrowserActionType, BrowserActionParams, SelectorType
from lamia.interpreter.commands import WebCommand, WebActionType
import asyncio

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
    elif selector.strip() != "" and " " not in selector and "." not in selector and "#" not in selector and "[" not in selector:
        return SelectorType.TAG_NAME
    else:
        return SelectorType.CSS  # Default to CSS


class WebActions:
    """Browser automation actions with excellent IntelliSense support.
    
    Can be used globally (web.click()) or scoped to elements (field.click()).
    
    Access via: web.click(), web.type_text(), web.wait_for(), etc.
    
    ARCHITECTURAL NOTE: EXECUTOR PATTERN
    ====================================
    
    Methods support immediate execution via an executor pattern when called from
    scoped WebActions objects. This is a workaround for a limitation in the hybrid
    syntax transformer.
    
    The transformer only transforms direct 'web.method()' calls to 'lamia.run()',
    but cannot statically detect method calls on variables (e.g., 'field.get_text()').
    When methods are called on scoped objects returned from get_element/get_elements,
    they return WebCommand objects that would never be executed without the executor.
    
    ALL methods that can be called from scoped objects support the executor pattern:
    - Value-returning methods: get_text, get_input_type, get_options, get_attribute,
      is_visible, is_enabled, is_checked (need immediate execution to return values)
    - Action methods: click, type_text, wait_for, hover, scroll_to, select_option,
      submit_form, upload_file (should execute immediately when called on scoped objects)
    
    In an ideal architecture, the engine would handle WebCommand execution
    automatically, eliminating the need for the executor workaround.
    """
    
    def __init__(self, element_handle: Optional[Any] = None, executor: Optional[Any] = None):
        """Initialize WebActions, optionally scoped to an element.
        
        Args:
            element_handle: Optional Selenium WebElement or Playwright ElementHandle
                          to scope all operations to. If None, operations are global.
            executor: Optional execution manager for running commands immediately.
                     Used as a workaround when methods are called on scoped objects
                     (see class docstring for architectural details).
        """
        self._element_handle = element_handle
        self._executor = executor

    def __repr__(self) -> str:
        if self._element_handle is None:
            return "<web global>"
        try:
            tag = self._element_handle.tag_name
            text = (self._element_handle.text or "")[:80]
            el_id = self._element_handle.get_attribute("id") or ""
            el_class = self._element_handle.get_attribute("class") or ""
            parts = [f"<{tag}"]
            if el_id:
                parts.append(f' id="{el_id}"')
            if el_class:
                classes_short = el_class[:50] + ("..." if len(el_class) > 50 else "")
                parts.append(f' class="{classes_short}"')
            parts.append(">")
            desc = "".join(parts)
            if text:
                text_preview = text.replace("\n", " ").strip()[:60]
                desc += f' "{text_preview}"'
            return desc
        except Exception:
            return f"<element@{id(self._element_handle):#x}>"

    def _execute_if_available(self, command: WebCommand, result_processor: Optional[Any] = None):
        """Execute command if executor is available, otherwise return command.
        
        This is a workaround for the transformer limitation where method calls
        on scoped objects (e.g., 'field.get_text()') are not transformed to
        'lamia.run()' calls. When an executor is available, we execute immediately
        to ensure the command runs. Otherwise, we return the WebCommand for
        normal DSL transformation flow.
        
        Args:
            command: WebCommand to execute
            result_processor: Optional callable to process result after extraction
            
        Returns:
            Executed result if executor available, otherwise the command
        """
        if self._executor:
            validation_result = asyncio.run(self._executor.execute(command))
            result = validation_result.result_type if validation_result.result_type is not None else validation_result
            
            if result_processor:
                result = result_processor(result)
            return result
        return command
    
    def get_element(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None):
        """Get a single element as a scoped WebActions instance.
        
        Returns a new WebActions object that operates only within the found element.
        The adapter will find the first matching element and return a handle.
        
        Args:
            selector: CSS selector, XPath, or natural language description
            fallback_selectors: Alternative selectors to try
            timeout: Optional timeout in seconds
            
        Returns:
            New WebActions instance scoped to the found element, or None if not found
            
        Example:
            modal = web.get_element("div.modal")
            if modal:
                modal.click("button")  # Clicks button within the modal only
            
            field = web.get_element("div.form-field:nth-child(2)")
            if field:
                label = field.get_text("label")
        """
        command = self._create_web_command(
            WebActionType.GET_ELEMENT,  # Use GET_ELEMENT (singular)
            selector,
            fallback_selectors,
            timeout,
            None,
            scope_element=self._element_handle
        )
        
        def ensure_executor(result: Any) -> Any:
            if result and hasattr(result, '_executor') and not result._executor:
                result._executor = self._executor
            return result
        
        return self._execute_if_available(command, ensure_executor)  # type: ignore
    
    def get_elements(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None):
        """Get multiple elements as scoped WebActions instances.
        
        Returns a list of WebActions objects, each scoped to one matched element.
        The adapter finds all matching elements and returns handles.
        
        Args:
            selector: CSS selector, XPath, or natural language description
            fallback_selectors: Alternative selectors to try
            timeout: Optional timeout in seconds
            
        Returns:
            List of WebActions instances if executor available, otherwise WebCommand for DSL execution
            
        Example:
            fields = web.get_elements("div.form-field")
            for field in fields:
                q = field.get_text("label")
                field.type_text("input", answer)
            
            # Natural language with cache reset
            buttons = web.get_elements("all submit buttons")
        """
        command = self._create_web_command(
            WebActionType.GET_ELEMENTS,
            selector,
            fallback_selectors,
            timeout,
            None,
            scope_element=self._element_handle
        )
        
        def ensure_executors(result: Any) -> Any:
            if isinstance(result, list):
                for web_action in result:
                    if hasattr(web_action, '_executor') and not web_action._executor:
                        web_action._executor = self._executor
            return result
        
        return self._execute_if_available(command, ensure_executors)  # type: ignore
    
    def click(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None):
        """Click an element.
        
        Args:
            selector: CSS selector, XPath, or natural language description
            fallback_selectors: Alternative selectors to try
            timeout: Optional timeout in seconds
            
        Returns:
            Executed result if executor is available (when called from scoped objects),
            otherwise WebCommand for DSL execution.
        """
        command = self._create_web_command(WebActionType.CLICK, selector, fallback_selectors, timeout, None, scope_element=self._element_handle)
        return self._execute_if_available(command)
        
    def type_text(self, selector: str, text: str, *fallback_selectors: str, timeout: Optional[float] = None):
        """Type text into an input element.
        
        Args:
            selector: CSS selector, XPath, or natural language description
            text: Text to type
            fallback_selectors: Alternative selectors to try
            timeout: Optional timeout in seconds
            
        Returns:
            Executed result if executor is available (when called from scoped objects),
            otherwise WebCommand for DSL execution.
        """
        command = self._create_web_command(WebActionType.TYPE, selector, fallback_selectors, timeout, text, scope_element=self._element_handle)
        return self._execute_if_available(command)
    
    def wait_for(self, selector: str, condition: str = "visible", *fallback_selectors: str, timeout: Optional[float] = None):
        """Wait for an element to meet a condition.
        
        Args:
            selector: CSS selector, XPath, or natural language description
            condition: Condition to wait for (default: "visible")
            fallback_selectors: Alternative selectors to try
            timeout: Optional timeout in seconds
            
        Returns:
            Executed result if executor is available (when called from scoped objects),
            otherwise WebCommand for DSL execution.
        """
        command = self._create_web_command(WebActionType.WAIT, selector, fallback_selectors, timeout, condition, scope_element=self._element_handle)
        return self._execute_if_available(command)
    
    def get_text(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None):
        """Get text from an element.
        
        Args:
            selector: CSS selector, XPath, or natural language description
            fallback_selectors: Alternative selectors to try
            timeout: Optional timeout in seconds
            
        Returns:
            String text if executor is available (when called from scoped objects),
            otherwise WebCommand for DSL execution.
            
        Note:
            When called from a scoped WebActions object (e.g., 'field.get_text()'),
            this executes immediately via the executor pattern. See class docstring
            for architectural details.
        """
        command = self._create_web_command(WebActionType.GET_TEXT, selector, fallback_selectors, timeout, None, scope_element=self._element_handle)
        return self._execute_if_available(command)
    
    def hover(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None):
        """Hover over an element.
        
        Args:
            selector: CSS selector, XPath, or natural language description
            fallback_selectors: Alternative selectors to try
            timeout: Optional timeout in seconds
            
        Returns:
            Executed result if executor is available (when called from scoped objects),
            otherwise WebCommand for DSL execution.
        """
        command = self._create_web_command(WebActionType.HOVER, selector, fallback_selectors, timeout, None, scope_element=self._element_handle)
        return self._execute_if_available(command)
    
    def scroll_to(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None):
        """Scroll to an element.
        
        Args:
            selector: CSS selector, XPath, or natural language description
            fallback_selectors: Alternative selectors to try
            timeout: Optional timeout in seconds
            
        Returns:
            Executed result if executor is available (when called from scoped objects),
            otherwise WebCommand for DSL execution.
        """
        command = self._create_web_command(WebActionType.SCROLL, selector, fallback_selectors, timeout, None, scope_element=self._element_handle)
        return self._execute_if_available(command)
    
    def select_option(self, selector: str, option_value: str, *fallback_selectors: str, timeout: Optional[float] = None):
        """Select an option in a dropdown.
        
        Args:
            selector: CSS selector, XPath, or natural language description
            option_value: Value of the option to select
            fallback_selectors: Alternative selectors to try
            timeout: Optional timeout in seconds
            
        Returns:
            Executed result if executor is available (when called from scoped objects),
            otherwise WebCommand for DSL execution.
        """
        command = self._create_web_command(WebActionType.SELECT, selector, fallback_selectors, timeout, option_value, scope_element=self._element_handle)
        return self._execute_if_available(command)
    
    def submit_form(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None):
        """Submit a form.
        
        Args:
            selector: CSS selector, XPath, or natural language description
            fallback_selectors: Alternative selectors to try
            timeout: Optional timeout in seconds
            
        Returns:
            Executed result if executor is available (when called from scoped objects),
            otherwise WebCommand for DSL execution.
        """
        command = self._create_web_command(WebActionType.SUBMIT, selector, fallback_selectors, timeout, None, scope_element=self._element_handle)
        return self._execute_if_available(command)
    
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
    
    def is_visible(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None):
        """Check if an element is visible.
        
        Args:
            selector: CSS selector, XPath, or natural language description
            fallback_selectors: Alternative selectors to try
            timeout: Optional timeout in seconds
            
        Returns:
            Boolean if executor is available (when called from scoped objects),
            otherwise WebCommand for DSL execution.
        """
        command = self._create_web_command(WebActionType.IS_VISIBLE, selector, fallback_selectors, timeout, None, scope_element=self._element_handle)
        return self._execute_if_available(command)
    
    def is_enabled(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None):
        """Check if an element is enabled.
        
        Args:
            selector: CSS selector, XPath, or natural language description
            fallback_selectors: Alternative selectors to try
            timeout: Optional timeout in seconds
            
        Returns:
            Boolean if executor is available (when called from scoped objects),
            otherwise WebCommand for DSL execution.
        """
        command = self._create_web_command(WebActionType.IS_ENABLED, selector, fallback_selectors, timeout, None, scope_element=self._element_handle)
        return self._execute_if_available(command)
    
    def is_checked(self, selector: str, *fallback_selectors: str, timeout: Optional[float] = None):
        """Check if a checkbox or radio button is checked.
        
        Args:
            selector: CSS selector for the checkbox/radio input
            fallback_selectors: Alternative selectors
            timeout: Optional timeout in seconds
            
        Returns:
            Boolean if executor is available (when called from scoped objects),
            otherwise WebCommand for DSL execution.
            
        Example:
            if web.is_checked("input[type='checkbox']"):
                print("Checkbox is checked")
        """
        command = self._create_web_command(WebActionType.IS_CHECKED, selector, fallback_selectors, timeout, None, scope_element=self._element_handle)
        return self._execute_if_available(command)
    
    def get_input_type(self, selector: str = "input, select, textarea", *fallback_selectors: str, timeout: Optional[float] = None):
        """Detect the type of an input element.
        
        Returns InputType enum value (as string): TEXT, EMAIL, TEL, NUMBER, PASSWORD, URL, 
        SEARCH, DATE, TIME, DATETIME_LOCAL, MONTH, WEEK, FILE, CHECKBOX, RADIO, COLOR, 
        RANGE, SELECT, TEXTAREA, BUTTON, SUBMIT, RESET, HIDDEN, UNKNOWN
        
        Args:
            selector: CSS selector for input element (defaults to common input types)
            fallback_selectors: Alternative selectors
            timeout: Optional timeout in seconds
            
        Returns:
            InputType enum value as string if executor is available (when called from scoped objects),
            otherwise WebCommand for DSL execution.
            
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
        command = self._create_web_command(WebActionType.GET_INPUT_TYPE, selector, fallback_selectors, timeout, None, scope_element=self._element_handle)
        return self._execute_if_available(command)
    
    def get_attribute(self, selector: str, attribute_name: str, *fallback_selectors: str, timeout: Optional[float] = None):
        """Get an attribute value from an element.
        
        Args:
            selector: CSS selector for the element
            attribute_name: Name of the attribute to get (e.g., "href", "class", "data-id")
            fallback_selectors: Alternative selectors
            timeout: Optional timeout in seconds
            
        Returns:
            Attribute value string if executor is available (when called from scoped objects),
            otherwise WebCommand for DSL execution.
            
        Example:
            href = web.get_attribute("a.link", "href")
            data_id = web.get_attribute("div", "data-id")
        """
        command = self._create_web_command(WebActionType.GET_ATTRIBUTE, selector, fallback_selectors, timeout, attribute_name, scope_element=self._element_handle)
        return self._execute_if_available(command)
    
    def get_options(self, selector: Optional[str] = None, *fallback_selectors: str, timeout: Optional[float] = None):
        """Get all selectable option texts from radio buttons, checkboxes, or dropdown.
        
        Auto-detects and returns options from within the current scope. Works universally for:
        - Radio buttons: Returns all radio option labels
        - Checkboxes: Returns all checkbox option labels  
        - Dropdowns (<select>): Returns all <option> texts
        
        Smart behavior:
        - If exactly 1 option group found → Returns option texts
        - If multiple groups found → Raises MultipleSelectableInputsError
        - If no options found → Raises NoSelectableInputError
        
        Args:
            selector: Optional specific selector for the options container (auto-detects if None)
            fallback_selectors: Alternative selectors
            timeout: Optional timeout in seconds
            
        Returns:
            List[str] of option texts if executor is available (when called from scoped objects),
            otherwise WebCommand for DSL execution.
        
        Raises:
            MultipleSelectableInputsError: Multiple radio/checkbox/select groups in scope
            NoSelectableInputError: No radio/checkbox/select found in scope
            
        Example:
            # Auto-detect and get options
            field = web.get_element("div.form-field")
            options = field.get_options()
            # Returns: ["Entry Level", "Mid-Level", "Senior"]
            
            # AI picks which to select
            selected = pick_best_options(question, options)
            
            # Click selected option(s)
            for opt in selected:
                field.click(opt)  # AI resolves natural language selector
        """
        command = self._create_web_command(WebActionType.GET_OPTIONS, selector or "", fallback_selectors, timeout, None, scope_element=self._element_handle)
        return self._execute_if_available(command)
    
    def upload_file(self, file_path: str, selector: str, *fallback_selectors: str, timeout: Optional[float] = None):
        """Upload a file to a file input element.
        
        Args:
            file_path: Absolute path to the file to upload
            selector: CSS selector for the file input element (usually input[type='file'])
            fallback_selectors: Alternative selectors to try if the primary selector fails
            timeout: Optional timeout in seconds
            
        Returns:
            Executed result if executor is available (when called from scoped objects),
            otherwise WebCommand for DSL execution.
            
        Example:
            web.upload_file("/Users/john/Documents/resume.pdf", "input[type='file']")
            web.upload_file("/path/to/file.pdf", "input[name='file']", "input[type='file']", ".file-input")
        """
        command = self._create_web_command(WebActionType.UPLOAD_FILE, selector, fallback_selectors, timeout, file_path, scope_element=self._element_handle)
        return self._execute_if_available(command)
    
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