"""Tests for browser base adapter."""

import pytest
from abc import ABC
from unittest.mock import Mock, AsyncMock
from typing import List, Any
from lamia.adapters.web.browser.base import (
    BaseBrowserAdapter,
    DOM_STABLE_MUTATION_QUIET_MS,
    DOM_STABILITY_TRACKER_BOOTSTRAP,
    DOM_STABILITY_CHECK_SCRIPT
)
from lamia.internal_types import BrowserActionParams, SelectorType


class TestBaseBrowserAdapterInterface:
    """Test BaseBrowserAdapter interface."""
    
    def test_is_abstract_base_class(self):
        """Test that BaseBrowserAdapter is an abstract base class."""
        assert issubclass(BaseBrowserAdapter, ABC)
        
        # Should not be able to instantiate directly
        with pytest.raises(TypeError):
            BaseBrowserAdapter()
    
    def test_abstract_methods_exist(self):
        """Test that all required abstract methods are defined."""
        abstract_methods = [
            'initialize', 'close', 'navigate', 'click', 'type_text', 'upload_file',
            'wait_for_element', 'get_text', 'get_attribute', 'is_visible', 'is_enabled',
            'hover', 'scroll', 'select_option', 'submit_form', 'take_screenshot',
            'get_current_url', 'get_page_source', 'set_profile', 'load_session_state',
            'save_session_state'
        ]
        
        for method_name in abstract_methods:
            assert hasattr(BaseBrowserAdapter, method_name)
            method = getattr(BaseBrowserAdapter, method_name)
            assert callable(method)
    
    def test_dom_stability_constants(self):
        """Test DOM stability constants."""
        assert isinstance(DOM_STABLE_MUTATION_QUIET_MS, float)
        assert DOM_STABLE_MUTATION_QUIET_MS == 500.0
        
        assert isinstance(DOM_STABILITY_TRACKER_BOOTSTRAP, str)
        assert "window.__lamiaDomTracker" in DOM_STABILITY_TRACKER_BOOTSTRAP
        
        assert isinstance(DOM_STABILITY_CHECK_SCRIPT, str)
        assert "timeSinceMutation" in DOM_STABILITY_CHECK_SCRIPT


class MockBrowserAdapter(BaseBrowserAdapter):
    """Mock implementation for testing."""
    
    def __init__(self):
        self.initialized = False
        self.closed = False
        self.current_url = "about:blank"
        self.page_source = "<html><body></body></html>"
        self.profile_name = None
        self.session_loaded = False
        self.session_saved = False
    
    async def initialize(self):
        self.initialized = True
    
    async def close(self):
        self.closed = True
    
    async def navigate(self, params: BrowserActionParams):
        if params.value:
            self.current_url = params.value
    
    async def click(self, params: BrowserActionParams):
        pass
    
    async def type_text(self, params: BrowserActionParams):
        pass
    
    async def upload_file(self, params: BrowserActionParams):
        pass
    
    async def wait_for_element(self, params: BrowserActionParams):
        pass
    
    async def get_text(self, params: BrowserActionParams) -> str:
        return "sample text"
    
    async def get_attribute(self, params: BrowserActionParams) -> str:
        return "sample attribute"
    
    async def is_visible(self, params: BrowserActionParams) -> bool:
        return True
    
    async def is_enabled(self, params: BrowserActionParams) -> bool:
        return True
    
    async def hover(self, params: BrowserActionParams):
        pass
    
    async def scroll(self, params: BrowserActionParams):
        pass
    
    async def select_option(self, params: BrowserActionParams):
        pass
    
    async def submit_form(self, params: BrowserActionParams):
        pass
    
    async def take_screenshot(self, params: BrowserActionParams) -> str:
        return "/path/to/screenshot.png"
    
    async def get_current_url(self) -> str:
        return self.current_url
    
    async def get_page_source(self) -> str:
        return self.page_source
    
    def set_profile(self, profile_name):
        self.profile_name = profile_name
    
    async def load_session_state(self):
        self.session_loaded = True
    
    async def save_session_state(self):
        self.session_saved = True

    async def execute_script(self, script: str):
        pass

    async def get_elements(self, params: BrowserActionParams) -> List[Any]:
        return []
    
    async def get_input_type(self, params: BrowserActionParams) -> str:
        return ""
    
    async def get_options(self, params: BrowserActionParams) -> List[str]:
        return []
    
    async def is_checked(self, params: BrowserActionParams) -> bool:
        return False


