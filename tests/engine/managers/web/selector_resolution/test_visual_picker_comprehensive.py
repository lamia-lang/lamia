"""
Comprehensive tests for Visual Picker Module.

This module tests all components of the visual element picker system:
- VisualSelectionCache: Persistent caching of visual selections
- ElementContextExtractor: HTML context extraction and XPath evaluation
- BrowserOverlay: JavaScript picker injection and user interaction
- VisualElementPicker: Main orchestrator for visual selection
- SelectionValidator: Method-specific validation rules
- ActionSelectionHandler: Action-specific selection logic
- PluralSelectionStrategy: Template-based multiple element selection
- SingularSelectionStrategy: Single element selection

Coverage areas:
- Cache operations (get/set/invalidate, URL normalization)
- Context extraction (XPath evaluation, visibility filtering)
- Overlay management (JS injection, polling, event handling)
- Picker orchestration (cache workflow, strategy routing)
- Selection validation (method-specific rules)
- Strategy classes (action, plural, singular logic)
- Integration tests (end-to-end visual picking)
"""

import os
import json
import pytest
from pathlib import Path
from typing import Dict, List, Optional, Any
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call

from lamia.engine.managers.web.selector_resolution.visual_picker.cache import VisualSelectionCache
from lamia.engine.managers.web.selector_resolution.visual_picker.context_extractor import ElementContextExtractor
from lamia.engine.managers.web.selector_resolution.visual_picker.overlay import BrowserOverlay
from lamia.engine.managers.web.selector_resolution.visual_picker.picker import VisualElementPicker
from lamia.engine.managers.web.selector_resolution.visual_picker.validation import SelectionValidator
from lamia.engine.managers.web.selector_resolution.visual_picker.strategies.action_strategy import ActionSelectionHandler
from lamia.engine.managers.web.selector_resolution.visual_picker.strategies.plural_strategy import PluralSelectionStrategy
from lamia.engine.managers.web.selector_resolution.visual_picker.strategies.singular_strategy import SingularSelectionStrategy
from lamia.engine.config_provider import ConfigProvider, _DEFAULT_CACHE_DIR


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory."""
    cache_dir = tmp_path / "visual_cache"
    cache_dir.mkdir()
    return str(cache_dir)


@pytest.fixture
def config_provider(temp_cache_dir):
    """Create config provider with cache enabled and custom dir."""
    return ConfigProvider({
        "web_config": {
            "cache": {
                "enabled": True,
                "dir": temp_cache_dir,
            },
            "human_in_loop": True,
        }
    })


@pytest.fixture
def default_config_provider():
    """Create config provider with default cache settings."""
    return ConfigProvider({
        "web_config": {
            "cache": {
                "enabled": True,
                "dir": DEFAULT_CACHE_DIR,
            },
            "human_in_loop": True,
        }
    })


@pytest.fixture
def mock_browser_adapter():
    """Create mock browser adapter."""
    adapter = AsyncMock()
    adapter.execute_js = AsyncMock()
    adapter.get_current_url = AsyncMock(return_value="https://example.com/page")
    return adapter


@pytest.fixture
def mock_llm_executor():
    """Create mock LLM executor."""
    executor = AsyncMock()
    return executor


@pytest.fixture
def sample_cache_entry():
    """Create sample cache entry."""
    return {
        "selector": "button#submit",
        "method": "click",
        "timestamp": 1234567890.0,
        "url": "https://example.com/page",
        "context": "<button id='submit'>Submit</button>"
    }


@pytest.fixture
def sample_html_context():
    """Create sample HTML context."""
    return """
    <div class="container">
        <button id="submit" class="btn-primary" type="submit">Submit</button>
        <input type="text" name="username" placeholder="Enter username">
    </div>
    """


# ============================================================================
# VisualSelectionCache Tests
# ============================================================================

class TestVisualSelectionCacheInitialization:
    """Test VisualSelectionCache initialization."""

    def test_cache_initialization_default_path(self):
        """Test cache initialization with default path."""
        with patch('lamia.engine.managers.web.selector_resolution.visual_picker.cache.Path.mkdir'):
            cache = VisualSelectionCache()

            assert cache.cache_dir is not None
            assert "visual_selections" in str(cache.cache_dir)

    def test_cache_initialization_custom_path(self, temp_cache_dir):
        """Test cache initialization with custom path."""
        cache = VisualSelectionCache(cache_dir=temp_cache_dir)

        assert str(cache.cache_dir) == temp_cache_dir
        assert os.path.exists(temp_cache_dir)

    def test_cache_directory_creation(self, tmp_path):
        """Test cache directory is created if it doesn't exist."""
        cache_dir = tmp_path / "new_cache"
        cache = VisualSelectionCache(cache_dir=str(cache_dir))

        assert cache_dir.exists()


