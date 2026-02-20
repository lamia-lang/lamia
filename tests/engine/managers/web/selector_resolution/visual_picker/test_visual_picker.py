"""Tests for VisualElementPicker."""

import pytest
from unittest.mock import AsyncMock, Mock, MagicMock, patch

from lamia.engine.managers.web.selector_resolution.visual_picker.visual_picker import VisualElementPicker
from lamia.engine.config_provider import ConfigProvider


@pytest.fixture
def mock_browser_adapter():
    """Create mock browser adapter."""
    adapter = AsyncMock()
    adapter.execute_script = AsyncMock()
    adapter.get_elements = AsyncMock(return_value=[])
    return adapter


@pytest.fixture
def mock_llm_manager():
    """Create mock LLM manager."""
    manager = AsyncMock()
    return manager


@pytest.fixture
def config_provider(tmp_path):
    """Create config provider with isolated cache directory per test."""
    config = MagicMock(spec=ConfigProvider)
    config.is_cache_enabled = Mock(return_value=True)
    config.get_cache_dir = Mock(return_value=str(tmp_path))
    return config


class TestVisualElementPickerInitialization:
    """Test VisualElementPicker initialization."""

    def test_picker_initialization(self, mock_browser_adapter, mock_llm_manager, config_provider):
        """Test visual element picker initialization."""
        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_manager,
            config_provider
        )

        assert picker.browser == mock_browser_adapter
        assert picker.llm_manager == mock_llm_manager
        assert picker.cache is not None
        assert picker.overlay is not None
        assert picker.validator is not None

    def test_picker_creates_overlay(self, mock_browser_adapter, mock_llm_manager, config_provider):
        """Test that picker creates BrowserOverlay instance."""
        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_manager,
            config_provider
        )

        assert picker.overlay.browser == mock_browser_adapter

    def test_picker_creates_cache(self, mock_browser_adapter, mock_llm_manager, config_provider):
        """Test that picker creates VisualSelectionCache instance."""
        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_manager,
            config_provider
        )

        assert picker.cache is not None

    def test_picker_creates_validator(self, mock_browser_adapter, mock_llm_manager, config_provider):
        """Test that picker creates SelectionValidator instance."""
        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_manager,
            config_provider
        )

        assert picker.validator is not None


class TestVisualElementPickerPickElementForMethod:
    """Test VisualElementPicker pick_element_for_method method."""

    @pytest.mark.asyncio
    async def test_pick_element_cache_hit(self, mock_browser_adapter, mock_llm_manager, config_provider):
        """Test picking element with cache hit."""
        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_manager,
            config_provider
        )

        await picker.cache.set(
            method_name="click",
            description="submit button",
            page_url="https://example.com/page",
            selection_data={"selector": "button#submit", "element_count": 1}
        )

        mock_browser_adapter.get_elements = AsyncMock(return_value=[Mock()])

        selector, elements = await picker.pick_element_for_method(
            method_name="click",
            description="submit button",
            page_url="https://example.com/page"
        )

        assert selector == "button#submit"
        assert len(elements) == 1
        mock_llm_manager.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_pick_element_cache_miss_shows_overlay(self, mock_browser_adapter, mock_llm_manager, config_provider):
        """Test picking element with cache miss shows overlay."""
        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_manager,
            config_provider
        )

        with patch.object(picker.overlay, 'pick_single_element', new_callable=AsyncMock) as mock_pick:
            mock_pick.return_value = {
                "selected_element": {
                    "tagName": "BUTTON",
                    "xpath": "//button[@id='submit']",
                    "outerHTML": "<button id='submit'>Submit</button>"
                },
                "selection_type": "single"
            }

            mock_llm_result = Mock()
            mock_llm_result.validated_text = "//button[@id='submit']"
            mock_llm_manager.execute = AsyncMock(return_value=mock_llm_result)

            mock_browser_adapter.get_elements = AsyncMock(return_value=[Mock()])

            selector, elements = await picker.pick_element_for_method(
                method_name="click",
                description="submit button",
                page_url="https://example.com/page"
            )

            assert selector is not None
            mock_pick.assert_called_once()

    @pytest.mark.asyncio
    async def test_pick_element_plural_method(self, mock_browser_adapter, mock_llm_manager, config_provider):
        """Test picking elements for plural method."""
        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_manager,
            config_provider
        )

        with patch.object(picker, '_show_picker', new_callable=AsyncMock) as mock_show:
            mock_show.return_value = {
                "selected_element": {"tagName": "DIV"},
                "selection_type": "template",
                "found_elements": [Mock(), Mock()],
                "working_selector": "div.item"
            }

            mock_browser_adapter.get_elements = AsyncMock(return_value=[Mock(), Mock()])

            selector, elements = await picker.pick_element_for_method(
                method_name="get_elements",
                description="all items",
                page_url="https://example.com/page"
            )

            assert selector is not None
            mock_show.assert_called_once()

    @pytest.mark.asyncio
    async def test_pick_element_validates_result(self, mock_browser_adapter, mock_llm_manager, config_provider):
        """Test that pick_element validates the result."""
        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_manager,
            config_provider
        )

        with patch.object(picker.overlay, 'pick_single_element', new_callable=AsyncMock) as mock_pick:
            mock_pick.return_value = {
                "selected_element": {
                    "tagName": "BUTTON",
                    "xpath": "//button",
                    "outerHTML": "<button>X</button>"
                },
                "selection_type": "single"
            }

            mock_llm_result = Mock()
            mock_llm_result.validated_text = "//button"
            mock_llm_manager.execute = AsyncMock(return_value=mock_llm_result)

            mock_browser_adapter.get_elements = AsyncMock(return_value=[])

            with pytest.raises(ValueError, match="found no elements"):
                await picker.pick_element_for_method(
                    method_name="click",
                    description="submit button",
                    page_url="https://example.com/page"
                )

    @pytest.mark.asyncio
    async def test_pick_element_caches_result(self, mock_browser_adapter, mock_llm_manager, config_provider):
        """Test that pick_element caches the result."""
        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_manager,
            config_provider
        )

        with patch.object(picker.overlay, 'pick_single_element', new_callable=AsyncMock) as mock_pick:
            mock_pick.return_value = {
                "selected_element": {
                    "tagName": "BUTTON",
                    "xpath": "//button[@id='submit']",
                    "outerHTML": "<button id='submit'>Submit</button>"
                },
                "selection_type": "single"
            }

            mock_llm_result = Mock()
            mock_llm_result.validated_text = "//button[@id='submit']"
            mock_llm_manager.execute = AsyncMock(return_value=mock_llm_result)

            mock_browser_adapter.get_elements = AsyncMock(return_value=[Mock()])

            await picker.pick_element_for_method(
                method_name="click",
                description="submit button",
                page_url="https://example.com/page"
            )

            cached = await picker.cache.get(
                "click",
                "submit button",
                "https://example.com/page"
            )

            assert cached is not None
            assert cached["selection_data"]["selector"] == "//button[@id='submit']"


