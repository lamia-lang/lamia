"""Tests for web actions module."""

import pytest
import json
from unittest.mock import Mock, AsyncMock, MagicMock
from lamia.actions.web import WebActions, _detect_selector_type
from lamia.interpreter.commands import WebCommand, WebActionType
from lamia.internal_types import SelectorType


class TestSelectorTypeDetection:
    """Test selector type auto-detection."""
    
    def test_xpath_detection(self):
        """Test XPath selector detection."""
        assert _detect_selector_type("//div[@id='test']") == SelectorType.XPATH
        assert _detect_selector_type("//input[contains(@class, 'btn')]") == SelectorType.XPATH
        assert _detect_selector_type("//a[@href='#']") == SelectorType.XPATH
    
    def test_id_detection(self):
        """Test ID selector detection.""" 
        assert _detect_selector_type("#myId") == SelectorType.ID
        assert _detect_selector_type("#test-button") == SelectorType.ID
        assert _detect_selector_type("#form_123") == SelectorType.ID
    
    def test_class_name_detection(self):
        """Test class name selector detection."""
        assert _detect_selector_type(".myClass") == SelectorType.CLASS_NAME
        assert _detect_selector_type(".btn-primary") == SelectorType.CLASS_NAME
        assert _detect_selector_type(".nav_item") == SelectorType.CLASS_NAME
        
        # Should not detect class if contains spaces or brackets
        assert _detect_selector_type(".class .nested") == SelectorType.CSS
        assert _detect_selector_type(".class[attr]") == SelectorType.CSS
    
    def test_css_detection(self):
        """Test CSS selector detection."""
        assert _detect_selector_type("div:nth-child(2)") == SelectorType.CSS
        assert _detect_selector_type("input:contains('text')") == SelectorType.CSS
        assert _detect_selector_type("button[type='submit']") == SelectorType.CSS
        assert _detect_selector_type("[data-id='123']") == SelectorType.CSS
        assert _detect_selector_type("div.class span") == SelectorType.CSS
    
    def test_tag_name_detection(self):
        """Test tag name selector detection."""
        assert _detect_selector_type("button") == SelectorType.TAG_NAME
        assert _detect_selector_type("input") == SelectorType.TAG_NAME
        assert _detect_selector_type("form") == SelectorType.TAG_NAME
        
        # Should not detect as tag name if contains special characters
        assert _detect_selector_type("div.class") == SelectorType.CSS
        assert _detect_selector_type("button#id") == SelectorType.CSS
        assert _detect_selector_type("input[type]") == SelectorType.CSS
    
    def test_default_css_detection(self):
        """Test default to CSS for ambiguous cases."""
        assert _detect_selector_type("complex selector string") == SelectorType.CSS
        assert _detect_selector_type("div > span") == SelectorType.CSS
        assert _detect_selector_type("") == SelectorType.CSS


class TestWebActionsInitialization:
    """Test WebActions initialization."""
    
    def test_default_initialization(self):
        """Test default WebActions initialization."""
        web_actions = WebActions()
        assert web_actions._element_handle is None
        assert web_actions._executor is None
    
    def test_scoped_initialization(self):
        """Test scoped WebActions initialization."""
        element_handle = Mock()
        executor = Mock()
        
        web_actions = WebActions(element_handle=element_handle, executor=executor)
        assert web_actions._element_handle == element_handle
        assert web_actions._executor == executor