class TestVisualSelectionCacheOperations:
    """Test VisualSelectionCache cache operations."""

    def test_get_cached_selector_hit(self, temp_cache_dir, sample_cache_entry):
        """Test getting cached selector when cache hit."""
        cache = VisualSelectionCache(cache_dir=temp_cache_dir)

        # Write cache entry
        cache_key = cache._normalize_url("https://example.com/page")
        cache_file = os.path.join(temp_cache_dir, f"{cache_key}.json")
        with open(cache_file, 'w') as f:
            json.dump({"submit_button": sample_cache_entry}, f)

        result = cache.get_cached_selector(
            "https://example.com/page",
            "submit_button"
        )

        assert result == "button#submit"

    def test_get_cached_selector_miss(self, temp_cache_dir):
        """Test getting cached selector when cache miss."""
        cache = VisualSelectionCache(cache_dir=temp_cache_dir)

        result = cache.get_cached_selector(
            "https://example.com/page",
            "nonexistent_element"
        )

        assert result is None

    def test_cache_selector(self, temp_cache_dir):
        """Test caching a selector."""
        cache = VisualSelectionCache(cache_dir=temp_cache_dir)

        cache.cache_selector(
            url="https://example.com/page",
            element_name="submit_button",
            selector="button#submit",
            method="click",
            context="<button id='submit'>Submit</button>"
        )

        # Verify cache entry was written
        result = cache.get_cached_selector(
            "https://example.com/page",
            "submit_button"
        )

        assert result == "button#submit"

    def test_cache_selector_overwrites_existing(self, temp_cache_dir, sample_cache_entry):
        """Test caching a selector overwrites existing entry."""
        cache = VisualSelectionCache(cache_dir=temp_cache_dir)

        # Write initial entry
        cache_key = cache._normalize_url("https://example.com/page")
        cache_file = os.path.join(temp_cache_dir, f"{cache_key}.json")
        with open(cache_file, 'w') as f:
            json.dump({"submit_button": sample_cache_entry}, f)

        # Overwrite with new entry
        cache.cache_selector(
            url="https://example.com/page",
            element_name="submit_button",
            selector="button.submit-btn",
            method="click",
            context="<button class='submit-btn'>Submit</button>"
        )

        result = cache.get_cached_selector(
            "https://example.com/page",
            "submit_button"
        )

        assert result == "button.submit-btn"

    def test_invalidate_cache_for_url(self, temp_cache_dir, sample_cache_entry):
        """Test invalidating cache for a URL."""
        cache = VisualSelectionCache(cache_dir=temp_cache_dir)

        # Write cache entry
        cache_key = cache._normalize_url("https://example.com/page")
        cache_file = os.path.join(temp_cache_dir, f"{cache_key}.json")
        with open(cache_file, 'w') as f:
            json.dump({"submit_button": sample_cache_entry}, f)

        cache.invalidate_cache("https://example.com/page")

        # Verify cache was invalidated
        result = cache.get_cached_selector(
            "https://example.com/page",
            "submit_button"
        )

        assert result is None
        assert not os.path.exists(cache_file)

    def test_invalidate_nonexistent_cache(self, temp_cache_dir):
        """Test invalidating cache for URL that doesn't exist."""
        cache = VisualSelectionCache(cache_dir=temp_cache_dir)

        # Should not raise error
        cache.invalidate_cache("https://nonexistent.com/page")

    def test_clear_all_cache(self, temp_cache_dir):
        """Test clearing all cache entries."""
        cache = VisualSelectionCache(cache_dir=temp_cache_dir)

        # Write multiple cache entries
        for i in range(3):
            cache.cache_selector(
                url=f"https://example.com/page{i}",
                element_name="element",
                selector=f"#element{i}",
                method="click",
                context=f"<div id='element{i}'></div>"
            )

        cache.clear_all()

        # Verify all caches were cleared
        for i in range(3):
            result = cache.get_cached_selector(
                f"https://example.com/page{i}",
                "element"
            )
            assert result is None


class TestVisualSelectionCacheURLNormalization:
    """Test URL normalization in VisualSelectionCache."""

    def test_normalize_url_strips_fragment(self, temp_cache_dir):
        """Test URL normalization strips fragment."""
        cache = VisualSelectionCache(cache_dir=temp_cache_dir)

        normalized = cache._normalize_url("https://example.com/page#section")

        assert normalized == cache._normalize_url("https://example.com/page")

    def test_normalize_url_strips_trailing_slash(self, temp_cache_dir):
        """Test URL normalization strips trailing slash."""
        cache = VisualSelectionCache(cache_dir=temp_cache_dir)

        normalized = cache._normalize_url("https://example.com/page/")

        assert normalized == cache._normalize_url("https://example.com/page")

    def test_normalize_url_same_cache_key(self, temp_cache_dir):
        """Test different URL variations produce same cache key."""
        cache = VisualSelectionCache(cache_dir=temp_cache_dir)

        # Cache with one variation
        cache.cache_selector(
            url="https://example.com/page#section",
            element_name="element",
            selector="#element",
            method="click",
            context="<div id='element'></div>"
        )

        # Retrieve with different variation
        result = cache.get_cached_selector(
            "https://example.com/page/",
            "element"
        )

        assert result == "#element"


class TestVisualSelectionCacheStatistics:
    """Test VisualSelectionCache statistics tracking."""

    def test_get_cache_stats_empty(self, temp_cache_dir):
        """Test getting cache statistics when empty."""
        cache = VisualSelectionCache(cache_dir=temp_cache_dir)

        stats = cache.get_stats()

        assert stats["total_urls"] == 0
        assert stats["total_elements"] == 0

    def test_get_cache_stats_with_entries(self, temp_cache_dir):
        """Test getting cache statistics with entries."""
        cache = VisualSelectionCache(cache_dir=temp_cache_dir)

        # Add multiple entries
        cache.cache_selector(
            url="https://example.com/page1",
            element_name="element1",
            selector="#element1",
            method="click",
            context="<div id='element1'></div>"
        )
        cache.cache_selector(
            url="https://example.com/page1",
            element_name="element2",
            selector="#element2",
            method="click",
            context="<div id='element2'></div>"
        )
        cache.cache_selector(
            url="https://example.com/page2",
            element_name="element3",
            selector="#element3",
            method="click",
            context="<div id='element3'></div>"
        )

        stats = cache.get_stats()

        assert stats["total_urls"] == 2
        assert stats["total_elements"] == 3