class TestVisualElementPickerHelperMethods:
    """Test VisualElementPicker helper methods."""

    def test_get_instruction_text_singular(self, mock_browser_adapter, mock_llm_manager, config_provider):
        """Test getting instruction text for singular selection."""
        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_manager,
            config_provider
        )

        instruction = picker._get_instruction_text("click", "submit button", "singular")
        assert "select" in instruction.lower()
        assert "submit button" in instruction

    def test_get_instruction_text_plural(self, mock_browser_adapter, mock_llm_manager, config_provider):
        """Test getting instruction text for plural strategy."""
        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_manager,
            config_provider
        )

        instruction = picker._get_instruction_text("get_elements", "all items", "plural")
        assert "area" in instruction.lower()

    def test_get_element_filter_most_methods_return_none(self, mock_browser_adapter, mock_llm_manager, config_provider):
        """Test that most methods have no element filter (allow any element)."""
        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_manager,
            config_provider
        )

        assert picker._get_element_filter("click") is None
        assert picker._get_element_filter("type_text") is None
        assert picker._get_element_filter("get_element") is None

    def test_get_element_filter_upload_file(self, mock_browser_adapter, mock_llm_manager, config_provider):
        """Test that upload_file has a filter for file inputs."""
        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_manager,
            config_provider
        )

        filter_func = picker._get_element_filter("upload_file")
        assert filter_func is not None
        assert "file" in filter_func


class TestVisualElementPickerErrorHandling:
    """Test VisualElementPicker error handling."""

    @pytest.mark.asyncio
    async def test_pick_element_cache_stale(self, mock_browser_adapter, mock_llm_manager, config_provider):
        """Test handling stale cache."""
        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_manager,
            config_provider
        )

        await picker.cache.set(
            method_name="click",
            description="submit button",
            page_url="https://example.com/page",
            selection_data={"selector": "button#submit", "element_count": 1}
        )

        mock_browser_adapter.get_elements = AsyncMock(return_value=[])

        with pytest.raises(ValueError, match="Cached selection no longer valid"):
            await picker.pick_element_for_method(
                method_name="click",
                description="submit button",
                page_url="https://example.com/page"
            )

    @pytest.mark.asyncio
    async def test_pick_element_ambiguous_selection(self, mock_browser_adapter, mock_llm_manager, config_provider):
        """Test handling ambiguous selection for singular method."""
        picker = VisualElementPicker(
            mock_browser_adapter,
            mock_llm_manager,
            config_provider
        )

        with patch.object(picker.overlay, 'pick_single_element', new_callable=AsyncMock) as mock_pick:
            mock_pick.return_value = {
                "selected_element": {
                    "tagName": "BUTTON",
                    "xpath": "//button",
                    "outerHTML": "<button>X</button>"
                },
                "selection_type": "single"
            }

            mock_llm_result = Mock()
            mock_llm_result.validated_text = "//button"
            mock_llm_manager.execute = AsyncMock(return_value=mock_llm_result)

            mock_browser_adapter.get_elements = AsyncMock(return_value=[Mock(), Mock()])

            with pytest.raises(ValueError, match="ambiguous"):
                await picker.pick_element_for_method(
                    method_name="click",
                    description="submit button",
                    page_url="https://example.com/page"
                )
