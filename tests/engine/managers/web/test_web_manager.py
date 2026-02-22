"""Tests for WebManager."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from lamia.engine.managers.web.web_manager import WebManager
from lamia.engine.config_provider import ConfigProvider
from lamia.engine.managers.web.browser_manager import BrowserManager
from lamia.engine.managers.web.http_manager import HttpManager
from lamia.validation.base import ValidationResult, BaseValidator
from lamia.interpreter.commands import WebCommand, WebActionType
from lamia.interpreter.command_types import CommandType


class TestWebManagerInitialization:
    """Test WebManager initialization."""
    
    def test_initialization_with_config_provider(self):
        """Test initialization with config provider."""
        config_dict = {}
        config_provider = ConfigProvider(config_dict)
        
        with patch('lamia.engine.managers.web.web_manager.BrowserManager') as mock_browser:
            with patch('lamia.engine.managers.web.web_manager.HttpManager') as mock_http:
                manager = WebManager(config_provider)
        
        assert manager.config_provider == config_provider
        assert manager.llm_manager is None
        
        # Should initialize sub-managers
        mock_browser.assert_called_once_with(config_provider, web_manager=manager)
        mock_http.assert_called_once_with(config_provider)
        
        # Should initialize tracking structures
        assert manager.recent_actions == []
        assert manager.max_recent_actions == 10
        assert manager.stuck_threshold == 3
    
    def test_initialization_with_llm_manager(self):
        """Test initialization with LLM manager."""
        config_dict = {}
        config_provider = ConfigProvider(config_dict)
        llm_manager = Mock()
        
        with patch('lamia.engine.managers.web.web_manager.BrowserManager') as mock_browser:
            with patch('lamia.engine.managers.web.web_manager.HttpManager') as mock_http:
                manager = WebManager(config_provider, llm_manager=llm_manager)
        
        assert manager.llm_manager == llm_manager
    
    def test_action_type_categorization(self):
        """Test that action types are correctly categorized."""
        config_dict = {}
        config_provider = ConfigProvider(config_dict)
        
        with patch('lamia.engine.managers.web.web_manager.BrowserManager'):
            with patch('lamia.engine.managers.web.web_manager.HttpManager'):
                manager = WebManager(config_provider)
        
        # Check browser actions
        assert WebActionType.NAVIGATE in manager.browser_actions
        assert WebActionType.CLICK in manager.browser_actions
        assert WebActionType.TYPE in manager.browser_actions
        assert WebActionType.GET_TEXT in manager.browser_actions
        assert WebActionType.SCREENSHOT in manager.browser_actions
        
        # Check HTTP actions
        assert WebActionType.HTTP_REQUEST in manager.http_actions
        
        # Ensure no overlap
        assert len(manager.browser_actions & manager.http_actions) == 0


class TestWebManagerCommandRouting:
    """Test command routing to specialized managers."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {}
        self.config_provider = ConfigProvider(config_dict)
        
        with patch('lamia.engine.managers.web.web_manager.BrowserManager') as mock_browser_class:
            with patch('lamia.engine.managers.web.web_manager.HttpManager') as mock_http_class:
                self.mock_browser_manager = Mock()
                self.mock_http_manager = Mock()
                mock_browser_class.return_value = self.mock_browser_manager
                mock_http_class.return_value = self.mock_http_manager
                
                self.manager = WebManager(self.config_provider)
    
    @pytest.mark.asyncio
    async def test_route_browser_action(self):
        """Test routing browser actions to BrowserManager."""
        command = WebCommand(action=WebActionType.CLICK, selector="#button")
        validator = Mock(spec=BaseValidator)
        
        browser_result = "Success"
        self.mock_browser_manager.execute = AsyncMock(return_value=browser_result)
        
        expected_validation_result = ValidationResult(
            is_valid=True,
            raw_text=browser_result,
            validated_text=browser_result,
            execution_context=Mock()
        )
        validator.validate = AsyncMock(return_value=expected_validation_result)
        
        with patch.object(self.manager, '_track_action') as mock_track:
            result = await self.manager.execute(command, validator=validator)
        
        # Should route to browser manager
        self.mock_browser_manager.execute.assert_called_once_with(command, validator)
        # Should validate the result
        validator.validate.assert_called_once_with(browser_result)
        assert result == expected_validation_result
        
        # Should track the action
        mock_track.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_route_http_action(self):
        """Test routing HTTP actions to HttpManager."""
        command = WebCommand(action=WebActionType.HTTP_REQUEST, url="https://example.com")
        validator = Mock(spec=BaseValidator)
        
        expected_result = "HTTP response text"
        self.mock_http_manager.execute = AsyncMock(return_value=expected_result)
        
        mock_validation_result = ValidationResult(
            is_valid=True,
            raw_text=expected_result,
            validated_text=expected_result,
            execution_context=Mock()
        )
        validator.validate = AsyncMock(return_value=mock_validation_result)
        
        with patch.object(self.manager, '_track_action') as mock_track:
            result = await self.manager.execute(command, validator=validator)
        
        # Should route to HTTP manager
        self.mock_http_manager.execute.assert_called_once_with(command, validator)
        
        # Should validate the result
        validator.validate.assert_called_once_with(expected_result)
        assert result == mock_validation_result
        
        # Should track the action
        mock_track.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_unsupported_action_raises_error(self):
        """Test that unsupported actions raise ValueError."""
        # Create a custom action type that's not in either category
        command = Mock()
        command.action = "UNSUPPORTED_ACTION"
        command.selector = None
        command.value = None
        command.scope_element_handle = None
        
        with pytest.raises(ValueError, match="Unsupported web action: UNSUPPORTED_ACTION"):
            await self.manager.execute(command)
    
    @pytest.mark.asyncio
    async def test_execute_without_validator(self):
        """Test execution without validator creates default ValidationResult."""
        command = WebCommand(action=WebActionType.CLICK, selector="#button")
        
        expected_result = "Browser action result"
        self.mock_browser_manager.execute = AsyncMock(return_value=expected_result)
        
        result = await self.manager.execute(command, validator=None)
        
        # Should create default ValidationResult
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.typed_result == expected_result
        assert result.error_message is None