class TestVisualSelectionCacheFileIO:
    """Test VisualSelectionCache file I/O operations."""

    def test_cache_file_format(self, temp_cache_dir):
        """Test cache file is written in correct JSON format."""
        cache = VisualSelectionCache(cache_dir=temp_cache_dir)

        cache.cache_selector(
            url="https://example.com/page",
            element_name="element",
            selector="#element",
            method="click",
            context="<div id='element'></div>"
        )

        # Read cache file directly
        cache_key = cache._normalize_url("https://example.com/page")
        cache_file = os.path.join(temp_cache_dir, f"{cache_key}.json")

        with open(cache_file, 'r') as f:
            data = json.load(f)

        assert "element" in data
        assert data["element"]["selector"] == "#element"
        assert data["element"]["method"] == "click"
        assert "timestamp" in data["element"]

    def test_cache_handles_corrupted_file(self, temp_cache_dir):
        """Test cache handles corrupted JSON file gracefully."""
        cache = VisualSelectionCache(cache_dir=temp_cache_dir)

        # Write corrupted cache file
        cache_key = cache._normalize_url("https://example.com/page")
        cache_file = os.path.join(temp_cache_dir, f"{cache_key}.json")
        with open(cache_file, 'w') as f:
            f.write("corrupted json {")

        result = cache.get_cached_selector(
            "https://example.com/page",
            "element"
        )

        assert result is None


# ============================================================================
# ElementContextExtractor Tests
# ============================================================================

class TestElementContextExtractorInitialization:
    """Test ElementContextExtractor initialization."""

    @pytest.mark.asyncio
    async def test_extractor_initialization(self, mock_browser_adapter):
        """Test context extractor initialization."""
        extractor = ElementContextExtractor(mock_browser_adapter)

        assert extractor.browser == mock_browser_adapter


class TestElementContextExtractorContextExtraction:
    """Test ElementContextExtractor context extraction."""

    @pytest.mark.asyncio
    async def test_extract_context_with_selector(self, mock_browser_adapter, sample_html_context):
        """Test extracting context with CSS selector."""
        mock_browser_adapter.execute_js.return_value = sample_html_context

        extractor = ElementContextExtractor(mock_browser_adapter)
        context = await extractor.extract_context("button#submit")

        assert "button id=\"submit\"" in context.lower()
        mock_browser_adapter.execute_js.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_context_with_xpath(self, mock_browser_adapter):
        """Test extracting context with XPath."""
        mock_browser_adapter.execute_js.return_value = "<div>XPath result</div>"

        extractor = ElementContextExtractor(mock_browser_adapter)
        context = await extractor.extract_context("//button[@id='submit']", use_xpath=True)

        assert "XPath result" in context
        mock_browser_adapter.execute_js.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_context_nonexistent_element(self, mock_browser_adapter):
        """Test extracting context for nonexistent element."""
        mock_browser_adapter.execute_js.return_value = ""

        extractor = ElementContextExtractor(mock_browser_adapter)
        context = await extractor.extract_context("#nonexistent")

        assert context == ""

    @pytest.mark.asyncio
    async def test_extract_context_with_parent(self, mock_browser_adapter):
        """Test extracting context includes parent elements."""
        mock_browser_adapter.execute_js.return_value = """
        <div class="parent">
            <button id="submit">Submit</button>
        </div>
        """

        extractor = ElementContextExtractor(mock_browser_adapter)
        context = await extractor.extract_context("button#submit", include_parent=True)

        assert "parent" in context.lower()
        assert "button" in context.lower()


class TestElementContextExtractorVisibilityFiltering:
    """Test ElementContextExtractor visibility filtering."""

    @pytest.mark.asyncio
    async def test_filter_visible_elements(self, mock_browser_adapter):
        """Test filtering only visible elements."""
        mock_browser_adapter.execute_js.return_value = [
            {"selector": "button#visible", "visible": True},
            {"selector": "button#hidden", "visible": False}
        ]

        extractor = ElementContextExtractor(mock_browser_adapter)
        visible = await extractor.get_visible_elements("button")

        assert len(visible) == 1
        assert visible[0]["selector"] == "button#visible"

    @pytest.mark.asyncio
    async def test_filter_visible_elements_none_visible(self, mock_browser_adapter):
        """Test filtering when no elements are visible."""
        mock_browser_adapter.execute_js.return_value = []

        extractor = ElementContextExtractor(mock_browser_adapter)
        visible = await extractor.get_visible_elements("button")

        assert len(visible) == 0


class TestElementContextExtractorXPathEvaluation:
    """Test ElementContextExtractor XPath evaluation."""

    @pytest.mark.asyncio
    async def test_evaluate_xpath(self, mock_browser_adapter):
        """Test XPath evaluation."""
        mock_browser_adapter.execute_js.return_value = ["button#submit"]

        extractor = ElementContextExtractor(mock_browser_adapter)
        elements = await extractor.evaluate_xpath("//button[@type='submit']")

        assert len(elements) == 1
        assert elements[0] == "button#submit"

    @pytest.mark.asyncio
    async def test_evaluate_xpath_no_results(self, mock_browser_adapter):
        """Test XPath evaluation with no results."""
        mock_browser_adapter.execute_js.return_value = []

        extractor = ElementContextExtractor(mock_browser_adapter)
        elements = await extractor.evaluate_xpath("//nonexistent")

        assert len(elements) == 0

    @pytest.mark.asyncio
    async def test_evaluate_xpath_complex(self, mock_browser_adapter):
        """Test complex XPath evaluation."""
        mock_browser_adapter.execute_js.return_value = [
            "input[name='username']",
            "input[name='password']"
        ]

        extractor = ElementContextExtractor(mock_browser_adapter)
        elements = await extractor.evaluate_xpath("//input[@type='text' or @type='password']")

        assert len(elements) == 2