@pytest.mark.asyncio
class TestBaseBrowserAdapterImplementation:
    """Test implementation behavior through mock adapter."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = MockBrowserAdapter()
    
    async def test_initialization(self):
        """Test adapter initialization."""
        assert not self.adapter.initialized
        await self.adapter.initialize()
        assert self.adapter.initialized
    
    async def test_close(self):
        """Test adapter close."""
        assert not self.adapter.closed
        await self.adapter.close()
        assert self.adapter.closed
    
    async def test_navigation(self):
        """Test navigation functionality."""
        params = Mock(spec=BrowserActionParams)
        params.value = "https://example.com"
        
        await self.adapter.navigate(params)
        current_url = await self.adapter.get_current_url()
        assert current_url == "https://example.com"
    
    async def test_text_operations(self):
        """Test text-based operations."""
        params = Mock(spec=BrowserActionParams)
        
        text = await self.adapter.get_text(params)
        assert text == "sample text"
        
        attribute = await self.adapter.get_attribute(params)
        assert attribute == "sample attribute"
    
    async def test_visibility_checks(self):
        """Test element visibility and state checks."""
        params = Mock(spec=BrowserActionParams)
        
        visible = await self.adapter.is_visible(params)
        assert visible is True
        
        enabled = await self.adapter.is_enabled(params)
        assert enabled is True
    
    async def test_screenshot(self):
        """Test screenshot functionality."""
        params = Mock(spec=BrowserActionParams)
        
        screenshot_path = await self.adapter.take_screenshot(params)
        assert screenshot_path == "/path/to/screenshot.png"
    
    async def test_page_source(self):
        """Test page source retrieval."""
        source = await self.adapter.get_page_source()
        assert "<html>" in source
        assert "<body>" in source
    
    def test_profile_management(self):
        """Test profile management."""
        assert self.adapter.profile_name is None
        
        self.adapter.set_profile("test_profile")
        assert self.adapter.profile_name == "test_profile"
        
        self.adapter.set_profile(None)
        assert self.adapter.profile_name is None
    
    async def test_session_state_management(self):
        """Test session state loading and saving."""
        assert not self.adapter.session_loaded
        assert not self.adapter.session_saved
        
        await self.adapter.load_session_state()
        assert self.adapter.session_loaded
        
        await self.adapter.save_session_state()
        assert self.adapter.session_saved
    
    async def test_action_operations(self):
        """Test action operations don't raise errors."""
        params = Mock(spec=BrowserActionParams)
        
        # These should not raise exceptions
        await self.adapter.click(params)
        await self.adapter.type_text(params)
        await self.adapter.upload_file(params)
        await self.adapter.wait_for_element(params)
        await self.adapter.hover(params)
        await self.adapter.scroll(params)
        await self.adapter.select_option(params)
        await self.adapter.submit_form(params)


class TestBrowserActionParams:
    """Test BrowserActionParams interaction."""
    
    @pytest.mark.asyncio
    async def test_params_handling(self):
        """Test that adapters properly handle BrowserActionParams."""
        adapter = MockBrowserAdapter()
        
        # Test with mock params
        params = Mock(spec=BrowserActionParams)
        params.value = "https://test.com"
        params.selector = "#test"
        params.text = "test text"
        params.timeout = 5.0
        
        # Should not raise exceptions
        await adapter.navigate(params)
        await adapter.click(params)
        await adapter.type_text(params)
        
        # Verify URL was set
        current_url = await adapter.get_current_url()
        assert current_url == "https://test.com"


class TestDOMStabilityScripts:
    """Test DOM stability tracking scripts."""
    
    def test_bootstrap_script_content(self):
        """Test DOM stability bootstrap script content."""
        script = DOM_STABILITY_TRACKER_BOOTSTRAP
        
        # Should contain essential tracking components
        assert "window.__lamiaDomTracker" in script
        assert "MutationObserver" in script
        assert "fetch" in script
        assert "XMLHttpRequest" in script
        assert "pendingFetches" in script
        assert "pendingXhrs" in script
        assert "lastMutationTs" in script
    
    def test_check_script_content(self):
        """Test DOM stability check script content."""
        script = DOM_STABILITY_CHECK_SCRIPT
        
        # Should return stability information
        assert "readyStateComplete" in script
        assert "readyState" in script
        assert "pendingFetches" in script
        assert "pendingXhrs" in script
        assert "timeSinceMutation" in script
        assert "return {" in script
    
    def test_scripts_are_functions(self):
        """Test that scripts are wrapped in functions."""
        bootstrap = DOM_STABILITY_TRACKER_BOOTSTRAP.strip()
        check = DOM_STABILITY_CHECK_SCRIPT.strip()
        
        # Both should be wrapped in immediately invoked function expressions
        assert bootstrap.startswith("(() => {")
        assert bootstrap.endswith("})();")
        assert check.startswith("(() => {")
        assert check.endswith("})();")
    
    def test_script_safety(self):
        """Test that scripts don't contain dangerous patterns."""
        scripts = [DOM_STABILITY_TRACKER_BOOTSTRAP, DOM_STABILITY_CHECK_SCRIPT]
        
        for script in scripts:
            # Should not contain dangerous eval or similar patterns
            assert "eval(" not in script
            assert "Function(" not in script
            assert "setTimeout(" not in script  # Should use performance timing
            assert "setInterval(" not in script