class TestWebManagerStuckDetection:
    """Test stuck detection functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {}
        self.config_provider = ConfigProvider(config_dict)
        
        with patch('lamia.engine.managers.web.web_manager.BrowserManager'):
            with patch('lamia.engine.managers.web.web_manager.HttpManager'):
                self.manager = WebManager(self.config_provider)
    
    def test_get_action_signature_with_selector(self):
        """Test action signature generation with selector."""
        command = WebCommand(action=WebActionType.CLICK, selector="#button")
        signature = self.manager._get_action_signature(command)
        
        assert signature == "WebActionType.CLICK:#button"
    
    def test_get_action_signature_with_value(self):
        """Test action signature generation with value."""
        command = WebCommand(action=WebActionType.TYPE, value="hello world")
        # Add text attribute to match implementation
        command.text = "hello world"
        signature = self.manager._get_action_signature(command)
        
        assert signature == "WebActionType.TYPE:hello world"
    
    def test_get_action_signature_action_only(self):
        """Test action signature generation with action only."""
        command = WebCommand(action=WebActionType.NAVIGATE, url="https://example.com")
        signature = self.manager._get_action_signature(command)
        
        assert signature == "WebActionType.NAVIGATE"
    
    def test_track_action_normal_operation(self):
        """Test normal action tracking."""
        signature = "CLICK:#button"
        
        # Track some actions
        self.manager._track_action(signature)
        self.manager._track_action("TYPE:text")
        self.manager._track_action(signature)
        
        assert self.manager.recent_actions == [signature, "TYPE:text", signature]
    
    def test_track_action_memory_limit(self):
        """Test that action tracking respects memory limit."""
        # Fill up beyond max_recent_actions
        for i in range(15):
            self.manager._track_action(f"ACTION_{i}")
        
        # Should only keep the most recent max_recent_actions (10)
        assert len(self.manager.recent_actions) == self.manager.max_recent_actions
        assert self.manager.recent_actions[0] == "ACTION_5"  # First 5 should be dropped
        assert self.manager.recent_actions[-1] == "ACTION_14"
    
    def test_check_for_stuck_behavior_normal_operation(self):
        """Test stuck detection with normal operation."""
        signature = "CLICK:#button"
        
        # Add actions below threshold
        self.manager.recent_actions = [signature, "OTHER_ACTION", signature]
        
        # Should not raise exception
        self.manager._check_for_stuck_behavior(signature)
    
    def test_check_for_stuck_behavior_detects_stuck(self):
        """Test stuck detection when threshold is exceeded."""
        signature = "CLICK:#button"
        
        # Add actions at threshold level
        self.manager.recent_actions = [signature] * self.manager.stuck_threshold
        
        with pytest.raises(RuntimeError, match="Automation stuck in loop"):
            self.manager._check_for_stuck_behavior(signature)
    
    def test_check_for_stuck_behavior_mixed_actions(self):
        """Test stuck detection with mixed actions."""
        signature = "CLICK:#button"
        
        # Add mixed actions with target signature appearing stuck_threshold times
        self.manager.recent_actions = [
            signature, "OTHER_ACTION", signature, "ANOTHER_ACTION", signature
        ]
        
        with pytest.raises(RuntimeError, match="Automation stuck in loop"):
            self.manager._check_for_stuck_behavior(signature)


class TestWebManagerIntegration:
    """Test integration with stuck detection during execution."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {}
        self.config_provider = ConfigProvider(config_dict)
        
        with patch('lamia.engine.managers.web.web_manager.BrowserManager') as mock_browser_class:
            with patch('lamia.engine.managers.web.web_manager.HttpManager') as mock_http_class:
                self.mock_browser_manager = Mock()
                self.mock_http_manager = Mock()
                mock_browser_class.return_value = self.mock_browser_manager
                mock_http_class.return_value = self.mock_http_manager
                
                self.manager = WebManager(self.config_provider)
    
    @pytest.mark.asyncio
    async def test_stuck_detection_during_execution(self):
        """Test that stuck detection works during actual command execution."""
        command = WebCommand(action=WebActionType.CLICK, selector="#button")
        
        # Pre-populate recent actions to be at threshold
        signature = "WebActionType.CLICK:#button"
        self.manager.recent_actions = [signature] * (self.manager.stuck_threshold - 1)
        
        # First execution should work
        self.mock_browser_manager.execute = AsyncMock(return_value="Success")
        result1 = await self.manager.execute(command)
        assert result1.is_valid is True
        
        # Second execution should detect stuck behavior and raise exception
        # After the first execution, we should have stuck_threshold - 1 + 1 = stuck_threshold actions
        # The next execution should check for stuck behavior before executing
        with pytest.raises(RuntimeError, match="Automation stuck in loop"):
            await self.manager.execute(command)
    
    @pytest.mark.asyncio
    async def test_successful_execution_flow(self):
        """Test complete successful execution flow."""
        command = WebCommand(action=WebActionType.GET_TEXT, selector="#content")
        validator = Mock(spec=BaseValidator)
        
        browser_result = "Retrieved text content"
        self.mock_browser_manager.execute = AsyncMock(return_value=browser_result)
        
        validation_result = ValidationResult(
            is_valid=True,
            raw_text=browser_result,
            validated_text=browser_result,
            execution_context=Mock()
        )
        validator.validate = AsyncMock(return_value=validation_result)
        
        result = await self.manager.execute(command, validator=validator)
        
        # Verify execution flow
        self.mock_browser_manager.execute.assert_called_once_with(command, validator)
        # Should validate the result and return the validation result
        validator.validate.assert_called_once_with(browser_result)
        assert result == validation_result
        
        # Verify action was tracked
        assert "WebActionType.GET_TEXT:#content" in self.manager.recent_actions


