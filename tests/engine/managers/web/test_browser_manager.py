"""Tests for BrowserManager."""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from lamia.engine.managers.web.browser_manager import BrowserManager
from lamia.engine.config_provider import ConfigProvider
from lamia.validation.base import ValidationResult, BaseValidator
from lamia.interpreter.commands import WebCommand, WebActionType
from lamia.internal_types import BrowserAction, BrowserActionType, BrowserActionParams
from lamia.adapters.web.browser.base import BaseBrowserAdapter


class TestBrowserManagerInitialization:
    """Test BrowserManager initialization."""
    
    def test_initialization_with_config_provider(self):
        """Test initialization with config provider."""
        config_dict = {}
        config_provider = ConfigProvider(config_dict)
        
        manager = BrowserManager(config_provider)
        
        assert manager.config_provider == config_provider
        assert manager.web_manager is None
        assert manager._browser_engine == "selenium"  # default
        assert manager._browser_options["headless"] is False  # default
        assert manager._browser_options["timeout"] == 10.0  # default
        assert manager._active_profile is None
        assert manager._selector_resolution_service is None
        assert manager._selector_suggestion_service is None
        assert manager._browser_adapter is None
        assert manager.all_selectors_failed_handler is None
    
    def test_initialization_with_web_config(self):
        """Test initialization with web configuration."""
        web_config = {
            "browser_engine": "playwright",
            "browser_options": {
                "headless": True,
                "timeout": 30.0,
                "custom_option": "test_value"
            }
        }
        config_dict = {"web_config": web_config}
        config_provider = ConfigProvider(config_dict)
        
        manager = BrowserManager(config_provider)
        
        assert manager._browser_engine == "playwright"
        assert manager._browser_options["headless"] is True
        assert manager._browser_options["timeout"] == 30.0
        assert manager._browser_options["custom_option"] == "test_value"
    
    def test_initialization_with_web_manager(self):
        """Test initialization with web manager reference."""
        config_dict = {}
        config_provider = ConfigProvider(config_dict)
        web_manager = Mock()
        
        manager = BrowserManager(config_provider, web_manager=web_manager)
        
        assert manager.web_manager == web_manager
    
    def test_initialization_with_partial_browser_options(self):
        """Test initialization with partial browser options preserves defaults."""
        web_config = {
            "browser_options": {
                "headless": True
                # timeout missing, should use default
            }
        }
        config_dict = {"web_config": web_config}
        config_provider = ConfigProvider(config_dict)
        
        manager = BrowserManager(config_provider)
        
        assert manager._browser_options["headless"] is True  # from config
        assert manager._browser_options["timeout"] == 10.0  # default


class TestBrowserManagerWebCommandConversion:
    """Test WebCommand to BrowserAction conversion."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {}
        self.config_provider = ConfigProvider(config_dict)
        self.manager = BrowserManager(self.config_provider)
    
    def test_convert_navigate_command(self):
        """Test converting NAVIGATE command."""
        command = WebCommand(action=WebActionType.NAVIGATE, url="https://example.com")
        
        browser_action = self.manager._web_command_to_browser_action(command)
        
        assert isinstance(browser_action, BrowserAction)
        assert browser_action.action == BrowserActionType.NAVIGATE
        assert browser_action.params.value == "https://example.com"
    
    def test_convert_click_command(self):
        """Test converting CLICK command."""
        command = WebCommand(action=WebActionType.CLICK, selector="#button")
        
        browser_action = self.manager._web_command_to_browser_action(command)
        
        assert browser_action.action == BrowserActionType.CLICK
        assert browser_action.params.selector == "#button"
    
    def test_convert_type_command(self):
        """Test converting TYPE command."""
        command = WebCommand(action=WebActionType.TYPE, selector="#input", value="test text")
        
        browser_action = self.manager._web_command_to_browser_action(command)
        
        assert browser_action.action == BrowserActionType.TYPE
        assert browser_action.params.selector == "#input"
        assert browser_action.params.value == "test text"
    
    def test_convert_get_text_command(self):
        """Test converting GET_TEXT command."""
        command = WebCommand(action=WebActionType.GET_TEXT, selector=".content")
        
        browser_action = self.manager._web_command_to_browser_action(command)
        
        assert browser_action.action == BrowserActionType.GET_TEXT
        assert browser_action.params.selector == ".content"
    
    def test_convert_wait_command(self):
        """Test converting WAIT command."""
        command = WebCommand(action=WebActionType.WAIT, selector="button", timeout=5.0)
        
        browser_action = self.manager._web_command_to_browser_action(command)
        
        assert browser_action.action == BrowserActionType.WAIT
        assert browser_action.params.selector == "button"


class TestBrowserManagerSelectorDetection:
    """Test selector detection logic."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {}
        self.config_provider = ConfigProvider(config_dict)
        self.manager = BrowserManager(self.config_provider)
    
    def test_has_selector_with_selector(self):
        """Test _has_selector returns True for actions with selectors."""
        action_with_selector = BrowserAction(
            action=BrowserActionType.CLICK,
            params=BrowserActionParams(selector="#button")
        )
        
        assert self.manager._has_selector(action_with_selector) is True
    
    def test_has_selector_without_selector(self):
        """Test _has_selector returns False for actions without selectors."""
        action_without_selector = BrowserAction(
            action=BrowserActionType.NAVIGATE,
            params=BrowserActionParams(value="https://example.com")
        )
        
        assert self.manager._has_selector(action_without_selector) is False
    
    def test_has_selector_with_empty_selector(self):
        """Test _has_selector returns True for empty selectors."""
        action_with_empty_selector = BrowserAction(
            action=BrowserActionType.CLICK,
            params=BrowserActionParams(selector="")
        )
        
        # The actual implementation only checks if selector is not None
        # Empty string is considered a valid selector
        assert self.manager._has_selector(action_with_empty_selector) is True
    
    def test_has_selector_with_none_selector(self):
        """Test _has_selector returns False for None selectors."""
        action_with_none_selector = BrowserAction(
            action=BrowserActionType.CLICK,
            params=BrowserActionParams(selector=None)
        )
        
        assert self.manager._has_selector(action_with_none_selector) is False