class TestBaseBrowserAdapterDocumentation:
    """Test documentation and method signatures."""
    
    def test_method_documentation(self):
        """Test that key methods have documentation."""
        methods_with_docs = [
            'initialize', 'close', 'navigate', 'click', 'type_text',
            'get_text', 'take_screenshot'
        ]
        
        for method_name in methods_with_docs:
            method = getattr(BaseBrowserAdapter, method_name)
            assert method.__doc__ is not None
            assert len(method.__doc__.strip()) > 0
    
    def test_method_parameters(self):
        """Test method parameter expectations."""
        # Most methods should accept BrowserActionParams
        params_methods = [
            'navigate', 'click', 'type_text', 'upload_file', 'wait_for_element',
            'get_text', 'get_attribute', 'is_visible', 'is_enabled', 'hover',
            'scroll', 'select_option', 'submit_form', 'take_screenshot'
        ]
        
        for method_name in params_methods:
            method = getattr(BaseBrowserAdapter, method_name)
            # Check that method has parameters (can't check signature of abstract methods easily)
            assert method.__name__ == method_name
    
    def test_return_type_methods(self):
        """Test methods that should return specific types."""
        # Methods that return strings
        string_methods = ['get_text', 'get_attribute', 'take_screenshot', 
                         'get_current_url', 'get_page_source']
        
        for method_name in string_methods:
            method = getattr(BaseBrowserAdapter, method_name)
            # Just verify method exists and has documentation
            assert method.__doc__ is not None, f"Method {method_name} should have documentation"
        
        # Methods that return booleans
        bool_methods = ['is_visible', 'is_enabled']
        
        for method_name in bool_methods:
            method = getattr(BaseBrowserAdapter, method_name)
            # Just verify method exists and has documentation
            assert method.__doc__ is not None, f"Method {method_name} should have documentation"


class TestBaseBrowserAdapterProtocol:
    """Test BaseBrowserAdapter follows expected protocol patterns."""
    
    def test_adapter_is_abstract_base_class(self):
        """Test that BaseBrowserAdapter is properly configured as ABC."""
        assert hasattr(BaseBrowserAdapter, '__abstractmethods__')
        assert len(BaseBrowserAdapter.__abstractmethods__) > 0
    
    def test_browser_action_methods_defined(self):
        """Test that all browser action methods are defined as abstract."""
        abstract_methods = BaseBrowserAdapter.__abstractmethods__
        action_methods = {
            'click', 'type_text', 'upload_file', 'hover', 'scroll',
            'select_option', 'submit_form', 'navigate'
        }
        
        assert action_methods.issubset(abstract_methods)
    
    def test_element_query_methods_defined(self):
        """Test that element query methods are defined as abstract."""
        abstract_methods = BaseBrowserAdapter.__abstractmethods__
        query_methods = {
            'get_text', 'get_attribute', 'is_visible', 'is_enabled',
            'wait_for_element'
        }
        
        assert query_methods.issubset(abstract_methods)
    
    def test_page_methods_defined(self):
        """Test that page methods are defined as abstract."""
        abstract_methods = BaseBrowserAdapter.__abstractmethods__
        page_methods = {
            'get_current_url', 'get_page_source', 'take_screenshot'
        }
        
        assert page_methods.issubset(abstract_methods)
    
    def test_session_methods_defined(self):
        """Test that session management methods are defined as abstract."""
        abstract_methods = BaseBrowserAdapter.__abstractmethods__
        session_methods = {
            'set_profile', 'load_session_state', 'save_session_state'
        }
        
        assert session_methods.issubset(abstract_methods)
    
    def test_lifecycle_methods_defined(self):
        """Test that lifecycle methods are defined as abstract."""
        abstract_methods = BaseBrowserAdapter.__abstractmethods__
        lifecycle_methods = {'initialize', 'close'}
        
        assert lifecycle_methods.issubset(abstract_methods)
    
    def test_adapter_inheritance_hierarchy(self):
        """Test BaseBrowserAdapter inheritance and type checking."""
        # Should inherit from ABC
        assert issubclass(BaseBrowserAdapter, ABC)
        
        # Concrete implementation should inherit from BaseBrowserAdapter
        adapter = MockBrowserAdapter()
        assert isinstance(adapter, BaseBrowserAdapter)
        assert isinstance(adapter, ABC)