class TestWebManagerCleanup:
    """Test WebManager cleanup and resource management."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {}
        self.config_provider = ConfigProvider(config_dict)
        
        with patch('lamia.engine.managers.web.web_manager.BrowserManager') as mock_browser_class:
            with patch('lamia.engine.managers.web.web_manager.HttpManager') as mock_http_class:
                self.mock_browser_manager = Mock()
                self.mock_http_manager = Mock()
                mock_browser_class.return_value = self.mock_browser_manager
                mock_http_class.return_value = self.mock_http_manager
                
                self.manager = WebManager(self.config_provider)
    
    @pytest.mark.asyncio
    async def test_close_cleans_up_sub_managers(self):
        """Test that close method cleans up all sub-managers."""
        self.mock_browser_manager.close = AsyncMock()
        self.mock_http_manager.close = AsyncMock()
        
        await self.manager.close()
        
        # Both sub-managers should be closed
        self.mock_browser_manager.close.assert_called_once()
        self.mock_http_manager.close.assert_called_once()


class TestWebManagerEdgeCases:
    """Test edge cases and error conditions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {}
        self.config_provider = ConfigProvider(config_dict)
        
        with patch('lamia.engine.managers.web.web_manager.BrowserManager') as mock_browser_class:
            with patch('lamia.engine.managers.web.web_manager.HttpManager') as mock_http_class:
                self.mock_browser_manager = Mock()
                self.mock_http_manager = Mock()
                mock_browser_class.return_value = self.mock_browser_manager
                mock_http_class.return_value = self.mock_http_manager
                
                self.manager = WebManager(self.config_provider)
    
    @pytest.mark.asyncio
    async def test_execute_with_long_result_truncation(self):
        """Test result truncation for logging when result is very long."""
        command = WebCommand(action=WebActionType.GET_PAGE_SOURCE)
        
        # Create a very long result
        long_result = "x" * 2000
        self.mock_browser_manager.execute = AsyncMock(return_value=long_result)
        
        with patch('lamia.engine.managers.web.web_manager.logger') as mock_logger:
            result = await self.manager.execute(command, validator=None)
            
            # Should succeed
            assert result.is_valid is True
            assert result.typed_result == long_result
    
    def test_get_action_signature_with_empty_attributes(self):
        """Test action signature generation with empty attributes."""
        command = Mock()
        command.action = WebActionType.CLICK
        command.selector = ""
        command.value = ""
        command.text = ""
        command.scope_element_handle = None
        
        signature = self.manager._get_action_signature(command)
        assert signature == "WebActionType.CLICK"
    
    def test_get_action_signature_with_missing_attributes(self):
        """Test action signature generation with missing attributes."""
        command = Mock()
        command.action = WebActionType.NAVIGATE
        command.selector = None
        command.value = None
        command.text = None
        command.scope_element_handle = None
        
        signature = self.manager._get_action_signature(command)
        assert signature == "WebActionType.NAVIGATE"
    
    @pytest.mark.asyncio
    async def test_execute_with_validator_error_handling(self):
        """Test execution when validator raises an exception."""
        command = WebCommand(action=WebActionType.CLICK, selector="#button")
        validator = Mock(spec=BaseValidator)
        
        self.mock_browser_manager.execute = AsyncMock(return_value="Success")
        validator.validate.side_effect = RuntimeError("Validation failed")
        
        with pytest.raises(RuntimeError, match="Validation failed"):
            await self.manager.execute(command, validator=validator)
    
    @pytest.mark.asyncio
    async def test_execute_with_none_result(self):
        """Test execution when sub-manager returns None."""
        command = WebCommand(action=WebActionType.CLICK, selector="#button")
        
        self.mock_browser_manager.execute = AsyncMock(return_value=None)
        
        result = await self.manager.execute(command, validator=None)
        
        assert result.is_valid is True
        assert result.typed_result is None
        assert result.error_message is None


