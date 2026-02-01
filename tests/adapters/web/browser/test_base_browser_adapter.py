"""Comprehensive tests for BaseBrowserAdapter abstract interface."""

import pytest
from unittest.mock import Mock, AsyncMock
from lamia.adapters.web.browser.base import (
    BaseBrowserAdapter, 
    DOM_STABLE_MUTATION_QUIET_MS,
    DOM_STABILITY_TRACKER_BOOTSTRAP,
    DOM_STABILITY_CHECK_SCRIPT
)
from lamia.internal_types import BrowserActionParams, SelectorType
from typing import Any


class ConcreteBrowserAdapter(BaseBrowserAdapter):
    """Concrete implementation for testing abstract methods."""
    
    def __init__(self):
        self.initialized = False
        self.profile_name = None
        
    async def initialize(self) -> None:
        self.initialized = True
    
    async def close(self) -> None:
        self.initialized = False
    
    async def navigate(self, params: BrowserActionParams) -> None:
        return f"navigated to {params.value}"
    
    async def click(self, params: BrowserActionParams) -> None:
        return f"clicked {params.selector}"
    
    async def type_text(self, params: BrowserActionParams) -> None:
        return f"typed {params.value} into {params.selector}"
    
    async def upload_file(self, params: BrowserActionParams) -> None:
        return f"uploaded {params.value} to {params.selector}"
    
    async def wait_for_element(self, params: BrowserActionParams) -> None:
        return f"waited for {params.selector}"
    
    async def get_text(self, params: BrowserActionParams) -> str:
        return f"text from {params.selector}"
    
    async def get_attribute(self, params: BrowserActionParams) -> str:
        return f"attribute {params.value} from {params.selector}"
    
    async def is_visible(self, params: BrowserActionParams) -> bool:
        return True
    
    async def is_enabled(self, params: BrowserActionParams) -> bool:
        return True
    
    async def hover(self, params: BrowserActionParams) -> None:
        return f"hovered over {params.selector}"
    
    async def scroll(self, params: BrowserActionParams) -> None:
        return f"scrolled to {params.selector}"
    
    async def select_option(self, params: BrowserActionParams) -> None:
        return f"selected {params.value} in {params.selector}"
    
    async def submit_form(self, params: BrowserActionParams) -> None:
        return f"submitted form {params.selector}"
    
    async def take_screenshot(self, params: BrowserActionParams) -> str:
        return params.value or "screenshot.png"
    
    async def get_current_url(self) -> str:
        return "https://current.url.com"
    
    async def get_page_source(self) -> str:
        return "<html><body>Test content</body></html>"
    
    def set_profile(self, profile_name: str) -> None:
        self.profile_name = profile_name
    
    async def load_session_state(self) -> None:
        return f"loaded session for {self.profile_name}"
    
    async def save_session_state(self) -> None:
        return f"saved session for {self.profile_name}"
    
    async def execute_script(self, script: str) -> Any:
        return f"executed script: {script}"


