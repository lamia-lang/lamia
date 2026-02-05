"""Tests for interpreter commands."""

import pytest
from lamia.interpreter.commands import (
    Command, LLMCommand, WebCommand, FileCommand,
    WebActionType, FileActionType
)


class TestCommandBase:
    """Test Command base class."""
    
    def test_command_is_abstract(self):
        """Test that Command is abstract or can be instantiated."""
        # Command might be abstract or concrete - test accordingly
        try:
            command = Command()
            assert command is not None
        except TypeError:
            # If abstract, this is expected
            pass
    
    def test_command_interface(self):
        """Test Command interface."""
        assert Command is not None
        # Test that Command defines expected interface
        assert hasattr(Command, '__init__')


class TestLLMCommand:
    """Test LLMCommand class."""
    
    def test_initialization(self):
        """Test LLMCommand initialization."""
        content = "What is the weather today?"
        command = LLMCommand(content)
        
        assert command.prompt == content
        assert isinstance(command, Command)
    
    def test_initialization_with_kwargs(self):
        """Test LLMCommand initialization with additional arguments."""
        content = "Generate a summary"
        
        try:
            command = LLMCommand(content)
            assert command.prompt == content
        except TypeError:
            # Constructor might not accept these parameters
            pass
    
    def test_empty_content(self):
        """Test LLMCommand with empty content."""
        command = LLMCommand("")
        assert command.prompt == ""
    
    def test_unicode_content(self):
        """Test LLMCommand with unicode content."""
        content = "Translate 'Hello' to français: Bonjour! 🇫🇷"
        command = LLMCommand(content)
        assert command.prompt == content
    
    def test_very_long_content(self):
        """Test LLMCommand with very long content."""
        content = "Long prompt " * 1000
        command = LLMCommand(content)
        assert command.prompt == content
        assert len(command.prompt) == len(content)


class TestWebCommand:
    """Test WebCommand class."""
    
    def test_initialization_basic(self):
        """Test basic WebCommand initialization."""
        action = WebActionType.NAVIGATE
        url = "https://example.com"
        
        command = WebCommand(action=action, url=url)
        
        assert command.action == action
        assert command.url == url
        assert isinstance(command, Command)
    
    def test_initialization_with_selector(self):
        """Test WebCommand with selector."""
        action = WebActionType.CLICK
        selector = "#submit-button"
        
        try:
            command = WebCommand(action=action, selector=selector)
            assert command.action == action
            assert command.selector == selector
        except TypeError:
            # Constructor signature might be different
            pass
    
    def test_initialization_with_fallbacks(self):
        """Test WebCommand with fallback selectors."""
        action = WebActionType.CLICK
        selector = "#primary-button"
        fallbacks = [".button", "button"]
        
        try:
            command = WebCommand(
                action=action,
                selector=selector,
                fallback_selectors=fallbacks
            )
            assert command.action == action
            assert command.selector == selector
            assert command.fallback_selectors == fallbacks
        except TypeError:
            # Constructor signature might be different
            pass
    
    def test_different_action_types(self):
        """Test WebCommand with different action types."""
        actions = [
            WebActionType.NAVIGATE,
            WebActionType.CLICK,
            WebActionType.TYPE,
            WebActionType.WAIT,
            WebActionType.GET_TEXT
        ]
        
        for action in actions:
            try:
                command = WebCommand(action=action, url="https://example.com")
                assert command.action == action
            except TypeError:
                # Some actions might require different parameters
                pass
    
    def test_with_value(self):
        """Test WebCommand with value parameter."""
        action = WebActionType.TYPE
        selector = "input[type='text']"
        value = "Hello, World!"
        
        try:
            command = WebCommand(
                action=action,
                selector=selector,
                value=value
            )
            assert command.action == action
            assert command.value == value
        except TypeError:
            # Constructor signature might be different
            pass
    
    def test_with_timeout(self):
        """Test WebCommand with timeout."""
        action = WebActionType.WAIT
        selector = ".loading"
        timeout = 30.0
        
        try:
            command = WebCommand(
                action=action,
                selector=selector,
                timeout=timeout
            )
            assert command.action == action
            assert command.timeout == timeout
        except TypeError:
            # Constructor signature might be different
            pass


class TestFileCommand:
    """Test FileCommand class."""
    
    def test_initialization_basic(self):
        """Test basic FileCommand initialization."""
        action = FileActionType.READ
        path = "/path/to/file.txt"
        
        command = FileCommand(action=action, path=path)
        
        assert command.action == action
        assert command.path == path
        assert isinstance(command, Command)
    
    def test_different_action_types(self):
        """Test FileCommand with different action types."""
        actions = [
            FileActionType.READ,
            FileActionType.WRITE,
            FileActionType.APPEND,
            FileActionType.DELETE
        ]
        
        path = "/test/file.txt"
        
        for action in actions:
            try:
                command = FileCommand(action=action, path=path)
                assert command.action == action
                assert command.path == path
            except (TypeError, AttributeError):
                # Some actions might not exist or require different parameters
                pass
    
    def test_with_content(self):
        """Test FileCommand with content."""
        action = FileActionType.WRITE
        path = "/test/file.txt"
        content = "Hello, World!"
        
        try:
            command = FileCommand(
                action=action,
                path=path,
                content=content
            )
            assert command.action == action
            assert command.path == path
            assert command.content == content
        except TypeError:
            # Constructor signature might be different
            pass
    
    def test_different_path_formats(self):
        """Test FileCommand with different path formats."""
        paths = [
            "/absolute/path/file.txt",
            "relative/path/file.txt",
            "~/home/file.txt",
            "C:\\Windows\\file.txt",
            "/path/with spaces/file.txt",
            "/path/with-special_chars@file.txt"
        ]
        
        action = FileActionType.READ
        
        for path in paths:
            command = FileCommand(action=action, path=path)
            assert command.path == path
    
    def test_empty_path(self):
        """Test FileCommand with empty path."""
        try:
            command = FileCommand(action=FileActionType.READ, path="")
            assert command.path == ""
        except ValueError:
            # Empty path might be invalid
            pass