class TestBrowserManagerExecution:
    """Test browser command execution flow."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {}
        self.config_provider = ConfigProvider(config_dict)
        self.manager = BrowserManager(self.config_provider)
    
    @pytest.mark.asyncio
    async def test_execute_command_without_selector(self):
        """Test executing command that doesn't require selector resolution."""
        command = WebCommand(action=WebActionType.NAVIGATE, url="https://example.com")
        
        with patch.object(self.manager, '_execute_browser_action') as mock_execute:
            mock_execute.return_value = "Navigation successful"
            
            result = await self.manager.execute(command)
            
            assert result == "Navigation successful"
            mock_execute.assert_called_once()
            
            # Check that browser action was created correctly
            call_args = mock_execute.call_args
            browser_action = call_args[0][0]
            assert browser_action.action == BrowserActionType.NAVIGATE
            assert browser_action.params.value == "https://example.com"
    
    @pytest.mark.asyncio
    async def test_execute_command_with_selector(self):
        """Test executing command that requires selector resolution."""
        command = WebCommand(action=WebActionType.CLICK, selector="#button")
        
        resolved_action = BrowserAction(
            action=BrowserActionType.CLICK,
            params=BrowserActionParams(selector="#resolved-button")
        )
        
        with patch.object(self.manager, '_resolve_selectors') as mock_resolve:
            mock_resolve.return_value = resolved_action
            
            with patch.object(self.manager, '_execute_browser_action') as mock_execute:
                mock_execute.return_value = "Click successful"
                
                result = await self.manager.execute(command)
                
                assert result == "Click successful"
                mock_resolve.assert_called_once()
                mock_execute.assert_called_once()
                
                # Check that resolved action was used
                call_args = mock_execute.call_args
                used_action = call_args[0][0]
                assert used_action.params.selector == "#resolved-button"
    
    @pytest.mark.asyncio
    async def test_execute_with_validator_fallback_to_page_source(self):
        """Test execution with validator that falls back to page source when result is None."""
        command = WebCommand(action=WebActionType.CLICK, selector="#button")
        validator = Mock(spec=BaseValidator)
        
        with patch.object(self.manager, '_execute_browser_action') as mock_execute:
            mock_execute.return_value = None  # Action returns None
            
            with patch.object(self.manager, 'get_page_source') as mock_get_source:
                mock_get_source.return_value = "<html>Page content</html>"
                
                result = await self.manager.execute(command, validator=validator)
                
                assert result == "<html>Page content</html>"
                mock_get_source.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_with_validator_page_source_error(self):
        """Test execution when page source fallback fails."""
        command = WebCommand(action=WebActionType.CLICK, selector="#button")
        validator = Mock(spec=BaseValidator)
        
        with patch.object(self.manager, '_execute_browser_action') as mock_execute:
            mock_execute.return_value = None
            
            with patch.object(self.manager, 'get_page_source') as mock_get_source:
                mock_get_source.side_effect = RuntimeError("Failed to get page source")
                
                result = await self.manager.execute(command, validator=validator)
                
                assert result is None
    
    @pytest.mark.asyncio
    async def test_execute_with_active_profile_loads_session(self):
        """Test execution with active profile loads session cookies."""
        command = WebCommand(action=WebActionType.NAVIGATE, url="https://example.com")
        
        self.manager._active_profile = "test_profile"
        self.manager._browser_adapter = None  # Not yet initialized
        
        with patch.object(self.manager, 'load_session_cookies') as mock_load:
            mock_load.return_value = None
            
            with patch.object(self.manager, '_execute_browser_action') as mock_execute:
                mock_execute.return_value = "Success"
                
                result = await self.manager.execute(command)
                
                mock_load.assert_called_once_with("test_profile")
                assert result == "Success"
    
    @pytest.mark.asyncio
    async def test_execute_with_active_profile_load_session_error(self):
        """Test execution continues even if session loading fails."""
        command = WebCommand(action=WebActionType.NAVIGATE, url="https://example.com")
        
        self.manager._active_profile = "test_profile"
        self.manager._browser_adapter = None
        
        with patch.object(self.manager, 'load_session_cookies') as mock_load:
            mock_load.side_effect = RuntimeError("Failed to load session")
            
            with patch.object(self.manager, '_execute_browser_action') as mock_execute:
                mock_execute.return_value = "Success"
                
                # Should not raise exception
                result = await self.manager.execute(command)
                
                assert result == "Success"