class TestBaseBrowserAdapterConstants:
    """Test BaseBrowserAdapter constants and configuration."""
    
    def test_dom_stability_constants(self):
        """Test DOM stability configuration constants."""
        assert DOM_STABLE_MUTATION_QUIET_MS == 500.0
        assert isinstance(DOM_STABLE_MUTATION_QUIET_MS, float)
    
    def test_dom_tracker_bootstrap_script(self):
        """Test DOM tracker bootstrap script structure."""
        assert isinstance(DOM_STABILITY_TRACKER_BOOTSTRAP, str)
        assert "__lamiaDomTracker" in DOM_STABILITY_TRACKER_BOOTSTRAP
        assert "pendingFetches" in DOM_STABILITY_TRACKER_BOOTSTRAP
        assert "pendingXhrs" in DOM_STABILITY_TRACKER_BOOTSTRAP
        assert "lastMutationTs" in DOM_STABILITY_TRACKER_BOOTSTRAP
        assert "MutationObserver" in DOM_STABILITY_TRACKER_BOOTSTRAP
        assert "XMLHttpRequest" in DOM_STABILITY_TRACKER_BOOTSTRAP
        assert "fetch" in DOM_STABILITY_TRACKER_BOOTSTRAP
    
    def test_dom_stability_check_script(self):
        """Test DOM stability check script structure."""
        assert isinstance(DOM_STABILITY_CHECK_SCRIPT, str)
        assert "__lamiaDomTracker" in DOM_STABILITY_CHECK_SCRIPT
        assert "readyStateComplete" in DOM_STABILITY_CHECK_SCRIPT
        assert "pendingFetches" in DOM_STABILITY_CHECK_SCRIPT
        assert "pendingXhrs" in DOM_STABILITY_CHECK_SCRIPT
        assert "timeSinceMutation" in DOM_STABILITY_CHECK_SCRIPT
        assert "performance.now()" in DOM_STABILITY_CHECK_SCRIPT
    
    def test_scripts_are_javascript_compatible(self):
        """Test that scripts are valid JavaScript format."""
        # Basic JavaScript syntax checks - strip leading whitespace
        assert DOM_STABILITY_TRACKER_BOOTSTRAP.strip().startswith("(")
        assert DOM_STABILITY_TRACKER_BOOTSTRAP.strip().endswith(";")
        assert DOM_STABILITY_CHECK_SCRIPT.strip().startswith("(")
        assert DOM_STABILITY_CHECK_SCRIPT.strip().endswith(";")


