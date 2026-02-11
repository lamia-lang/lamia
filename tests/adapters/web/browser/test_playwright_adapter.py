"""Comprehensive tests for PlaywrightAdapter browser implementation."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
import time
from lamia.adapters.web.browser.playwright_adapter import PLAYWRIGHT_AVAILABLE
from lamia.adapters.web.browser.base import BaseBrowserAdapter, DOM_STABLE_MUTATION_QUIET_MS
from lamia.internal_types import BrowserActionParams, SelectorType
from lamia.errors import ExternalOperationTransientError, ExternalOperationPermanentError

pytestmark = pytest.mark.skipif(
    not PLAYWRIGHT_AVAILABLE,
    reason="playwright is not installed",
)

# Import after skip marker so collection doesn't fail when playwright is missing
from lamia.adapters.web.browser.playwright_adapter import PlaywrightAdapter


class TestablePlaywrightAdapter(PlaywrightAdapter):
    """TestablePlaywrightAdapter that implements missing abstract methods for testing."""
    
    def set_profile(self, profile_name):
        """Implementation for testing."""
        self.profile_name = profile_name
        
    async def load_session_state(self):
        """Implementation for testing."""
        if hasattr(self, '_load_session_data'):
            await self._load_session_data()
            
    async def save_session_state(self):
        """Implementation for testing."""
        if hasattr(self, '_save_session_data'):
            await self._save_session_data()


class TestPlaywrightAdapterInitialization:
    """Test PlaywrightAdapter initialization and configuration."""
    
    def test_initialization_with_defaults(self):
        """Test initialization with default parameters."""
        adapter = TestablePlaywrightAdapter()
        
        assert adapter.playwright is None
        assert adapter.browser is None
        assert adapter.context is None
        assert adapter.page is None
        assert adapter.headless is True
        assert adapter.default_timeout == 10000.0
        assert not adapter.initialized
        assert adapter.profile_name == "default"
        assert not adapter.use_persistent_context
    
    def test_initialization_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        session_config = {"enabled": True, "base_dir": "/tmp/sessions"}
        
        adapter = TestablePlaywrightAdapter(
            headless=False,
            timeout=5000.0,
            session_config=session_config,
            profile_name="test-profile"
        )
        
        assert adapter.headless is False
        assert adapter.default_timeout == 5000.0
        assert adapter.profile_name == "test-profile"
        assert adapter.session_manager is not None
        assert adapter.use_persistent_context is True
    
    def test_initialization_without_session_config(self):
        """Test initialization without session configuration."""
        adapter = TestablePlaywrightAdapter()
        
        assert adapter.session_manager is None
        assert not adapter.use_persistent_context
        assert adapter.profile_name == "default"
    
    def test_inheritance_from_base_adapter(self):
        """Test that PlaywrightAdapter inherits from BaseBrowserAdapter."""
        adapter = TestablePlaywrightAdapter()
        assert isinstance(adapter, BaseBrowserAdapter)
        assert isinstance(adapter, PlaywrightAdapter)


class TestPlaywrightAdapterHelperMethods:
    """Test PlaywrightAdapter helper and utility methods."""
    
    @pytest.fixture
    def adapter(self):
        """Create adapter for testing."""
        return TestablePlaywrightAdapter()
    
    def test_require_selector_with_valid_selector(self, adapter):
        """Test _require_selector with valid selector."""
        params = BrowserActionParams(selector="#button")
        result = adapter._require_selector(params)
        
        assert result == "#button"
    
    def test_require_selector_raises_error_without_selector(self, adapter):
        """Test _require_selector raises error when no selector."""
        params = BrowserActionParams(value="some value")
        
        with pytest.raises(ExternalOperationPermanentError, match="Selector is required"):
            adapter._require_selector(params)
    
    def test_has_quiet_dom_window_with_valid_number(self, adapter):
        """Test _has_quiet_dom_window with valid timing."""
        # Greater than threshold
        assert adapter._has_quiet_dom_window(600.0) is True
        
        # Equal to threshold
        assert adapter._has_quiet_dom_window(500.0) is True
        
        # Less than threshold
        assert adapter._has_quiet_dom_window(300.0) is False
    
    def test_has_quiet_dom_window_with_invalid_input(self, adapter):
        """Test _has_quiet_dom_window with invalid input."""
        # Invalid types should default to infinity (True)
        assert adapter._has_quiet_dom_window("invalid") is True
        assert adapter._has_quiet_dom_window(None) is True
        assert adapter._has_quiet_dom_window({}) is True
    
    def test_get_timeout_ms_with_params_timeout(self, adapter):
        """Test _get_timeout_ms with timeout in params."""
        params = BrowserActionParams(selector="#test", timeout=5.0)
        result = adapter._get_timeout_ms(params)
        
        assert result == 5000.0  # 5 seconds to ms
    
    def test_get_timeout_ms_with_default_timeout(self, adapter):
        """Test _get_timeout_ms without timeout in params."""
        params = BrowserActionParams(selector="#test")
        result = adapter._get_timeout_ms(params)
        
        assert result == adapter.default_timeout
    
    def test_get_playwright_selector_css(self, adapter):
        """Test _get_playwright_selector with CSS selector."""
        result = adapter._get_playwright_selector("#button", SelectorType.CSS)
        assert result == "#button"
    
    def test_get_playwright_selector_xpath(self, adapter):
        """Test _get_playwright_selector with XPath selector."""
        result = adapter._get_playwright_selector("//button", SelectorType.XPATH)
        assert result == "xpath=//button"
    
    def test_get_playwright_selector_id(self, adapter):
        """Test _get_playwright_selector with ID selector."""
        result = adapter._get_playwright_selector("submit-btn", SelectorType.ID)
        assert result == "id=submit-btn"
        
        # Should strip leading #
        result = adapter._get_playwright_selector("#submit-btn", SelectorType.ID)
        assert result == "id=submit-btn"
    
    def test_get_playwright_selector_class_name(self, adapter):
        """Test _get_playwright_selector with class name."""
        result = adapter._get_playwright_selector("button", SelectorType.CLASS_NAME)
        assert result == ".button"
        
        # Should handle existing dot
        result = adapter._get_playwright_selector(".button", SelectorType.CLASS_NAME)
        assert result == ".button"
    
    def test_get_playwright_selector_various_types(self, adapter):
        """Test _get_playwright_selector with various selector types."""
        # Tag name
        result = adapter._get_playwright_selector("button", SelectorType.TAG_NAME)
        assert result == "button"
        
        # Name attribute
        result = adapter._get_playwright_selector("username", SelectorType.NAME)
        assert result == "[name='username']"
        
        # Link text
        result = adapter._get_playwright_selector("Click here", SelectorType.LINK_TEXT)
        assert result == "text=Click here"
        
        # Partial link text
        result = adapter._get_playwright_selector("Click", SelectorType.PARTIAL_LINK_TEXT)
        assert result == "text*=Click"


@pytest.mark.asyncio
class TestPlaywrightAdapterDOMStability:
    """Test PlaywrightAdapter DOM stability tracking."""
    
    @pytest.fixture
    def adapter_with_mock_page(self):
        """Create adapter with mocked page for DOM testing."""
        adapter = TestablePlaywrightAdapter()
        adapter.initialized = True
        adapter.page = AsyncMock()
        return adapter
    
    async def test_ensure_dom_tracker_success(self, adapter_with_mock_page):
        """Test _ensure_dom_tracker successful installation."""
        adapter = adapter_with_mock_page
        
        await adapter._ensure_dom_tracker()
        
        adapter.page.evaluate.assert_called_once()
        call_args = adapter.page.evaluate.call_args[0][0]
        assert "__lamiaDomTracker" in call_args
    
    async def test_ensure_dom_tracker_handles_exception(self, adapter_with_mock_page):
        """Test _ensure_dom_tracker handles evaluation errors."""
        adapter = adapter_with_mock_page
        adapter.page.evaluate.side_effect = Exception("Evaluation failed")
        
        # Should not raise exception, just log debug
        await adapter._ensure_dom_tracker()
        
        adapter.page.evaluate.assert_called_once()
    
    async def test_ensure_dom_tracker_without_page(self):
        """Test _ensure_dom_tracker when no page exists."""
        adapter = TestablePlaywrightAdapter()
        adapter.page = None
        
        # Should not raise exception
        await adapter._ensure_dom_tracker()
    
    async def test_is_dom_stable_not_initialized(self):
        """Test is_dom_stable when adapter not initialized."""
        adapter = TestablePlaywrightAdapter()
        
        result = await adapter.is_dom_stable()
        assert result is False
    
    async def test_is_dom_stable_no_page(self):
        """Test is_dom_stable when no page exists."""
        adapter = TestablePlaywrightAdapter()
        adapter.initialized = True
        adapter.page = None
        
        result = await adapter.is_dom_stable()
        assert result is False
    
    async def test_is_dom_stable_success(self, adapter_with_mock_page):
        """Test is_dom_stable with stable DOM."""
        adapter = adapter_with_mock_page
        
        # Mock DOM stability check results
        adapter.page.evaluate.return_value = {
            "readyStateComplete": True,
            "pendingFetches": 0,
            "pendingXhrs": 0,
            "timeSinceMutation": 600.0
        }
        
        result = await adapter.is_dom_stable()
        assert result is True
    
    async def test_is_dom_stable_not_ready(self, adapter_with_mock_page):
        """Test is_dom_stable with DOM not ready."""
        adapter = adapter_with_mock_page
        
        adapter.page.evaluate.return_value = {
            "readyStateComplete": False,
            "pendingFetches": 0,
            "pendingXhrs": 0,
            "timeSinceMutation": 600.0
        }
        
        result = await adapter.is_dom_stable()
        assert result is False
    
    async def test_is_dom_stable_pending_requests(self, adapter_with_mock_page):
        """Test is_dom_stable with pending requests."""
        adapter = adapter_with_mock_page
        
        adapter.page.evaluate.return_value = {
            "readyStateComplete": True,
            "pendingFetches": 2,
            "pendingXhrs": 1,
            "timeSinceMutation": 600.0
        }
        
        result = await adapter.is_dom_stable()
        assert result is False
    
    async def test_is_dom_stable_recent_mutations(self, adapter_with_mock_page):
        """Test is_dom_stable with recent mutations."""
        adapter = adapter_with_mock_page
        
        adapter.page.evaluate.return_value = {
            "readyStateComplete": True,
            "pendingFetches": 0,
            "pendingXhrs": 0,
            "timeSinceMutation": 300.0  # Less than threshold
        }
        
        result = await adapter.is_dom_stable()
        assert result is False
    
    async def test_is_dom_stable_evaluation_error(self, adapter_with_mock_page):
        """Test is_dom_stable handles evaluation errors."""
        adapter = adapter_with_mock_page
        adapter.page.evaluate.side_effect = Exception("Script error")
        
        # Should return False on error to avoid false permanent errors
        result = await adapter.is_dom_stable()
        assert result is False
    
    async def test_raise_dom_classified_error_stable(self, adapter_with_mock_page):
        """Test _raise_dom_classified_error with stable DOM."""
        adapter = adapter_with_mock_page
        adapter.page.evaluate.return_value = {
            "readyStateComplete": True,
            "pendingFetches": 0,
            "pendingXhrs": 0,
            "timeSinceMutation": 600.0
        }
        
        original_error = Exception("Original error")
        
        with pytest.raises(ExternalOperationPermanentError, match="Test message \\(DOM stable\\)"):
            await adapter._raise_dom_classified_error("Test message", original_error)
    
    async def test_raise_dom_classified_error_unstable(self, adapter_with_mock_page):
        """Test _raise_dom_classified_error with unstable DOM."""
        adapter = adapter_with_mock_page
        adapter.page.evaluate.return_value = {
            "readyStateComplete": True,
            "pendingFetches": 1,
            "pendingXhrs": 0,
            "timeSinceMutation": 600.0
        }
        
        original_error = Exception("Original error")
        
        with pytest.raises(ExternalOperationTransientError, match="Test message \\(DOM still changing\\)"):
            await adapter._raise_dom_classified_error("Test message", original_error)


@pytest.mark.asyncio 
class TestPlaywrightAdapterLifecycle:
    """Test PlaywrightAdapter lifecycle management."""
    
    @patch('lamia.adapters.web.browser.playwright_adapter.PLAYWRIGHT_AVAILABLE', True)
    @patch('lamia.adapters.web.browser.playwright_adapter.async_playwright')
    async def test_initialize_standard_browser(self, mock_async_playwright):
        """Test initialization with standard browser setup."""
        # Mock Playwright objects
        mock_playwright_instance = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        
        mock_async_playwright.return_value.start = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        
        adapter = TestablePlaywrightAdapter(headless=False)
        await adapter.initialize()
        
        assert adapter.initialized
        assert adapter.playwright is mock_playwright_instance
        assert adapter.browser is mock_browser
        assert adapter.context is mock_context
        assert adapter.page is mock_page
        
        # Verify launch options
        mock_playwright_instance.chromium.launch.assert_called_once_with(
            headless=False,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
    
    @patch('lamia.adapters.web.browser.playwright_adapter.PLAYWRIGHT_AVAILABLE', False)
    async def test_initialize_playwright_not_available(self):
        """Test initialization when Playwright not available."""
        adapter = TestablePlaywrightAdapter()
        
        with pytest.raises(ImportError, match="Playwright not installed"):
            await adapter.initialize()
    
    @patch('lamia.adapters.web.browser.playwright_adapter.PLAYWRIGHT_AVAILABLE', True)
    @patch('lamia.adapters.web.browser.playwright_adapter.async_playwright')
    async def test_initialize_with_persistent_context(self, mock_async_playwright):
        """Test initialization with persistent context for session management."""
        mock_playwright_instance = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        mock_context.pages = [mock_page]
        
        mock_async_playwright.return_value.start = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright_instance.chromium.launch_persistent_context = AsyncMock(return_value=mock_context)
        
        # Mock session manager
        mock_session_manager = Mock()
        mock_session_manager.enabled = True
        mock_session_manager.get_profile_session_dir.return_value = "/tmp/profile"
        
        adapter = TestablePlaywrightAdapter(session_config={"enabled": True})
        adapter.session_manager = mock_session_manager
        adapter.use_persistent_context = True
        
        await adapter.initialize()
        
        assert adapter.initialized
        assert adapter.context is mock_context
        assert adapter.page is mock_page
        assert adapter.browser is None  # Not used in persistent mode
        
        # Verify persistent context call
        mock_playwright_instance.chromium.launch_persistent_context.assert_called_once()
        call_args = mock_playwright_instance.chromium.launch_persistent_context.call_args
        assert call_args[1]['user_data_dir'] == "/tmp/profile"
    
    @patch('lamia.adapters.web.browser.playwright_adapter.PLAYWRIGHT_AVAILABLE', True)
    @patch('lamia.adapters.web.browser.playwright_adapter.async_playwright')
    async def test_initialize_error_handling(self, mock_async_playwright):
        """Test initialization error handling."""
        mock_async_playwright.return_value.start.side_effect = Exception("Playwright error")
        
        adapter = TestablePlaywrightAdapter()
        
        with pytest.raises(Exception, match="Playwright error"):
            await adapter.initialize()
    
    async def test_close_cleanup(self):
        """Test close method cleanup."""
        adapter = TestablePlaywrightAdapter()
        
        # Mock browser objects
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_browser = AsyncMock()
        mock_playwright = AsyncMock()
        
        adapter.page = mock_page
        adapter.context = mock_context
        adapter.browser = mock_browser
        adapter.playwright = mock_playwright
        adapter.initialized = True
        
        # Mock session manager if it exists
        if hasattr(adapter, 'session_manager') and adapter.session_manager:
            adapter.session_manager = Mock()
            adapter.session_manager.enabled = False
        
        await adapter.close()
        
        # Verify cleanup calls
        mock_page.close.assert_called_once()
        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()
        
        # Verify state reset
        assert adapter.page is None
        assert adapter.context is None
        assert adapter.browser is None
        assert adapter.playwright is None
        assert not adapter.initialized
    
    async def test_close_handles_errors(self):
        """Test close method handles cleanup errors gracefully."""
        adapter = TestablePlaywrightAdapter()
        
        # Mock browser objects with errors
        adapter.page = AsyncMock()
        adapter.context = AsyncMock()
        adapter.browser = AsyncMock()
        adapter.playwright = AsyncMock()
        adapter.initialized = True
        
        adapter.page.close.side_effect = Exception("Page close error")
        adapter.context.close.side_effect = Exception("Context close error")
        
        # Should not raise exception
        await adapter.close()
        
        # State should still be reset
        assert adapter.page is None
        assert adapter.context is None
        assert adapter.browser is None
        assert adapter.playwright is None
        assert not adapter.initialized


@pytest.mark.asyncio
class TestPlaywrightAdapterElementFinding:
    """Test PlaywrightAdapter element finding and fallback logic."""
    
    @pytest.fixture
    def adapter_with_page(self):
        """Create adapter with mocked page."""
        adapter = TestablePlaywrightAdapter()
        adapter.initialized = True
        adapter.page = AsyncMock()
        return adapter
    
    async def test_find_element_with_fallbacks_success_first(self, adapter_with_page):
        """Test finding element with first selector."""
        adapter = adapter_with_page
        mock_element = AsyncMock()
        
        adapter.page.wait_for_selector.return_value = mock_element
        
        params = BrowserActionParams(
            selector="#button",
            fallback_selectors=[".btn", "button"],
            timeout=5.0
        )
        
        result = await adapter._find_element_with_fallbacks(params)
        
        assert result is mock_element
        adapter.page.wait_for_selector.assert_called_once_with(
            "#button", 
            timeout=5000.0
        )
    
    async def test_find_element_with_fallbacks_uses_fallback(self, adapter_with_page):
        """Test finding element uses fallback selector."""
        adapter = adapter_with_page
        mock_element = AsyncMock()
        
        # First selector fails, second succeeds
        adapter.page.wait_for_selector.side_effect = [
            Exception("First failed"),
            mock_element
        ]
        
        params = BrowserActionParams(
            selector="#button",
            fallback_selectors=[".btn", "button"]
        )
        
        result = await adapter._find_element_with_fallbacks(params)
        
        assert result is mock_element
        assert adapter.page.wait_for_selector.call_count == 2
    
    async def test_find_element_with_fallbacks_all_fail(self, adapter_with_page):
        """Test finding element when all selectors fail."""
        adapter = adapter_with_page
        
        adapter.page.wait_for_selector.side_effect = Exception("All failed")
        
        params = BrowserActionParams(
            selector="#button",
            fallback_selectors=[".btn", "button"]
        )
        
        with pytest.raises(Exception, match="Could not find element"):
            await adapter._find_element_with_fallbacks(params)
    
    async def test_find_element_with_scoped_search(self, adapter_with_page):
        """Test finding element with scoped search root."""
        adapter = adapter_with_page
        mock_scope_element = AsyncMock()
        mock_found_element = AsyncMock()
        
        mock_scope_element.wait_for_selector.return_value = mock_found_element
        
        params = BrowserActionParams(
            selector=".item",
            scope_element_handle=mock_scope_element
        )
        
        result = await adapter._find_element_with_fallbacks(params)
        
        assert result is mock_found_element
        mock_scope_element.wait_for_selector.assert_called_once()
        adapter.page.wait_for_selector.assert_not_called()


@pytest.mark.asyncio
class TestPlaywrightAdapterBasicActions:
    """Test PlaywrightAdapter basic browser actions."""
    
    @pytest.fixture
    def adapter_with_page(self):
        """Create adapter with mocked page."""
        adapter = TestablePlaywrightAdapter()
        adapter.initialized = True
        adapter.page = AsyncMock()
        return adapter
    
    async def test_navigate_success(self, adapter_with_page):
        """Test successful navigation."""
        adapter = adapter_with_page
        
        params = BrowserActionParams(value="https://example.com")
        
        await adapter.navigate(params)
        
        adapter.page.goto.assert_called_once_with("https://example.com")
    
    async def test_navigate_not_initialized(self):
        """Test navigate when adapter not initialized."""
        adapter = TestablePlaywrightAdapter()
        params = BrowserActionParams(value="https://example.com")
        
        with pytest.raises(RuntimeError, match="PlaywrightAdapter not initialized"):
            await adapter.navigate(params)
    
    async def test_click_success(self, adapter_with_page):
        """Test successful click action."""
        adapter = adapter_with_page
        
        params = BrowserActionParams(
            selector="#button",
            selector_type=SelectorType.CSS,
            timeout=5.0
        )
        
        await adapter.click(params)
        
        adapter.page.click.assert_called_once_with("#button", timeout=5000.0)
    
    async def test_click_timeout_error_stable_dom(self, adapter_with_page):
        """Test click timeout error with stable DOM."""
        adapter = adapter_with_page
        
        from lamia.adapters.web.browser.playwright_adapter import PlaywrightTimeoutError
        adapter.page.click.side_effect = PlaywrightTimeoutError("Timeout")
        
        # Mock stable DOM
        adapter.page.evaluate.return_value = {
            "readyStateComplete": True,
            "pendingFetches": 0,
            "pendingXhrs": 0,
            "timeSinceMutation": 600.0
        }
        
        params = BrowserActionParams(selector="#button")
        
        with pytest.raises(ExternalOperationPermanentError, match="DOM stable"):
            await adapter.click(params)
    
    async def test_type_text_success(self, adapter_with_page):
        """Test successful text typing."""
        adapter = adapter_with_page
        
        params = BrowserActionParams(
            selector="#input",
            value="test text"
        )
        
        await adapter.type_text(params)
        
        adapter.page.fill.assert_called_once_with("#input", "test text", timeout=10000.0)
    
    async def test_type_text_no_selector(self, adapter_with_page):
        """Test type_text without selector."""
        adapter = adapter_with_page
        
        params = BrowserActionParams(value="test text")
        
        with pytest.raises(ExternalOperationPermanentError, match="Selector is required"):
            await adapter.type_text(params)
    
    async def test_upload_file_success(self, adapter_with_page):
        """Test successful file upload."""
        adapter = adapter_with_page
        
        params = BrowserActionParams(
            selector="input[type='file']",
            value="/path/to/file.txt"
        )
        
        await adapter.upload_file(params)
        
        adapter.page.set_input_files.assert_called_once_with(
            "input[type='file']", 
            "/path/to/file.txt", 
            timeout=10000.0
        )
    
    async def test_upload_file_no_path(self, adapter_with_page):
        """Test upload_file without file path."""
        adapter = adapter_with_page
        
        params = BrowserActionParams(selector="input[type='file']")
        
        with pytest.raises(ValueError, match="File path is required"):
            await adapter.upload_file(params)


@pytest.mark.asyncio
class TestPlaywrightAdapterElementQueries:
    """Test PlaywrightAdapter element query methods."""
    
    @pytest.fixture
    def adapter_with_page(self):
        """Create adapter with mocked page."""
        adapter = TestablePlaywrightAdapter()
        adapter.initialized = True
        adapter.page = AsyncMock()
        return adapter
    
    async def test_get_text_success(self, adapter_with_page):
        """Test successful text retrieval."""
        adapter = adapter_with_page
        mock_element = AsyncMock()
        mock_element.text_content.return_value = "Button text"
        
        adapter.page.wait_for_selector.return_value = mock_element
        
        params = BrowserActionParams(selector="#button")
        result = await adapter.get_text(params)
        
        assert result == "Button text"
        adapter.page.wait_for_selector.assert_called_once_with("#button", timeout=10000.0)
        mock_element.text_content.assert_called_once()
    
    async def test_get_text_empty_content(self, adapter_with_page):
        """Test get_text with empty content."""
        adapter = adapter_with_page
        mock_element = AsyncMock()
        mock_element.text_content.return_value = None
        
        adapter.page.wait_for_selector.return_value = mock_element
        
        params = BrowserActionParams(selector="#button")
        result = await adapter.get_text(params)
        
        assert result == ""
    
    async def test_get_attribute_success(self, adapter_with_page):
        """Test successful attribute retrieval."""
        adapter = adapter_with_page
        mock_element = AsyncMock()
        mock_element.get_attribute.return_value = "button"
        
        adapter.page.wait_for_selector.return_value = mock_element
        
        params = BrowserActionParams(
            selector="#button",
            value="type"
        )
        result = await adapter.get_attribute(params)
        
        assert result == "button"
        mock_element.get_attribute.assert_called_once_with("type")
    
    async def test_get_attribute_not_found(self, adapter_with_page):
        """Test get_attribute when attribute not found."""
        adapter = adapter_with_page
        mock_element = AsyncMock()
        mock_element.get_attribute.return_value = None
        
        adapter.page.wait_for_selector.return_value = mock_element
        
        params = BrowserActionParams(
            selector="#button",
            value="nonexistent"
        )
        result = await adapter.get_attribute(params)
        
        assert result == ""
    
    async def test_is_visible_true(self, adapter_with_page):
        """Test is_visible returning true."""
        adapter = adapter_with_page
        mock_element = AsyncMock()
        mock_element.is_visible.return_value = True
        
        adapter.page.query_selector.return_value = mock_element
        
        params = BrowserActionParams(selector="#button")
        result = await adapter.is_visible(params)
        
        assert result is True
        mock_element.is_visible.assert_called_once()
    
    async def test_is_visible_element_not_found(self, adapter_with_page):
        """Test is_visible when element not found."""
        adapter = adapter_with_page
        adapter.page.query_selector.return_value = None
        
        # Mock stable DOM for permanent error
        adapter.page.evaluate.return_value = {
            "readyStateComplete": True,
            "pendingFetches": 0,
            "pendingXhrs": 0,
            "timeSinceMutation": 600.0
        }
        
        params = BrowserActionParams(selector="#button")
        
        with pytest.raises(ExternalOperationPermanentError):
            await adapter.is_visible(params)
    
    async def test_is_enabled_true(self, adapter_with_page):
        """Test is_enabled returning true."""
        adapter = adapter_with_page
        mock_element = AsyncMock()
        mock_element.is_enabled.return_value = True
        
        adapter.page.query_selector.return_value = mock_element
        
        params = BrowserActionParams(selector="#button")
        result = await adapter.is_enabled(params)
        
        assert result is True
        mock_element.is_enabled.assert_called_once()


@pytest.mark.asyncio
class TestPlaywrightAdapterAdvancedActions:
    """Test PlaywrightAdapter advanced actions and interactions."""
    
    @pytest.fixture
    def adapter_with_page(self):
        """Create adapter with mocked page."""
        adapter = TestablePlaywrightAdapter()
        adapter.initialized = True
        adapter.page = AsyncMock()
        return adapter
    
    async def test_wait_for_element_visible(self, adapter_with_page):
        """Test waiting for element to be visible."""
        adapter = adapter_with_page
        
        params = BrowserActionParams(
            selector="#button",
            wait_condition="visible",
            timeout=5.0
        )
        
        await adapter.wait_for_element(params)
        
        adapter.page.wait_for_selector.assert_called_once_with(
            "#button", 
            state="visible", 
            timeout=5000.0
        )
    
    async def test_wait_for_element_hidden(self, adapter_with_page):
        """Test waiting for element to be hidden."""
        adapter = adapter_with_page
        
        params = BrowserActionParams(
            selector="#button",
            wait_condition="hidden"
        )
        
        await adapter.wait_for_element(params)
        
        adapter.page.wait_for_selector.assert_called_once_with(
            "#button", 
            state="hidden", 
            timeout=10000.0
        )
    
    async def test_wait_for_element_clickable(self, adapter_with_page):
        """Test waiting for element to be clickable."""
        adapter = adapter_with_page
        mock_element = AsyncMock()
        
        adapter.page.wait_for_selector.return_value = mock_element
        
        params = BrowserActionParams(
            selector="#button",
            wait_condition="clickable"
        )
        
        await adapter.wait_for_element(params)
        
        adapter.page.wait_for_selector.assert_called_once()
        mock_element.wait_for_element_state.assert_called_once_with("stable")
    
    async def test_hover_success(self, adapter_with_page):
        """Test successful hover action."""
        adapter = adapter_with_page
        
        params = BrowserActionParams(selector="#menu-item")
        
        await adapter.hover(params)
        
        adapter.page.hover.assert_called_once_with("#menu-item", timeout=10000.0)
    
    async def test_scroll_success(self, adapter_with_page):
        """Test successful scroll action."""
        adapter = adapter_with_page
        mock_element = AsyncMock()
        
        adapter.page.wait_for_selector.return_value = mock_element
        
        params = BrowserActionParams(selector="#bottom-content")
        
        await adapter.scroll(params)
        
        adapter.page.wait_for_selector.assert_called_once()
        mock_element.scroll_into_view_if_needed.assert_called_once()
    
    async def test_select_option_success(self, adapter_with_page):
        """Test successful option selection."""
        adapter = adapter_with_page
        
        params = BrowserActionParams(
            selector="#country",
            value="USA"
        )
        
        await adapter.select_option(params)
        
        adapter.page.select_option.assert_called_once_with(
            "#country", 
            value="USA", 
            timeout=10000.0
        )
    
    async def test_submit_form_success(self, adapter_with_page):
        """Test successful form submission."""
        adapter = adapter_with_page
        mock_form = AsyncMock()
        
        adapter.page.query_selector.return_value = mock_form
        
        params = BrowserActionParams(selector="#contact-form")
        
        await adapter.submit_form(params)
        
        adapter.page.query_selector.assert_called_once_with("#contact-form")
        mock_form.evaluate.assert_called_once_with("form => form.submit()")
    
    async def test_submit_form_not_found(self, adapter_with_page):
        """Test form submission when form not found."""
        adapter = adapter_with_page
        adapter.page.query_selector.return_value = None
        
        # Mock stable DOM for permanent error
        adapter.page.evaluate.return_value = {
            "readyStateComplete": True,
            "pendingFetches": 0,
            "pendingXhrs": 0,
            "timeSinceMutation": 600.0
        }
        
        params = BrowserActionParams(selector="#contact-form")
        
        with pytest.raises(ExternalOperationPermanentError, match="Form .* not found"):
            await adapter.submit_form(params)
    
    async def test_take_screenshot_with_path(self, adapter_with_page):
        """Test taking screenshot with specified path."""
        adapter = adapter_with_page
        
        params = BrowserActionParams(value="test-screenshot.png")
        
        result = await adapter.take_screenshot(params)
        
        assert result == "test-screenshot.png"
        adapter.page.screenshot.assert_called_once_with(path="test-screenshot.png")
    
    async def test_take_screenshot_auto_name(self, adapter_with_page):
        """Test taking screenshot with auto-generated name."""
        adapter = adapter_with_page
        
        params = BrowserActionParams()
        
        with patch('time.time', return_value=1234567890):
            result = await adapter.take_screenshot(params)
        
        assert result == "screenshot_1234567890.png"
        adapter.page.screenshot.assert_called_once_with(path="screenshot_1234567890.png")


@pytest.mark.asyncio
class TestPlaywrightAdapterPageUtilities:
    """Test PlaywrightAdapter page utility methods."""
    
    @pytest.fixture
    def adapter_with_page(self):
        """Create adapter with mocked page."""
        adapter = TestablePlaywrightAdapter()
        adapter.initialized = True
        adapter.page = AsyncMock()
        return adapter
    
    async def test_get_page_source_success(self, adapter_with_page):
        """Test successful page source retrieval."""
        adapter = adapter_with_page
        adapter.page.content.return_value = "<html><body>Content</body></html>"
        
        result = await adapter.get_page_source()
        
        assert result == "<html><body>Content</body></html>"
        adapter.page.content.assert_called_once()
    
    async def test_get_page_source_no_page(self):
        """Test page source retrieval without page."""
        adapter = TestablePlaywrightAdapter()
        adapter.initialized = True
        adapter.page = None
        
        result = await adapter.get_page_source()
        
        assert result == ""
    
    async def test_get_page_source_not_initialized(self):
        """Test page source retrieval when not initialized."""
        adapter = TestablePlaywrightAdapter()
        
        with pytest.raises(RuntimeError, match="PlaywrightAdapter not initialized"):
            await adapter.get_page_source()
    
    async def test_get_current_url_success(self, adapter_with_page):
        """Test successful current URL retrieval."""
        adapter = adapter_with_page
        adapter.page.url = "https://example.com/page"
        
        result = await adapter.get_current_url()
        
        assert result == "https://example.com/page"
    
    async def test_get_current_url_no_page(self):
        """Test current URL retrieval without page."""
        adapter = TestablePlaywrightAdapter()
        adapter.initialized = True
        adapter.page = None
        
        result = await adapter.get_current_url()
        
        assert result is None
    
    async def test_get_current_url_not_initialized(self):
        """Test current URL retrieval when not initialized."""
        adapter = TestablePlaywrightAdapter()
        
        with pytest.raises(RuntimeError, match="PlaywrightAdapter not initialized"):
            await adapter.get_current_url()


@pytest.mark.asyncio
class TestPlaywrightAdapterWaitForStability:
    """Test PlaywrightAdapter DOM stability waiting logic."""
    
    @pytest.fixture
    def adapter_with_page(self):
        """Create adapter with mocked page."""
        adapter = TestablePlaywrightAdapter()
        adapter.initialized = True
        adapter.page = AsyncMock()
        return adapter
    
    async def test_wait_for_dom_stability_quick_stable(self, adapter_with_page):
        """Test DOM stability wait when DOM is quickly stable."""
        adapter = adapter_with_page
        
        # Mock stable DOM immediately
        adapter.page.evaluate.return_value = {
            "readyStateComplete": True,
            "pendingFetches": 0,
            "pendingXhrs": 0,
            "timeSinceMutation": 600.0
        }
        
        start_time = time.time()
        await adapter._wait_for_dom_stability(timeout=2.0)
        elapsed = time.time() - start_time
        
        # Should return quickly (within 1 second for stable checks)
        assert elapsed < 1.0
    
    async def test_wait_for_dom_stability_timeout(self, adapter_with_page):
        """Test DOM stability wait timeout."""
        adapter = adapter_with_page
        
        # Mock never-stable DOM
        adapter.page.evaluate.return_value = {
            "readyStateComplete": True,
            "pendingFetches": 1,  # Always pending
            "pendingXhrs": 0,
            "timeSinceMutation": 600.0
        }
        
        start_time = time.time()
        await adapter._wait_for_dom_stability(timeout=0.5)
        elapsed = time.time() - start_time
        
        # Should timeout after specified time
        assert 0.4 < elapsed < 0.7
    
    async def test_wait_for_dom_stability_exception_fallback(self, adapter_with_page):
        """Test DOM stability wait with exception fallback."""
        adapter = adapter_with_page
        adapter.page.evaluate.side_effect = Exception("Evaluation error")
        
        start_time = time.time()
        await adapter._wait_for_dom_stability(timeout=1.0)
        elapsed = time.time() - start_time
        
        # Should fallback to short sleep (0.5 seconds) - allow for test timing variance
        assert 0.4 < elapsed < 1.2


class TestPlaywrightAdapterSessionManagement:
    """Test PlaywrightAdapter session management functionality."""
    
    def test_set_profile_updates_name(self):
        """Test set_profile updates profile name."""
        adapter = TestablePlaywrightAdapter()
        
        adapter.set_profile("custom-profile")
        assert adapter.profile_name == "custom-profile"
    
    def test_set_profile_none_resets_to_default(self):
        """Test set_profile with None resets to default."""
        adapter = TestablePlaywrightAdapter()
        adapter.profile_name = "custom"
        
        adapter.set_profile(None)
        assert adapter.profile_name is None
    
    @pytest.mark.asyncio
    async def test_load_session_state_no_manager(self):
        """Test load_session_state without session manager."""
        adapter = TestablePlaywrightAdapter()
        
        # Should not raise error
        await adapter.load_session_state()
    
    @pytest.mark.asyncio
    async def test_save_session_state_no_manager(self):
        """Test save_session_state without session manager."""
        adapter = TestablePlaywrightAdapter()
        
        # Should not raise error
        await adapter.save_session_state()


class TestPlaywrightAdapterIntegration:
    """Test PlaywrightAdapter integration scenarios."""
    
    def test_adapter_inheritance(self):
        """Test PlaywrightAdapter inheritance from BaseBrowserAdapter."""
        adapter = TestablePlaywrightAdapter()
        assert isinstance(adapter, BaseBrowserAdapter)
    
    def test_default_configuration(self):
        """Test default configuration values."""
        adapter = TestablePlaywrightAdapter()
        
        assert adapter.headless is True
        assert adapter.default_timeout == 10000.0
        assert adapter.profile_name == "default"
        assert not adapter.use_persistent_context
    
    def test_session_configuration_enables_persistence(self):
        """Test that session configuration enables persistent context."""
        session_config = {"enabled": True}
        
        with patch('lamia.adapters.web.browser.playwright_adapter.SessionManager') as mock_session_manager:
            mock_instance = Mock()
            mock_instance.enabled = True
            mock_session_manager.return_value = mock_instance
            
            adapter = TestablePlaywrightAdapter(session_config=session_config)
            
            assert adapter.session_manager is not None
            assert adapter.use_persistent_context is True
    
    @pytest.mark.asyncio
    async def test_error_classification_dom_aware(self):
        """Test that error classification is DOM stability aware."""
        adapter = TestablePlaywrightAdapter()
        adapter.initialized = True
        adapter.page = AsyncMock()
        
        # Mock unstable DOM
        adapter.page.evaluate.return_value = {
            "readyStateComplete": True,
            "pendingFetches": 1,
            "pendingXhrs": 0,
            "timeSinceMutation": 600.0
        }
        
        original_error = Exception("Test error")
        
        with pytest.raises(ExternalOperationTransientError, match="DOM still changing"):
            await adapter._raise_dom_classified_error("Test", original_error)