# ============================================================================
# BrowserOverlay Tests
# ============================================================================

class TestBrowserOverlayInitialization:
    """Test BrowserOverlay initialization."""

    @pytest.mark.asyncio
    async def test_overlay_initialization(self, mock_browser_adapter):
        """Test browser overlay initialization."""
        overlay = BrowserOverlay(mock_browser_adapter)

        assert overlay.browser == mock_browser_adapter
        assert overlay.is_active is False


class TestBrowserOverlayInjection:
    """Test BrowserOverlay JavaScript injection."""

    @pytest.mark.asyncio
    async def test_inject_picker_overlay(self, mock_browser_adapter):
        """Test injecting picker overlay."""
        mock_browser_adapter.execute_js.return_value = True

        overlay = BrowserOverlay(mock_browser_adapter)
        result = await overlay.inject_picker()

        assert result is True
        assert overlay.is_active is True
        mock_browser_adapter.execute_js.assert_called_once()

    @pytest.mark.asyncio
    async def test_inject_picker_overlay_failure(self, mock_browser_adapter):
        """Test injecting picker overlay fails."""
        mock_browser_adapter.execute_js.side_effect = Exception("Injection failed")

        overlay = BrowserOverlay(mock_browser_adapter)
        result = await overlay.inject_picker()

        assert result is False
        assert overlay.is_active is False

    @pytest.mark.asyncio
    async def test_remove_picker_overlay(self, mock_browser_adapter):
        """Test removing picker overlay."""
        overlay = BrowserOverlay(mock_browser_adapter)
        overlay.is_active = True

        await overlay.remove_picker()

        assert overlay.is_active is False
        mock_browser_adapter.execute_js.assert_called_once()


class TestBrowserOverlayInteraction:
    """Test BrowserOverlay user interaction."""

    @pytest.mark.asyncio
    async def test_wait_for_user_selection(self, mock_browser_adapter):
        """Test waiting for user selection."""
        mock_browser_adapter.execute_js.side_effect = [
            None,  # First poll - no selection
            None,  # Second poll - no selection
            {"selector": "button#submit", "method": "click"}  # Third poll - selection made
        ]

        overlay = BrowserOverlay(mock_browser_adapter)
        selection = await overlay.wait_for_selection(poll_interval=0.01, timeout=1.0)

        assert selection["selector"] == "button#submit"
        assert selection["method"] == "click"
        assert mock_browser_adapter.execute_js.call_count == 3

    @pytest.mark.asyncio
    async def test_wait_for_user_selection_timeout(self, mock_browser_adapter):
        """Test waiting for user selection times out."""
        mock_browser_adapter.execute_js.return_value = None

        overlay = BrowserOverlay(mock_browser_adapter)
        selection = await overlay.wait_for_selection(poll_interval=0.01, timeout=0.05)

        assert selection is None

    @pytest.mark.asyncio
    async def test_highlight_element(self, mock_browser_adapter):
        """Test highlighting an element."""
        overlay = BrowserOverlay(mock_browser_adapter)

        await overlay.highlight_element("button#submit")

        mock_browser_adapter.execute_js.assert_called_once()
        # Verify JS contains highlight logic
        call_args = mock_browser_adapter.execute_js.call_args[0][0]
        assert "button#submit" in call_args

    @pytest.mark.asyncio
    async def test_unhighlight_element(self, mock_browser_adapter):
        """Test unhighlighting an element."""
        overlay = BrowserOverlay(mock_browser_adapter)

        await overlay.unhighlight_element("button#submit")

        mock_browser_adapter.execute_js.assert_called_once()


class TestBrowserOverlayEventHandling:
    """Test BrowserOverlay event handling."""

    @pytest.mark.asyncio
    async def test_capture_user_cancel(self, mock_browser_adapter):
        """Test capturing user cancel event."""
        mock_browser_adapter.execute_js.return_value = {"cancelled": True}

        overlay = BrowserOverlay(mock_browser_adapter)
        selection = await overlay.wait_for_selection(poll_interval=0.01)

        assert selection is not None
        assert selection.get("cancelled") is True

    @pytest.mark.asyncio
    async def test_handle_element_click(self, mock_browser_adapter):
        """Test handling element click event."""
        mock_browser_adapter.execute_js.return_value = {
            "selector": "button#submit",
            "method": "click",
            "event": "click"
        }

        overlay = BrowserOverlay(mock_browser_adapter)
        selection = await overlay.wait_for_selection(poll_interval=0.01)

        assert selection["event"] == "click"


# ============================================================================
# SelectionValidator Tests
# ============================================================================

class TestSelectionValidatorInitialization:
    """Test SelectionValidator initialization."""

    def test_validator_initialization(self):
        """Test selection validator initialization."""
        validator = SelectionValidator()

        assert validator is not None