class TestBaseBrowserAdapterAbstractMethods:
    """Test BaseBrowserAdapter abstract interface."""
    
    def test_cannot_instantiate_abstract_class(self):
        """Test that BaseBrowserAdapter cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class.*abstract methods.*"):
            BaseBrowserAdapter()
    
    def test_abstract_methods_present(self):
        """Test that all expected abstract methods are defined."""
        abstract_methods = BaseBrowserAdapter.__abstractmethods__
        expected_methods = {
            'initialize', 'close', 'navigate', 'click', 'type_text', 
            'upload_file', 'wait_for_element', 'get_text', 'get_attribute',
            'is_visible', 'is_enabled', 'hover', 'scroll', 'select_option',
            'submit_form', 'take_screenshot', 'get_current_url', 'get_page_source',
            'set_profile', 'load_session_state', 'save_session_state', 
            'execute_script'
        }
        
        assert abstract_methods == expected_methods
    
    def test_concrete_implementation_instantiates(self):
        """Test that concrete implementation can be instantiated."""
        adapter = ConcreteBrowserAdapter()
        assert isinstance(adapter, BaseBrowserAdapter)
        assert not adapter.initialized


class TestBaseBrowserAdapterInterface:
    """Test BaseBrowserAdapter interface through concrete implementation."""
    
    @pytest.fixture
    def adapter(self):
        """Create concrete adapter for testing."""
        return ConcreteBrowserAdapter()
    
    @pytest.fixture
    def browser_params(self):
        """Create basic browser parameters."""
        return BrowserActionParams(
            selector="#test-element",
            selector_type=SelectorType.CSS,
            value="test value",
            timeout=10.0,
            wait_condition="visible"
        )
    
    @pytest.mark.asyncio
    async def test_lifecycle_methods(self, adapter):
        """Test initialization and cleanup lifecycle."""
        # Initial state
        assert not adapter.initialized
        
        # Initialize
        await adapter.initialize()
        assert adapter.initialized
        
        # Close
        await adapter.close()
        assert not adapter.initialized
    
    @pytest.mark.asyncio
    async def test_navigation_methods(self, adapter, browser_params):
        """Test navigation method interface."""
        nav_params = BrowserActionParams(value="https://example.com")
        result = await adapter.navigate(nav_params)
        
        assert "navigated to https://example.com" in str(result)
    
    @pytest.mark.asyncio
    async def test_interaction_methods(self, adapter, browser_params):
        """Test interaction method interfaces."""
        click_result = await adapter.click(browser_params)
        type_result = await adapter.type_text(browser_params)
        hover_result = await adapter.hover(browser_params)
        
        assert "clicked" in str(click_result)
        assert "typed" in str(type_result)
        assert "hovered" in str(hover_result)
    
    @pytest.mark.asyncio
    async def test_element_query_methods(self, adapter, browser_params):
        """Test element query method interfaces."""
        text = await adapter.get_text(browser_params)
        attribute = await adapter.get_attribute(browser_params)
        visible = await adapter.is_visible(browser_params)
        enabled = await adapter.is_enabled(browser_params)
        
        assert isinstance(text, str)
        assert isinstance(attribute, str)
        assert isinstance(visible, bool)
        assert isinstance(enabled, bool)
    
    @pytest.mark.asyncio
    async def test_form_interaction_methods(self, adapter, browser_params):
        """Test form interaction method interfaces."""
        select_result = await adapter.select_option(browser_params)
        submit_result = await adapter.submit_form(browser_params)
        upload_result = await adapter.upload_file(browser_params)
        
        assert "selected" in str(select_result)
        assert "submitted" in str(submit_result)
        assert "uploaded" in str(upload_result)
    
    @pytest.mark.asyncio
    async def test_page_utility_methods(self, adapter, browser_params):
        """Test page utility method interfaces."""
        screenshot = await adapter.take_screenshot(browser_params)
        url = await adapter.get_current_url()
        source = await adapter.get_page_source()
        
        assert isinstance(screenshot, str)
        assert isinstance(url, str)
        assert isinstance(source, str)
    
    @pytest.mark.asyncio
    async def test_session_management_methods(self, adapter):
        """Test session management method interfaces."""
        # Set profile
        adapter.set_profile("test-profile")
        assert adapter.profile_name == "test-profile"
        
        # Session state operations
        load_result = await adapter.load_session_state()
        save_result = await adapter.save_session_state()
        
        assert "loaded session" in str(load_result)
        assert "saved session" in str(save_result)


class TestBrowserActionParamsUsage:
    """Test BrowserActionParams usage with adapter interface."""
    
    @pytest.fixture
    def adapter(self):
        """Create concrete adapter for testing."""
        return ConcreteBrowserAdapter()
    
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
    
    @pytest.mark.asyncio
    async def test_params_with_different_selectors(self, adapter):
        """Test BrowserActionParams with different selector types."""
        css_params = BrowserActionParams(selector=".button", selector_type=SelectorType.CSS)
        xpath_params = BrowserActionParams(selector="//button", selector_type=SelectorType.XPATH)
        id_params = BrowserActionParams(selector="submit-btn", selector_type=SelectorType.ID)
        
        css_result = await adapter.click(css_params)
        xpath_result = await adapter.click(xpath_params)
        id_result = await adapter.click(id_params)
        
        assert ".button" in str(css_result)
        assert "//button" in str(xpath_result)
        assert "submit-btn" in str(id_result)


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
        from abc import ABC
        
        # Should inherit from ABC
        assert issubclass(BaseBrowserAdapter, ABC)
        
        # Concrete implementation should inherit from BaseBrowserAdapter
        adapter = ConcreteBrowserAdapter()
        assert isinstance(adapter, BaseBrowserAdapter)
        assert isinstance(adapter, ABC)


class TestBaseBrowserAdapterDocumentation:
    """Test BaseBrowserAdapter documentation and type annotations."""
    
    def test_class_docstring_exists(self):
        """Test that BaseBrowserAdapter has proper documentation."""
        assert BaseBrowserAdapter.__doc__ is not None
        assert "browser" in BaseBrowserAdapter.__doc__.lower()
        assert "adapter" in BaseBrowserAdapter.__doc__.lower()
    
    def test_abstract_methods_have_docstrings(self):
        """Test that abstract methods have documentation."""
        skip_methods = set()  # Methods that might not have docstrings
        
        for method_name in BaseBrowserAdapter.__abstractmethods__:
            if method_name in skip_methods:
                continue
            method = getattr(BaseBrowserAdapter, method_name)
            assert method.__doc__ is not None, f"Method {method_name} missing docstring"
    
    def test_method_signatures_use_type_annotations(self):
        """Test that methods have proper type annotations."""
        import inspect
        
        # Test some key method signatures
        init_sig = inspect.signature(BaseBrowserAdapter.initialize)
        close_sig = inspect.signature(BaseBrowserAdapter.close)
        click_sig = inspect.signature(BaseBrowserAdapter.click)
        
        # Should return None for action methods
        assert init_sig.return_annotation is None or 'None' in str(init_sig.return_annotation)
        assert close_sig.return_annotation is None or 'None' in str(close_sig.return_annotation)
        assert click_sig.return_annotation is None or 'None' in str(click_sig.return_annotation)
        
        # Should have proper parameter types
        assert 'params' in click_sig.parameters
        assert click_sig.parameters['params'].annotation == BrowserActionParams


class TestBrowserActionParamsIntegration:
    """Test integration between BrowserActionParams and adapter interface."""
    
    @pytest.fixture
    def adapter(self):
        return ConcreteBrowserAdapter()
    
    @pytest.mark.asyncio
    async def test_params_validation_pattern(self, adapter):
        """Test parameter validation pattern usage."""
        # Valid params
        valid_params = BrowserActionParams(selector="#button")
        result = await adapter.click(valid_params)
        assert "clicked #button" in str(result)
    
    @pytest.mark.asyncio
    async def test_multiple_browser_action_calls(self, adapter):
        """Test calling multiple browser actions with same adapter instance."""
        params = BrowserActionParams(
            selector="#form-input",
            selector_type=SelectorType.CSS,
            value="test data",
            timeout=5.0
        )
        
        # Multiple calls should work
        click_result = await adapter.click(params)
        type_result = await adapter.type_text(params)
        hover_result = await adapter.hover(params)
        
        assert "clicked" in str(click_result)
        assert "typed" in str(type_result)
        assert "hovered" in str(hover_result)
        
        # All should use same selector
        assert "#form-input" in str(click_result)
        assert "#form-input" in str(type_result)
        assert "#form-input" in str(hover_result)
    
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


class TestDOMStabilityIntegration:
    """Test DOM stability tracking integration concepts."""
    
    def test_dom_stability_scripts_structure(self):
        """Test that DOM stability scripts have required structure."""
        # Bootstrap script should set up tracking
        assert "window.__lamiaDomTracker" in DOM_STABILITY_TRACKER_BOOTSTRAP
        assert "MutationObserver" in DOM_STABILITY_TRACKER_BOOTSTRAP
        
        # Check script should return status object
        assert "readyStateComplete" in DOM_STABILITY_CHECK_SCRIPT
        assert "pendingFetches" in DOM_STABILITY_CHECK_SCRIPT
        assert "timeSinceMutation" in DOM_STABILITY_CHECK_SCRIPT
    
    def test_dom_stability_constants_reasonable(self):
        """Test that DOM stability timing constants are reasonable."""
        # 500ms quiet window is reasonable for most web apps
        assert 100 <= DOM_STABLE_MUTATION_QUIET_MS <= 2000
        assert isinstance(DOM_STABLE_MUTATION_QUIET_MS, (int, float))
    
    def test_dom_scripts_javascript_syntax(self):
        """Test that DOM scripts use proper JavaScript syntax."""
        # Both scripts should be self-executing functions
        assert DOM_STABILITY_TRACKER_BOOTSTRAP.strip().startswith("(")
        assert DOM_STABILITY_CHECK_SCRIPT.strip().startswith("(")
        
        # Should end properly
        assert DOM_STABILITY_TRACKER_BOOTSTRAP.strip().endswith(";")
        assert DOM_STABILITY_CHECK_SCRIPT.strip().endswith(";")
    
    def test_dom_tracker_covers_async_operations(self):
        """Test that DOM tracker covers common async operations."""
        tracker_script = DOM_STABILITY_TRACKER_BOOTSTRAP
        
        # Should track fetch operations
        assert "window.fetch" in tracker_script
        assert "pendingFetches" in tracker_script
        
        # Should track XMLHttpRequest
        assert "XMLHttpRequest" in tracker_script
        assert "pendingXhrs" in tracker_script
        
        # Should track DOM mutations
        assert "MutationObserver" in tracker_script
        assert "lastMutationTs" in tracker_script