class TestWebManagerConfiguration:
    """Test WebManager configuration handling."""
    
    def test_initialization_uses_config_for_sub_managers(self):
        """Test that WebManager passes config to sub-managers correctly."""
        web_config = {
            'browser_engine': 'playwright',
            'timeout': 60,
            'http_timeout': 30
        }
        config_dict = {'web_config': web_config}
        config_provider = ConfigProvider(config_dict)
        
        with patch('lamia.engine.managers.web.web_manager.BrowserManager') as mock_browser:
            with patch('lamia.engine.managers.web.web_manager.HttpManager') as mock_http:
                manager = WebManager(config_provider)
                
                # Sub-managers should be initialized with the same config provider
                mock_browser.assert_called_once_with(config_provider, web_manager=manager)
                mock_http.assert_called_once_with(config_provider)
    
    def test_stuck_detection_parameters_are_configurable(self):
        """Test that stuck detection parameters can be modified."""
        config_dict = {}
        config_provider = ConfigProvider(config_dict)
        
        with patch('lamia.engine.managers.web.web_manager.BrowserManager'):
            with patch('lamia.engine.managers.web.web_manager.HttpManager'):
                manager = WebManager(config_provider)
                
                # Modify stuck detection parameters
                manager.max_recent_actions = 20
                manager.stuck_threshold = 5
                
                # Test with modified parameters
                signature = "TEST_ACTION"
                for i in range(25):
                    manager._track_action(f"ACTION_{i}")
                
                # Should only keep 20 actions
                assert len(manager.recent_actions) == 20
                
                # Test stuck detection with new threshold
                manager.recent_actions = [signature] * 5
                
                with pytest.raises(RuntimeError, match="Automation stuck in loop"):
                    manager._check_for_stuck_behavior(signature)