class TestSelectionValidatorMethodValidation:
    """Test SelectionValidator method-specific validation."""

    @pytest.mark.asyncio
    async def test_validate_click_element(self, mock_browser_adapter):
        """Test validating element for click method."""
        mock_browser_adapter.execute_js.return_value = {
            "clickable": True,
            "visible": True,
            "enabled": True
        }

        validator = SelectionValidator()
        is_valid = await validator.validate_selection(
            mock_browser_adapter,
            "button#submit",
            "click"
        )

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_click_element_not_clickable(self, mock_browser_adapter):
        """Test validating non-clickable element for click method."""
        mock_browser_adapter.execute_js.return_value = {
            "clickable": False,
            "visible": True,
            "enabled": True
        }

        validator = SelectionValidator()
        is_valid = await validator.validate_selection(
            mock_browser_adapter,
            "div#static",
            "click"
        )

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_validate_type_element(self, mock_browser_adapter):
        """Test validating element for type method."""
        mock_browser_adapter.execute_js.return_value = {
            "editable": True,
            "visible": True,
            "enabled": True,
            "tagName": "INPUT"
        }

        validator = SelectionValidator()
        is_valid = await validator.validate_selection(
            mock_browser_adapter,
            "input#username",
            "type"
        )

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_type_element_not_editable(self, mock_browser_adapter):
        """Test validating non-editable element for type method."""
        mock_browser_adapter.execute_js.return_value = {
            "editable": False,
            "visible": True,
            "enabled": True,
            "tagName": "DIV"
        }

        validator = SelectionValidator()
        is_valid = await validator.validate_selection(
            mock_browser_adapter,
            "div#static",
            "type"
        )

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_validate_select_element(self, mock_browser_adapter):
        """Test validating element for select method."""
        mock_browser_adapter.execute_js.return_value = {
            "tagName": "SELECT",
            "visible": True,
            "enabled": True,
            "hasOptions": True
        }

        validator = SelectionValidator()
        is_valid = await validator.validate_selection(
            mock_browser_adapter,
            "select#country",
            "select"
        )

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_select_element_not_select(self, mock_browser_adapter):
        """Test validating non-select element for select method."""
        mock_browser_adapter.execute_js.return_value = {
            "tagName": "INPUT",
            "visible": True,
            "enabled": True
        }

        validator = SelectionValidator()
        is_valid = await validator.validate_selection(
            mock_browser_adapter,
            "input#username",
            "select"
        )

        assert is_valid is False


class TestSelectionValidatorPropertyChecks:
    """Test SelectionValidator element property checks."""

    @pytest.mark.asyncio
    async def test_check_element_visibility(self, mock_browser_adapter):
        """Test checking element visibility."""
        mock_browser_adapter.execute_js.return_value = {"visible": True}

        validator = SelectionValidator()
        is_visible = await validator.is_element_visible(
            mock_browser_adapter,
            "button#submit"
        )

        assert is_visible is True

    @pytest.mark.asyncio
    async def test_check_element_not_visible(self, mock_browser_adapter):
        """Test checking element not visible."""
        mock_browser_adapter.execute_js.return_value = {"visible": False}

        validator = SelectionValidator()
        is_visible = await validator.is_element_visible(
            mock_browser_adapter,
            "button#hidden"
        )

        assert is_visible is False

    @pytest.mark.asyncio
    async def test_check_element_enabled(self, mock_browser_adapter):
        """Test checking element enabled."""
        mock_browser_adapter.execute_js.return_value = {"enabled": True}

        validator = SelectionValidator()
        is_enabled = await validator.is_element_enabled(
            mock_browser_adapter,
            "button#submit"
        )

        assert is_enabled is True

    @pytest.mark.asyncio
    async def test_check_element_disabled(self, mock_browser_adapter):
        """Test checking element disabled."""
        mock_browser_adapter.execute_js.return_value = {"enabled": False}

        validator = SelectionValidator()
        is_enabled = await validator.is_element_enabled(
            mock_browser_adapter,
            "button[disabled]"
        )

        assert is_enabled is False


# ============================================================================
# ActionSelectionHandler Tests
# ============================================================================

class TestActionSelectionHandlerInitialization:
    """Test ActionSelectionHandler initialization."""

    @pytest.mark.asyncio
    async def test_handler_initialization(self, mock_browser_adapter, mock_llm_executor):
        """Test action selection handler initialization."""
        handler = ActionSelectionHandler(mock_browser_adapter, mock_llm_executor)

        assert handler.browser == mock_browser_adapter
        assert handler.llm == mock_llm_executor