class TestBrowserActionParamsUsage:
    """Test BrowserActionParams usage with adapter interface."""
    
    @pytest.fixture
    def adapter(self):
        """Create mock adapter for testing."""
        return MockBrowserAdapter()
    
    def test_browser_params_with_minimal_data(self):
        """Test BrowserActionParams with minimal required data."""
        params = BrowserActionParams(selector="#element")
        
        assert params.selector == "#element"
        assert params.selector_type == SelectorType.CSS  # default
        assert params.value is None
        assert params.timeout is None
    
    def test_browser_params_with_complete_data(self):
        """Test BrowserActionParams with all fields."""
        params = BrowserActionParams(
            selector="//div[@id='test']",
            selector_type=SelectorType.XPATH,
            value="test input",
            timeout=15.0,
            wait_condition="clickable",
            fallback_selectors=["#backup", ".alternative"]
        )
        
        assert params.selector == "//div[@id='test']"
        assert params.selector_type == SelectorType.XPATH
        assert params.value == "test input"
        assert params.timeout == 15.0
        assert params.wait_condition == "clickable"
        assert params.fallback_selectors == ["#backup", ".alternative"]
    
    def test_selector_types_enum(self):
        """Test SelectorType enum values."""
        css_params = BrowserActionParams(selector="#test", selector_type=SelectorType.CSS)
        xpath_params = BrowserActionParams(selector="//div", selector_type=SelectorType.XPATH)
        id_params = BrowserActionParams(selector="test", selector_type=SelectorType.ID)
        
        assert css_params.selector_type == SelectorType.CSS
        assert xpath_params.selector_type == SelectorType.XPATH
        assert id_params.selector_type == SelectorType.ID


class TestBrowserActionParamsIntegration:
    """Test integration between BrowserActionParams and adapter interface."""
    
    @pytest.fixture
    def adapter(self):
        return MockBrowserAdapter()
    
    @pytest.mark.asyncio
    async def test_multiple_browser_action_calls(self, adapter):
        """Test calling multiple browser actions with same adapter instance."""
        params = BrowserActionParams(
            selector="#form-input",
            selector_type=SelectorType.CSS,
            value="test data",
            timeout=5.0
        )
        
        # Multiple calls should work without errors
        await adapter.click(params)
        await adapter.type_text(params)
        await adapter.hover(params)
    
    def test_params_type_checking(self):
        """Test BrowserActionParams type checking behavior."""
        # Should be able to create with required fields
        params = BrowserActionParams(selector="#element")
        assert isinstance(params, BrowserActionParams)
        
        # Should have all expected attributes
        assert hasattr(params, 'selector')
        assert hasattr(params, 'selector_type')
        assert hasattr(params, 'value')
        assert hasattr(params, 'timeout')
        assert hasattr(params, 'wait_condition')
    
    @pytest.mark.asyncio
    async def test_complex_browser_scenario(self, adapter):
        """Test complex browser automation scenario."""
        # Navigation
        nav_params = BrowserActionParams(value="https://example.com/form")
        await adapter.navigate(nav_params)
        
        # Form filling
        input_params = BrowserActionParams(
            selector="#username",
            selector_type=SelectorType.ID,
            value="testuser"
        )
        await adapter.type_text(input_params)
        
        # Element interaction
        button_params = BrowserActionParams(
            selector="button[type='submit']",
            selector_type=SelectorType.CSS,
            timeout=10.0
        )
        await adapter.click(button_params)
        
        # Verification
        url = await adapter.get_current_url()
        assert isinstance(url, str)
    
    @pytest.mark.asyncio
    async def test_session_management_workflow(self, adapter):
        """Test session management workflow."""
        # Set profile
        adapter.set_profile("automation-profile")
        
        # Load existing session
        await adapter.load_session_state()
        
        # Perform actions
        params = BrowserActionParams(selector="#content")
        await adapter.click(params)
        
        # Save session
        await adapter.save_session_state()
        
        assert adapter.profile_name == "automation-profile"