class TestWebActionsBasicOperations:
    """Test basic web operations without executor."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.web_actions = WebActions()
    
    def test_click_command_generation(self):
        """Test click command generation."""
        result = self.web_actions.click("#button")
        assert isinstance(result, WebCommand)
        assert result.action == WebActionType.CLICK
        assert result.selector == "#button"
        assert result.fallback_selectors is None
        assert result.timeout is None
    
    def test_click_with_fallbacks(self):
        """Test click with fallback selectors."""
        result = self.web_actions.click("#button", ".btn", "button")
        assert isinstance(result, WebCommand)
        assert result.selector == "#button"
        assert result.fallback_selectors == [".btn", "button"]
    
    def test_click_with_timeout(self):
        """Test click with timeout."""
        result = self.web_actions.click("#button", timeout=5.0)
        assert isinstance(result, WebCommand)
        assert result.timeout == 5.0
    
    def test_type_text_command(self):
        """Test type text command generation."""
        result = self.web_actions.type_text("#input", "hello world")
        assert isinstance(result, WebCommand)
        assert result.action == WebActionType.TYPE
        assert result.selector == "#input"
        assert result.value == "hello world"
    
    def test_wait_for_command(self):
        """Test wait for command generation."""
        result = self.web_actions.wait_for("#element")
        assert isinstance(result, WebCommand)
        assert result.action == WebActionType.WAIT
        assert result.selector == "#element"
        assert result.value == "visible"  # default condition
        
        result = self.web_actions.wait_for("#element", "clickable")
        assert result.value == "clickable"
    
    def test_get_text_command(self):
        """Test get text command generation."""
        result = self.web_actions.get_text("#text")
        assert isinstance(result, WebCommand)
        assert result.action == WebActionType.GET_TEXT
        assert result.selector == "#text"
    
    def test_hover_command(self):
        """Test hover command generation."""
        result = self.web_actions.hover("#menu")
        assert isinstance(result, WebCommand)
        assert result.action == WebActionType.HOVER
        assert result.selector == "#menu"
    
    def test_scroll_to_command(self):
        """Test scroll to command generation."""
        result = self.web_actions.scroll_to("#section")
        assert isinstance(result, WebCommand)
        assert result.action == WebActionType.SCROLL
        assert result.selector == "#section"
    
    def test_select_option_command(self):
        """Test select option command generation."""
        result = self.web_actions.select_option("#dropdown", "option1")
        assert isinstance(result, WebCommand)
        assert result.action == WebActionType.SELECT
        assert result.selector == "#dropdown"
        assert result.value == "option1"
    
    def test_submit_form_command(self):
        """Test submit form command generation."""
        result = self.web_actions.submit_form("#form")
        assert isinstance(result, WebCommand)
        assert result.action == WebActionType.SUBMIT
        assert result.selector == "#form"
    
    def test_screenshot_command(self):
        """Test screenshot command generation."""
        result = self.web_actions.screenshot()
        assert isinstance(result, WebCommand)
        assert result.action == WebActionType.SCREENSHOT
        assert result.value is None
        
        result = self.web_actions.screenshot("test.png")
        assert result.value == "test.png"
    
    def test_is_visible_command(self):
        """Test is visible command generation."""
        result = self.web_actions.is_visible("#element")
        assert isinstance(result, WebCommand)
        assert result.action == WebActionType.IS_VISIBLE
        assert result.selector == "#element"
    
    def test_is_enabled_command(self):
        """Test is enabled command generation."""
        result = self.web_actions.is_enabled("#button")
        assert isinstance(result, WebCommand)
        assert result.action == WebActionType.IS_ENABLED
        assert result.selector == "#button"
    
    def test_is_checked_command(self):
        """Test is checked command generation."""
        result = self.web_actions.is_checked("input[type='checkbox']")
        assert isinstance(result, WebCommand)
        assert result.action == WebActionType.IS_CHECKED
        assert result.selector == "input[type='checkbox']"
    
    def test_get_input_type_command(self):
        """Test get input type command generation."""
        result = self.web_actions.get_input_type()
        assert isinstance(result, WebCommand)
        assert result.action == WebActionType.GET_INPUT_TYPE
        assert result.selector == "input, select, textarea"
        
        result = self.web_actions.get_input_type("#specific")
        assert result.selector == "#specific"
    
    def test_get_attribute_command(self):
        """Test get attribute command generation."""
        result = self.web_actions.get_attribute("#link", "href")
        assert isinstance(result, WebCommand)
        assert result.action == WebActionType.GET_ATTRIBUTE
        assert result.selector == "#link"
        assert result.value == "href"
    
    def test_get_options_command(self):
        """Test get options command generation."""
        result = self.web_actions.get_options()
        assert isinstance(result, WebCommand)
        assert result.action == WebActionType.GET_OPTIONS
        assert result.selector == ""
        
        result = self.web_actions.get_options("#select")
        assert result.selector == "#select"
    
    def test_upload_file_command(self):
        """Test upload file command generation."""
        result = self.web_actions.upload_file("/path/to/file.pdf", "input[type='file']")
        assert isinstance(result, WebCommand)
        assert result.action == WebActionType.UPLOAD_FILE
        assert result.selector == "input[type='file']"
        assert result.value == "/path/to/file.pdf"


class TestWebActionsElementOperations:
    """Test element getting operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.web_actions = WebActions()
    
    def test_get_element_command(self):
        """Test get element command generation."""
        result = self.web_actions.get_element("#element")
        assert isinstance(result, WebCommand)
        assert result.action == WebActionType.GET_ELEMENT
        assert result.selector == "#element"
    
    def test_get_elements_command(self):
        """Test get elements command generation."""
        result = self.web_actions.get_elements(".items")
        assert isinstance(result, WebCommand)
        assert result.action == WebActionType.GET_ELEMENTS
        assert result.selector == ".items"