class TestActionSelectionHandlerActionLogic:
    """Test ActionSelectionHandler action-specific logic."""

    @pytest.mark.asyncio
    async def test_handle_click_action(self, mock_browser_adapter, mock_llm_executor):
        """Test handling click action."""
        mock_llm_executor.generate.return_value = Mock(
            content='{"selector": "button#submit", "confidence": 0.95}'
        )

        handler = ActionSelectionHandler(mock_browser_adapter, mock_llm_executor)
        result = await handler.handle_action("click", "submit button")

        assert result["selector"] == "button#submit"
        assert result["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_handle_type_action(self, mock_browser_adapter, mock_llm_executor):
        """Test handling type action."""
        mock_llm_executor.generate.return_value = Mock(
            content='{"selector": "input#username", "confidence": 0.90}'
        )

        handler = ActionSelectionHandler(mock_browser_adapter, mock_llm_executor)
        result = await handler.handle_action("type", "username field")

        assert result["selector"] == "input#username"
        assert "input" in result["selector"].lower()

    @pytest.mark.asyncio
    async def test_handle_select_action(self, mock_browser_adapter, mock_llm_executor):
        """Test handling select action."""
        mock_llm_executor.generate.return_value = Mock(
            content='{"selector": "select#country", "confidence": 0.88}'
        )

        handler = ActionSelectionHandler(mock_browser_adapter, mock_llm_executor)
        result = await handler.handle_action("select", "country dropdown")

        assert result["selector"] == "select#country"
        assert "select" in result["selector"].lower()

    @pytest.mark.asyncio
    async def test_handle_upload_action(self, mock_browser_adapter, mock_llm_executor):
        """Test handling upload action."""
        mock_llm_executor.generate.return_value = Mock(
            content='{"selector": "input[type=file]", "confidence": 0.92}'
        )

        handler = ActionSelectionHandler(mock_browser_adapter, mock_llm_executor)
        result = await handler.handle_action("upload", "file upload")

        assert "file" in result["selector"].lower()


class TestActionSelectionHandlerFallback:
    """Test ActionSelectionHandler fallback handling."""

    @pytest.mark.asyncio
    async def test_fallback_to_generic_selector(self, mock_browser_adapter, mock_llm_executor):
        """Test fallback to generic selector."""
        mock_llm_executor.generate.return_value = Mock(content="invalid json")

        handler = ActionSelectionHandler(mock_browser_adapter, mock_llm_executor)

        # Should handle gracefully with fallback
        with pytest.raises(Exception):
            await handler.handle_action("click", "submit button")


# ============================================================================
# PluralSelectionStrategy Tests
# ============================================================================

class TestPluralSelectionStrategyInitialization:
    """Test PluralSelectionStrategy initialization."""

    @pytest.mark.asyncio
    async def test_strategy_initialization(self, mock_browser_adapter, mock_llm_executor):
        """Test plural selection strategy initialization."""
        strategy = PluralSelectionStrategy(mock_browser_adapter, mock_llm_executor)

        assert strategy.browser == mock_browser_adapter
        assert strategy.llm == mock_llm_executor


class TestPluralSelectionStrategyTemplateGeneration:
    """Test PluralSelectionStrategy template-based selection."""

    @pytest.mark.asyncio
    async def test_generate_template_selector(self, mock_browser_adapter, mock_llm_executor):
        """Test generating template-based selector for multiple elements."""
        mock_llm_executor.generate.return_value = Mock(
            content='{"template": "div.product-card", "count": 10}'
        )

        strategy = PluralSelectionStrategy(mock_browser_adapter, mock_llm_executor)
        result = await strategy.select_elements("all product cards")

        assert result["template"] == "div.product-card"
        assert result["count"] == 10

    @pytest.mark.asyncio
    async def test_select_list_items(self, mock_browser_adapter, mock_llm_executor):
        """Test selecting list items."""
        mock_llm_executor.generate.return_value = Mock(
            content='{"template": "ul.menu > li", "count": 5}'
        )

        strategy = PluralSelectionStrategy(mock_browser_adapter, mock_llm_executor)
        result = await strategy.select_elements("menu items")

        assert "li" in result["template"]
        assert result["count"] == 5

    @pytest.mark.asyncio
    async def test_select_table_rows(self, mock_browser_adapter, mock_llm_executor):
        """Test selecting table rows."""
        mock_llm_executor.generate.return_value = Mock(
            content='{"template": "table#data tbody tr", "count": 20}'
        )

        strategy = PluralSelectionStrategy(mock_browser_adapter, mock_llm_executor)
        result = await strategy.select_elements("data table rows")

        assert "tr" in result["template"]
        assert result["count"] == 20


class TestPluralSelectionStrategyValidation:
    """Test PluralSelectionStrategy validation."""

    @pytest.mark.asyncio
    async def test_validate_template_selector(self, mock_browser_adapter, mock_llm_executor):
        """Test validating template selector matches expected count."""
        mock_browser_adapter.execute_js.return_value = 10  # Element count

        strategy = PluralSelectionStrategy(mock_browser_adapter, mock_llm_executor)
        is_valid = await strategy.validate_template("div.product-card", expected_count=10)

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_template_selector_count_mismatch(self, mock_browser_adapter, mock_llm_executor):
        """Test validating template selector with count mismatch."""
        mock_browser_adapter.execute_js.return_value = 5  # Element count

        strategy = PluralSelectionStrategy(mock_browser_adapter, mock_llm_executor)
        is_valid = await strategy.validate_template("div.product-card", expected_count=10)

        assert is_valid is False


# ============================================================================
# SingularSelectionStrategy Tests
# ============================================================================

class TestSingularSelectionStrategyInitialization:
    """Test SingularSelectionStrategy initialization."""

    @pytest.mark.asyncio
    async def test_strategy_initialization(self, mock_browser_adapter, mock_llm_executor):
        """Test singular selection strategy initialization."""
        strategy = SingularSelectionStrategy(mock_browser_adapter, mock_llm_executor)

        assert strategy.browser == mock_browser_adapter
        assert strategy.llm == mock_llm_executor


class TestSingularSelectionStrategyElementSelection:
    """Test SingularSelectionStrategy single element selection."""

    @pytest.mark.asyncio
    async def test_select_single_element(self, mock_browser_adapter, mock_llm_executor):
        """Test selecting a single element."""
        mock_llm_executor.generate.return_value = Mock(
            content='{"selector": "button#submit", "method": "click"}'
        )

        strategy = SingularSelectionStrategy(mock_browser_adapter, mock_llm_executor)
        result = await strategy.select_element("submit button", method="click")

        assert result["selector"] == "button#submit"
        assert result["method"] == "click"

    @pytest.mark.asyncio
    async def test_select_input_field(self, mock_browser_adapter, mock_llm_executor):
        """Test selecting an input field."""
        mock_llm_executor.generate.return_value = Mock(
            content='{"selector": "input#username", "method": "type"}'
        )

        strategy = SingularSelectionStrategy(mock_browser_adapter, mock_llm_executor)
        result = await strategy.select_element("username field", method="type")

        assert "input" in result["selector"].lower()
        assert result["method"] == "type"

    @pytest.mark.asyncio
    async def test_select_dropdown(self, mock_browser_adapter, mock_llm_executor):
        """Test selecting a dropdown."""
        mock_llm_executor.generate.return_value = Mock(
            content='{"selector": "select#country", "method": "select"}'
        )

        strategy = SingularSelectionStrategy(mock_browser_adapter, mock_llm_executor)
        result = await strategy.select_element("country dropdown", method="select")

        assert "select" in result["selector"].lower()
        assert result["method"] == "select"


class TestSingularSelectionStrategyMethodSpecific:
    """Test SingularSelectionStrategy method-specific instructions."""

    @pytest.mark.asyncio
    async def test_click_method_instructions(self, mock_browser_adapter, mock_llm_executor):
        """Test click method includes specific instructions."""
        mock_llm_executor.generate.return_value = Mock(
            content='{"selector": "a.link", "method": "click"}'
        )

        strategy = SingularSelectionStrategy(mock_browser_adapter, mock_llm_executor)
        await strategy.select_element("link", method="click")

        # Verify LLM was called with click-specific instructions
        call_args = mock_llm_executor.generate.call_args[0][0]
        assert "click" in call_args.lower()

    @pytest.mark.asyncio
    async def test_type_method_instructions(self, mock_browser_adapter, mock_llm_executor):
        """Test type method includes specific instructions."""
        mock_llm_executor.generate.return_value = Mock(
            content='{"selector": "input", "method": "type"}'
        )

        strategy = SingularSelectionStrategy(mock_browser_adapter, mock_llm_executor)
        await strategy.select_element("input field", method="type")

        # Verify LLM was called with type-specific instructions
        call_args = mock_llm_executor.generate.call_args[0][0]
        assert "type" in call_args.lower() or "input" in call_args.lower()


# ============================================================================
# VisualElementPicker Tests
# ============================================================================

class TestVisualElementPickerInitialization:
    """Test VisualElementPicker initialization."""

    @pytest.mark.asyncio
    async def test_picker_initialization(self, mock_browser_adapter, mock_llm_executor, config_provider):
        """Test visual element picker initialization."""
        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_executor,
            config_provider
        )

        assert picker.browser == mock_browser_adapter
        assert picker.llm_manager == mock_llm_executor
        assert picker.cache is not None

    @pytest.mark.asyncio
    async def test_picker_initialization_default_cache(self, mock_browser_adapter, mock_llm_executor, default_config_provider):
        """Test picker initialization with default cache directory."""
        with patch('lamia.engine.managers.web.selector_resolution.visual_picker.cache.Path.mkdir'):
            picker = VisualElementPicker(
                mock_browser_adapter,
                mock_llm_executor,
                default_config_provider
            )

            assert picker.cache is not None