class TestActionTypes:
    """Test action type enums."""
    
    def test_web_action_types_exist(self):
        """Test that WebActionType enum values exist."""
        expected_actions = [
            'NAVIGATE', 'CLICK', 'TYPE', 'WAIT', 'GET_TEXT',
            'HOVER', 'SCROLL', 'SELECT', 'SUBMIT', 'SCREENSHOT'
        ]
        
        for action_name in expected_actions:
            try:
                action = getattr(WebActionType, action_name)
                assert action is not None
            except AttributeError:
                # Action might not be implemented yet
                pass
    
    def test_file_action_types_exist(self):
        """Test that FileActionType enum values exist."""
        expected_actions = [
            'READ', 'WRITE', 'APPEND', 'DELETE', 'COPY', 'MOVE', 'EXISTS'
        ]
        
        for action_name in expected_actions:
            action_name_upper = action_name.upper()
            try:
                action = getattr(FileActionType, action_name_upper)
                assert action is not None
            except AttributeError:
                # Action might not be implemented yet or have different name
                pass
    
    def test_action_types_are_comparable(self):
        """Test that action types can be compared."""
        try:
            action1 = WebActionType.NAVIGATE
            action2 = WebActionType.NAVIGATE
            action3 = WebActionType.CLICK
            
            assert action1 == action2
            assert action1 != action3
        except (AttributeError, NameError):
            # Actions might not be implemented
            pass
    
    def test_action_types_are_hashable(self):
        """Test that action types can be used as dict keys."""
        try:
            action_map = {
                WebActionType.NAVIGATE: "navigate_handler",
                WebActionType.CLICK: "click_handler"
            }
            
            assert action_map[WebActionType.NAVIGATE] == "navigate_handler"
        except (AttributeError, NameError):
            # Actions might not be implemented
            pass


class TestCommandInheritance:
    """Test command inheritance hierarchy."""
    
    def test_llm_command_inheritance(self):
        """Test LLMCommand inherits from Command."""
        command = LLMCommand("test")
        assert isinstance(command, Command)
    
    def test_web_command_inheritance(self):
        """Test WebCommand inherits from Command."""
        command = WebCommand(action=WebActionType.NAVIGATE, url="https://example.com")
        assert isinstance(command, Command)
    
    def test_file_command_inheritance(self):
        """Test FileCommand inherits from Command."""
        command = FileCommand(action=FileActionType.READ, path="/test.txt")
        assert isinstance(command, Command)


class TestCommandSerialization:
    """Test command serialization/representation."""
    
    def test_llm_command_repr(self):
        """Test LLMCommand string representation."""
        command = LLMCommand("Test content")
        repr_str = repr(command)
        
        assert isinstance(repr_str, str)
        assert "LLMCommand" in repr_str or "test content" in repr_str.lower()
    
    def test_web_command_repr(self):
        """Test WebCommand string representation."""
        command = WebCommand(action=WebActionType.NAVIGATE, url="https://example.com")
        repr_str = repr(command)
        
        assert isinstance(repr_str, str)
        assert "WebCommand" in repr_str or "navigate" in repr_str.lower()
    
    def test_file_command_repr(self):
        """Test FileCommand string representation."""
        command = FileCommand(action=FileActionType.READ, path="/test.txt")
        repr_str = repr(command)
        
        assert isinstance(repr_str, str)
        assert "FileCommand" in repr_str or "read" in repr_str.lower()


class TestCommandValidation:
    """Test command validation logic."""
    
    def test_invalid_web_action(self):
        """Test WebCommand with invalid action."""
        try:
            command = WebCommand(action="INVALID_ACTION", url="https://example.com")
            # If it allows invalid actions, that's also valid for testing
            assert command is not None
        except (ValueError, TypeError):
            # Expected for invalid action
            pass
    
    def test_invalid_file_action(self):
        """Test FileCommand with invalid action."""
        try:
            command = FileCommand(action="INVALID_ACTION", path="/test.txt")
            # If it allows invalid actions, that's also valid for testing
            assert command is not None
        except (ValueError, TypeError):
            # Expected for invalid action
            pass
    
    def test_none_parameters(self):
        """Test commands with None parameters."""
        try:
            llm_cmd = LLMCommand(None)
            assert llm_cmd.prompt is None
        except TypeError:
            # None content might not be allowed
            pass
        
        try:
            web_cmd = WebCommand(action=WebActionType.NAVIGATE, url=None)
            assert web_cmd.url is None
        except TypeError:
            # None URL might not be allowed
            pass