class TestBrowserManagerConfiguration:
    """Test browser manager configuration handling."""
    
    def test_default_browser_engine(self):
        """Test default browser engine selection."""
        config_dict = {}
        config_provider = ConfigProvider(config_dict)
        
        manager = BrowserManager(config_provider)
        
        assert manager._browser_engine == "selenium"
    
    def test_custom_browser_engine(self):
        """Test custom browser engine selection."""
        web_config = {"browser_engine": "playwright"}
        config_dict = {"web_config": web_config}
        config_provider = ConfigProvider(config_dict)
        
        manager = BrowserManager(config_provider)
        
        assert manager._browser_engine == "playwright"
    
    def test_browser_options_override_defaults(self):
        """Test that browser options override defaults."""
        web_config = {
            "browser_options": {
                "headless": True,
                "timeout": 25.0
            }
        }
        config_dict = {"web_config": web_config}
        config_provider = ConfigProvider(config_dict)
        
        manager = BrowserManager(config_provider)
        
        assert manager._browser_options["headless"] is True
        assert manager._browser_options["timeout"] == 25.0
    
    def test_browser_options_preserve_additional_settings(self):
        """Test that additional browser options are preserved."""
        web_config = {
            "browser_options": {
                "window_size": (1920, 1080),
                "user_agent": "Custom Agent",
                "download_directory": "/tmp/downloads"
            }
        }
        config_dict = {"web_config": web_config}
        config_provider = ConfigProvider(config_dict)
        
        manager = BrowserManager(config_provider)
        
        assert manager._browser_options["window_size"] == (1920, 1080)
        assert manager._browser_options["user_agent"] == "Custom Agent"
        assert manager._browser_options["download_directory"] == "/tmp/downloads"
        # Defaults should still be set
        assert manager._browser_options["headless"] is False
        assert manager._browser_options["timeout"] == 10.0