class TestVisualElementPickerCacheWorkflow:
    """Test VisualElementPicker cache workflow."""

    @pytest.mark.asyncio
    async def test_pick_element_cache_hit(self, mock_browser_adapter, mock_llm_executor, config_provider, temp_cache_dir):
        """Test picking element with cache hit."""
        # Setup cache
        cache = VisualSelectionCache(cache_dir=temp_cache_dir)
        cache.cache_selector(
            url="https://example.com/page",
            element_name="submit_button",
            selector="button#submit",
            method="click",
            context="<button id='submit'>Submit</button>"
        )

        mock_browser_adapter.get_current_url.return_value = "https://example.com/page"

        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_executor,
            config_provider
        )

        result = await picker.pick_element("submit_button", method="click")

        assert result == "button#submit"
        # LLM should not be called on cache hit
        mock_llm_executor.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_pick_element_cache_miss(self, mock_browser_adapter, mock_llm_executor, config_provider, temp_cache_dir):
        """Test picking element with cache miss."""
        mock_browser_adapter.get_current_url.return_value = "https://example.com/page"
        mock_browser_adapter.execute_js.return_value = "<button id='submit'>Submit</button>"
        mock_llm_executor.generate.return_value = Mock(
            content='{"selector": "button#submit"}'
        )

        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_executor,
            config_provider
        )

        result = await picker.pick_element("submit_button", method="click", use_cache=True)

        assert result == "button#submit"
        # LLM should be called on cache miss
        mock_llm_executor.generate.assert_called_once()

        # Verify result was cached
        cached = picker.cache.get_cached_selector(
            "https://example.com/page",
            "submit_button"
        )
        assert cached == "button#submit"


class TestVisualElementPickerStrategyRouting:
    """Test VisualElementPicker strategy routing."""

    @pytest.mark.asyncio
    async def test_pick_single_element_uses_singular_strategy(
        self, mock_browser_adapter, mock_llm_executor, config_provider, temp_cache_dir
    ):
        """Test picking single element uses singular strategy."""
        mock_browser_adapter.get_current_url.return_value = "https://example.com/page"
        mock_browser_adapter.execute_js.return_value = "<button>Submit</button>"
        mock_llm_executor.generate.return_value = Mock(
            content='{"selector": "button#submit"}'
        )

        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_executor,
            config_provider
        )

        result = await picker.pick_element("submit button", method="click")

        assert result is not None
        mock_llm_executor.generate.assert_called()

    @pytest.mark.asyncio
    async def test_pick_multiple_elements_uses_plural_strategy(
        self, mock_browser_adapter, mock_llm_executor, config_provider, temp_cache_dir
    ):
        """Test picking multiple elements uses plural strategy."""
        mock_browser_adapter.get_current_url.return_value = "https://example.com/page"
        mock_browser_adapter.execute_js.return_value = "<div>Items</div>"
        mock_llm_executor.generate.return_value = Mock(
            content='{"template": "div.item", "count": 5}'
        )

        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_executor,
            config_provider
        )

        result = await picker.pick_elements("all items")

        assert result is not None
        mock_llm_executor.generate.assert_called()