class TestWebActionsHTTP:
    """Test HTTP operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.web_actions = WebActions()
    
    def test_get_request(self):
        """Test HTTP GET request generation."""
        result = self.web_actions.get("https://api.example.com")
        assert result == "GET https://api.example.com"
        
        # With headers
        headers = {"Authorization": "Bearer token"}
        result = self.web_actions.get("https://api.example.com", headers=headers)
        expected = f"GET https://api.example.com headers:{json.dumps(headers)}"
        assert result == expected
        
        # With timeout
        result = self.web_actions.get("https://api.example.com", timeout=30.0)
        assert result == "GET https://api.example.com timeout:30.0"
    
    def test_post_request(self):
        """Test HTTP POST request generation."""
        result = self.web_actions.post("https://api.example.com")
        assert result == "POST https://api.example.com"
        
        # With dict data (JSON)
        data = {"name": "John", "email": "john@example.com"}
        result = self.web_actions.post("https://api.example.com", data=data)
        expected = f"POST https://api.example.com json:{json.dumps(data)}"
        assert result == expected
        
        # With string data
        data = "raw data"
        result = self.web_actions.post("https://api.example.com", data=data)
        assert result == "POST https://api.example.com data:raw data"
        
        # With headers
        headers = {"Content-Type": "application/json"}
        result = self.web_actions.post("https://api.example.com", headers=headers)
        expected = f"POST https://api.example.com headers:{json.dumps(headers)}"
        assert result == expected
    
    def test_put_request(self):
        """Test HTTP PUT request generation."""
        data = {"name": "John Updated"}
        result = self.web_actions.put("https://api.example.com/users/1", data=data)
        expected = f"PUT https://api.example.com/users/1 json:{json.dumps(data)}"
        assert result == expected
    
    def test_patch_request(self):
        """Test HTTP PATCH request generation."""
        data = {"email": "new@example.com"}
        result = self.web_actions.patch("https://api.example.com/users/1", data=data)
        expected = f"PATCH https://api.example.com/users/1 json:{json.dumps(data)}"
        assert result == expected
    
    def test_delete_request(self):
        """Test HTTP DELETE request generation."""
        result = self.web_actions.delete("https://api.example.com/users/1")
        assert result == "DELETE https://api.example.com/users/1"
        
        # With headers
        headers = {"Authorization": "Bearer token"}
        result = self.web_actions.delete("https://api.example.com/users/1", headers=headers)
        expected = f"DELETE https://api.example.com/users/1 headers:{json.dumps(headers)}"
        assert result == expected


class TestWebActionsExecutor:
    """Test WebActions with executor (scoped operations)."""
    
    def setup_method(self):
        """Set up test fixtures with mock executor."""
        self.mock_executor = AsyncMock()
        self.element_handle = Mock()
        self.web_actions = WebActions(element_handle=self.element_handle, executor=self.mock_executor)
    
    def test_execute_if_available_with_executor(self):
        """Test command execution when executor is available."""
        # Mock executor returning a validation result
        mock_result = Mock()
        mock_result.typed_result = "executed result"
        self.mock_executor.execute.return_value = mock_result
        
        command = WebCommand(action=WebActionType.CLICK, selector="#button")
        result = self.web_actions._execute_if_available(command)
        
        assert result == "executed result"
        self.mock_executor.execute.assert_called_once_with(command)
    
    def test_execute_if_available_with_result_processor(self):
        """Test command execution with result processor."""
        mock_result = Mock()
        mock_result.typed_result = "raw result"
        self.mock_executor.execute.return_value = mock_result
        
        def processor(result):
            return f"processed: {result}"
        
        command = WebCommand(action=WebActionType.GET_TEXT, selector="#text")
        result = self.web_actions._execute_if_available(command, processor)
        
        assert result == "processed: raw result"
    
    def test_execute_if_available_without_executor(self):
        """Test command return when no executor is available."""
        web_actions = WebActions()  # No executor
        command = WebCommand(action=WebActionType.CLICK, selector="#button")
        result = web_actions._execute_if_available(command)
        
        assert result == command
    
    def test_execute_if_available_with_exception(self):
        """Test command return when execution raises exception."""
        self.mock_executor.execute.side_effect = Exception("Execution failed")
        
        command = WebCommand(action=WebActionType.CLICK, selector="#button")

        with pytest.raises(Exception, match="Execution failed"):
            self.web_actions._execute_if_available(command)
    
    def test_scoped_operations_use_element_handle(self):
        """Test that scoped operations include element handle."""
        command = self.web_actions.click("#button")
        
        if isinstance(command, WebCommand):
            assert command.scope_element_handle == self.element_handle


class TestWebActionsCommandCreation:
    """Test WebCommand creation helper."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.web_actions = WebActions()
    
    def test_create_web_command_basic(self):
        """Test basic WebCommand creation."""
        command = self.web_actions._create_web_command(
            WebActionType.CLICK,
            "#button",
            (),
            None,
            None,
            None
        )
        
        assert isinstance(command, WebCommand)
        assert command.action == WebActionType.CLICK
        assert command.selector == "#button"
        assert command.fallback_selectors is None
        assert command.value is None
        assert command.timeout is None
        assert command.scope_element_handle is None
    
    def test_create_web_command_with_options(self):
        """Test WebCommand creation with all options."""
        element_handle = Mock()
        command = self.web_actions._create_web_command(
            WebActionType.TYPE,
            "#input",
            (".input", "input"),
            10.0,
            "text value",
            element_handle
        )
        
        assert command.action == WebActionType.TYPE
        assert command.selector == "#input"
        assert command.fallback_selectors == [".input", "input"]
        assert command.timeout == 10.0
        assert command.value == "text value"
        assert command.scope_element_handle == element_handle
    
    def test_create_web_command_empty_fallbacks(self):
        """Test WebCommand creation with empty fallbacks."""
        command = self.web_actions._create_web_command(
            WebActionType.CLICK,
            "#button",
            (),  # Empty tuple
            None,
            None,
            None
        )
        
        assert command.fallback_selectors is None