class TestBrowserManagerEdgeCases:
    """Test edge cases and error conditions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {}
        self.config_provider = ConfigProvider(config_dict)
        self.manager = BrowserManager(self.config_provider)
    
    def test_web_command_conversion_with_complex_selector(self):
        """Test command conversion with complex CSS selector."""
        complex_selector = "div.container > ul.list li:nth-child(2) a[href*='target']"
        command = WebCommand(action=WebActionType.CLICK, selector=complex_selector)
        
        browser_action = self.manager._web_command_to_browser_action(command)
        
        assert browser_action.params.selector == complex_selector
    
    def test_web_command_conversion_with_xpath_selector(self):
        """Test command conversion with XPath selector."""
        xpath_selector = "//div[@class='content']//span[contains(text(), 'Click me')]"
        command = WebCommand(action=WebActionType.GET_TEXT, selector=xpath_selector)
        
        browser_action = self.manager._web_command_to_browser_action(command)
        
        assert browser_action.params.selector == xpath_selector
    
    def test_web_command_conversion_with_fallback_selectors(self):
        """Test command conversion with fallback selectors."""
        command = WebCommand(
            action=WebActionType.CLICK,
            selector="#primary-button",
            fallback_selectors=["button.submit", "input[type='submit']"]
        )
        
        browser_action = self.manager._web_command_to_browser_action(command)
        
        assert browser_action.params.selector == "#primary-button"
        # Note: fallback_selectors would be handled by selector resolution service
    
    def test_web_command_conversion_with_element_handle(self):
        """Test command conversion with scoped element handle."""
        mock_element_handle = Mock()
        command = WebCommand(
            action=WebActionType.CLICK,
            selector="button",
            scope_element_handle=mock_element_handle
        )
        
        browser_action = self.manager._web_command_to_browser_action(command)
        
        assert browser_action.params.selector == "button"
        assert browser_action.params.scope_element_handle is mock_element_handle
    
    def test_has_selector_with_whitespace_selector(self):
        """Test selector detection with whitespace-only selector."""
        action_with_whitespace = BrowserAction(
            action=BrowserActionType.CLICK,
            params=BrowserActionParams(selector="   \t\n   ")
        )
        
        # The actual implementation only checks if selector is not None
        # Whitespace string is considered a valid selector
        assert self.manager._has_selector(action_with_whitespace) is True


class TestBrowserManagerIntegration:
    """Test integration scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {
            "web_config": {
                "browser_engine": "selenium",
                "browser_options": {
                    "headless": True,
                    "timeout": 15.0
                }
            }
        }
        self.config_provider = ConfigProvider(config_dict)
        self.web_manager = Mock()
        self.manager = BrowserManager(self.config_provider, web_manager=self.web_manager)
    
    @pytest.mark.asyncio
    async def test_full_workflow_without_selector_resolution(self):
        """Test complete workflow for commands that don't need selector resolution."""
        navigation_command = WebCommand(action=WebActionType.NAVIGATE, url="https://example.com")
        
        with patch.object(self.manager, '_execute_browser_action') as mock_execute:
            mock_execute.return_value = "Navigation complete"
            
            result = await self.manager.execute(navigation_command)
            
            assert result == "Navigation complete"
            
            # Verify browser action was created correctly
            call_args = mock_execute.call_args
            browser_action = call_args[0][0]
            assert browser_action.action == BrowserActionType.NAVIGATE
            assert browser_action.params.value == "https://example.com"
    
    @pytest.mark.asyncio
    async def test_full_workflow_with_selector_resolution(self):
        """Test complete workflow for commands that need selector resolution."""
        click_command = WebCommand(action=WebActionType.CLICK, selector="#submit")
        
        # Mock selector resolution
        resolved_action = BrowserAction(
            action=BrowserActionType.CLICK,
            params=BrowserActionParams(selector="button.btn-primary")
        )
        
        with patch.object(self.manager, '_resolve_selectors') as mock_resolve:
            mock_resolve.return_value = resolved_action
            
            with patch.object(self.manager, '_execute_browser_action') as mock_execute:
                mock_execute.return_value = "Click executed"
                
                result = await self.manager.execute(click_command)
                
                assert result == "Click executed"
                
                # Verify selector resolution was called
                mock_resolve.assert_called_once()
                
                # Verify resolved action was executed
                call_args = mock_execute.call_args
                executed_action = call_args[0][0]
                assert executed_action.params.selector == "button.btn-primary"
    
    @pytest.mark.asyncio
    async def test_realistic_browser_automation_sequence(self):
        """Test realistic sequence of browser automation commands."""
        commands = [
            WebCommand(action=WebActionType.NAVIGATE, url="https://example.com"),
            WebCommand(action=WebActionType.TYPE, selector="#username", value="testuser"),
            WebCommand(action=WebActionType.TYPE, selector="#password", value="testpass"),
            WebCommand(action=WebActionType.CLICK, selector="#login-button"),
            WebCommand(action=WebActionType.GET_TEXT, selector=".welcome-message")
        ]
        
        expected_results = [
            "Navigation complete",
            "Text entered",
            "Text entered", 
            "Button clicked",
            "Welcome, testuser!"
        ]
        
        with patch.object(self.manager, '_resolve_selectors') as mock_resolve:
            # Return the same action for selector-based commands
            mock_resolve.side_effect = lambda action: action
            
            with patch.object(self.manager, '_execute_browser_action') as mock_execute:
                mock_execute.side_effect = expected_results
                
                results = []
                for command in commands:
                    result = await self.manager.execute(command)
                    results.append(result)
                
                assert results == expected_results
                assert mock_execute.call_count == 5
                # 4 commands have selectors, so resolve should be called 4 times
                assert mock_resolve.call_count == 4