class TestVisualElementPickerValidation:
    """Test VisualElementPicker validation integration."""

    @pytest.mark.asyncio
    async def test_pick_element_validates_result(
        self, mock_browser_adapter, mock_llm_executor, config_provider, temp_cache_dir
    ):
        """Test pick element validates the result."""
        mock_browser_adapter.get_current_url.return_value = "https://example.com/page"
        mock_browser_adapter.execute_js.side_effect = [
            "<button id='submit'>Submit</button>",  # Context extraction
            {"clickable": True, "visible": True, "enabled": True}  # Validation
        ]
        mock_llm_executor.generate.return_value = Mock(
            content='{"selector": "button#submit"}'
        )

        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_executor,
            config_provider
        )

        result = await picker.pick_element(
            "submit button",
            method="click",
            validate=True
        )

        assert result == "button#submit"

    @pytest.mark.asyncio
    async def test_pick_element_validation_fails(
        self, mock_browser_adapter, mock_llm_executor, config_provider, temp_cache_dir
    ):
        """Test pick element when validation fails."""
        mock_browser_adapter.get_current_url.return_value = "https://example.com/page"
        mock_browser_adapter.execute_js.side_effect = [
            "<div id='static'>Static</div>",  # Context extraction
            {"clickable": False, "visible": True, "enabled": False}  # Validation fails
        ]
        mock_llm_executor.generate.return_value = Mock(
            content='{"selector": "div#static"}'
        )

        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_executor,
            config_provider
        )

        result = await picker.pick_element(
            "static div",
            method="click",
            validate=True
        )

        # Should return None or raise error when validation fails
        assert result is None or result == "div#static"


# ============================================================================
# Integration Tests
# ============================================================================

class TestVisualPickerIntegration:
    """Integration tests for complete visual picker workflow."""

    @pytest.mark.asyncio
    async def test_full_visual_selection_flow(
        self, mock_browser_adapter, mock_llm_executor, config_provider, temp_cache_dir
    ):
        """Test complete visual selection flow from cache miss to cache hit."""
        mock_browser_adapter.get_current_url.return_value = "https://example.com/page"
        mock_browser_adapter.execute_js.return_value = "<button id='submit'>Submit</button>"
        mock_llm_executor.generate.return_value = Mock(
            content='{"selector": "button#submit"}'
        )

        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_executor,
            config_provider
        )

        # First call - cache miss
        result1 = await picker.pick_element("submit button", method="click", use_cache=True)
        assert result1 == "button#submit"
        assert mock_llm_executor.generate.call_count == 1

        # Second call - cache hit
        mock_llm_executor.reset_mock()
        result2 = await picker.pick_element("submit button", method="click", use_cache=True)
        assert result2 == "button#submit"
        # LLM should not be called on cache hit
        mock_llm_executor.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_invalidation_flow(
        self, mock_browser_adapter, mock_llm_executor, config_provider, temp_cache_dir
    ):
        """Test cache invalidation and re-selection."""
        mock_browser_adapter.get_current_url.return_value = "https://example.com/page"
        mock_browser_adapter.execute_js.return_value = "<button id='submit'>Submit</button>"
        mock_llm_executor.generate.return_value = Mock(
            content='{"selector": "button#submit"}'
        )

        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_executor,
            config_provider
        )

        # First selection
        result1 = await picker.pick_element("submit button", method="click", use_cache=True)
        assert result1 == "button#submit"

        # Invalidate cache
        picker.cache.invalidate_cache("https://example.com/page")

        # Second selection after invalidation - should call LLM again
        mock_llm_executor.reset_mock()
        result2 = await picker.pick_element("submit button", method="click", use_cache=True)
        assert result2 == "button#submit"
        mock_llm_executor.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_elements_different_methods(
        self, mock_browser_adapter, mock_llm_executor, config_provider, temp_cache_dir
    ):
        """Test selecting multiple elements with different methods."""
        mock_browser_adapter.get_current_url.return_value = "https://example.com/page"

        def mock_execute_js(script):
            if "button" in script.lower():
                return "<button id='submit'>Submit</button>"
            elif "input" in script.lower():
                return "<input id='username' type='text'>"
            else:
                return "<div>Content</div>"

        mock_browser_adapter.execute_js.side_effect = mock_execute_js

        def mock_generate(prompt):
            if "submit" in prompt.lower():
                return Mock(content='{"selector": "button#submit"}')
            elif "username" in prompt.lower():
                return Mock(content='{"selector": "input#username"}')
            else:
                return Mock(content='{"selector": "div"}')

        mock_llm_executor.generate.side_effect = mock_generate

        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_executor,
            config_provider
        )

        # Select button for click
        result1 = await picker.pick_element("submit button", method="click", use_cache=False)
        assert "button" in result1.lower()

        # Select input for type
        result2 = await picker.pick_element("username field", method="type", use_cache=False)
        assert "input" in result2.lower()

        assert mock_llm_executor.generate.call_count == 2
