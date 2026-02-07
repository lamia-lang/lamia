"""Tests for ElementContextExtractor."""

import pytest
from unittest.mock import AsyncMock, Mock

from lamia.engine.managers.web.selector_resolution.visual_picker.context_extractor import ElementContextExtractor


@pytest.fixture
def mock_browser_adapter():
    """Create mock browser adapter."""
    adapter = AsyncMock()
    adapter.execute_script = AsyncMock()
    adapter.get_elements = AsyncMock(return_value=[])
    return adapter


class TestElementContextExtractorInitialization:
    """Test ElementContextExtractor initialization."""

    def test_extractor_initialization(self, mock_browser_adapter):
        """Test context extractor initialization."""
        extractor = ElementContextExtractor(mock_browser_adapter)

        assert extractor.browser == mock_browser_adapter


class TestElementContextExtractorContextExtraction:
    """Test ElementContextExtractor context extraction."""

    @pytest.mark.asyncio
    async def test_extract_contexts_for_xpath(self, mock_browser_adapter):
        """Test extracting contexts for XPath selector."""
        mock_browser_adapter.execute_script.return_value = [
            {
                "element_html": "<button id='submit'>Submit</button>",
                "element_xpath": "//button[@id='submit'][1]",
                "element_index": 0,
                "is_visible": True,
                "bounds": {"x": 100, "y": 200, "width": 80, "height": 30}
            }
        ]

        extractor = ElementContextExtractor(mock_browser_adapter)
        contexts = await extractor.extract_contexts_for_xpath("//button[@id='submit']")

        assert len(contexts) == 1
        assert contexts[0]["element_html"] == "<button id='submit'>Submit</button>"
        assert contexts[0]["element_xpath"] == "//button[@id='submit'][1]"
        assert contexts[0]["element_index"] == 0
        mock_browser_adapter.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_contexts_filters_invisible(self, mock_browser_adapter):
        """Test that invisible elements are filtered out."""
        mock_browser_adapter.execute_script.return_value = [
            {
                "element_html": "<button>Visible</button>",
                "element_xpath": "//button[1]",
                "element_index": 0,
                "is_visible": True,
                "bounds": {}
            },
            {
                "element_html": "<button>Hidden</button>",
                "element_xpath": "//button[2]",
                "element_index": 1,
                "is_visible": False,
                "bounds": {}
            }
        ]

        extractor = ElementContextExtractor(mock_browser_adapter)
        contexts = await extractor.extract_contexts_for_xpath("//button")

        assert len(contexts) == 1
        assert "Visible" in contexts[0]["element_html"]

    @pytest.mark.asyncio
    async def test_extract_contexts_empty_result(self, mock_browser_adapter):
        """Test extracting contexts when no elements found."""
        mock_browser_adapter.execute_script.return_value = []

        extractor = ElementContextExtractor(mock_browser_adapter)
        contexts = await extractor.extract_contexts_for_xpath("//nonexistent")

        assert len(contexts) == 0

    @pytest.mark.asyncio
    async def test_extract_contexts_filters_missing_html(self, mock_browser_adapter):
        """Test that contexts without HTML are filtered out."""
        mock_browser_adapter.execute_script.return_value = [
            {
                "element_html": "<button>Valid</button>",
                "element_xpath": "//button[1]",
                "element_index": 0,
                "is_visible": True,
                "bounds": {}
            },
            {
                "element_html": "",
                "element_xpath": "//button[2]",
                "element_index": 1,
                "is_visible": True,
                "bounds": {}
            }
        ]

        extractor = ElementContextExtractor(mock_browser_adapter)
        contexts = await extractor.extract_contexts_for_xpath("//button")

        assert len(contexts) == 1
        assert "Valid" in contexts[0]["element_html"]

    @pytest.mark.asyncio
    async def test_extract_contexts_handles_exception(self, mock_browser_adapter):
        """Test that exceptions during extraction are handled gracefully."""
        mock_browser_adapter.execute_script.side_effect = Exception("Script error")

        extractor = ElementContextExtractor(mock_browser_adapter)
        contexts = await extractor.extract_contexts_for_xpath("//button")

        assert len(contexts) == 0


class TestElementContextExtractorFindElements:
    """Test ElementContextExtractor element finding within context."""

    @pytest.mark.asyncio
    async def test_find_elements_within_context_css(self, mock_browser_adapter):
        """Test finding elements with CSS selector within context."""
        mock_browser_adapter.execute_script.return_value = [
            {
                "tagName": "INPUT",
                "outerHTML": "<input type='text'>",
                "textContent": "",
                "value": "",
                "id": "username",
                "className": ""
            }
        ]

        extractor = ElementContextExtractor(mock_browser_adapter)
        context = {"element_xpath": "//form[1]"}

        elements = await extractor.find_elements_within_context(context, "input[type='text']")

        assert len(elements) == 1
        assert elements[0]["tagName"] == "INPUT"

    @pytest.mark.asyncio
    async def test_find_elements_within_context_xpath(self, mock_browser_adapter):
        """Test finding elements with XPath selector within context."""
        mock_browser_adapter.get_elements.return_value = [Mock(), Mock()]

        extractor = ElementContextExtractor(mock_browser_adapter)
        context = {"element_xpath": "//form[1]"}

        elements = await extractor.find_elements_within_context(context, "//input[@type='text']")

        assert len(elements) == 2
        mock_browser_adapter.get_elements.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_elements_within_context_missing_xpath(self, mock_browser_adapter):
        """Test finding elements when context has no xpath."""
        extractor = ElementContextExtractor(mock_browser_adapter)
        context = {}

        elements = await extractor.find_elements_within_context(context, "input")

        assert len(elements) == 0

    @pytest.mark.asyncio
    async def test_find_elements_within_context_css_exception(self, mock_browser_adapter):
        """Test handling exception when finding elements with CSS."""
        mock_browser_adapter.execute_script.side_effect = Exception("Script error")

        extractor = ElementContextExtractor(mock_browser_adapter)
        context = {"element_xpath": "//form[1]"}

        elements = await extractor.find_elements_within_context(context, "input[type='text']")

        assert len(elements) == 0

    @pytest.mark.asyncio
    async def test_find_elements_within_context_xpath_exception(self, mock_browser_adapter):
        """Test handling exception when finding elements with XPath."""
        mock_browser_adapter.get_elements.side_effect = Exception("Get elements error")

        extractor = ElementContextExtractor(mock_browser_adapter)
        context = {"element_xpath": "//form[1]"}

        elements = await extractor.find_elements_within_context(context, "//input[@type='text']")

        assert len(elements) == 0


class TestElementContextExtractorResolveWithinContexts:
    """Test ElementContextExtractor resolve_within_contexts method."""

    @pytest.mark.asyncio
    async def test_resolve_within_contexts_basic(self, mock_browser_adapter):
        """Test basic resolution within contexts."""
        mock_llm_manager = AsyncMock()
        mock_llm_result = Mock()
        mock_llm_result.validated_text = '["button.submit", "button#submit"]'
        mock_llm_manager.execute = AsyncMock(return_value=mock_llm_result)

        mock_browser_adapter.execute_script.return_value = [
            {"tagName": "BUTTON", "outerHTML": "<button class='submit'>Submit</button>"}
        ]

        extractor = ElementContextExtractor(mock_browser_adapter)
        contexts = [
            {
                "element_html": "<div><button class='submit'>Submit</button></div>",
                "element_xpath": "//div[1]",
                "element_index": 0,
                "is_visible": True,
                "bounds": {}
            }
        ]

        result = await extractor.resolve_within_contexts(
            contexts,
            "submit button",
            mock_llm_manager
        )

        assert "matches" in result
        assert "contexts_processed" in result
        assert "total_matches" in result
        assert result["contexts_processed"] == 1

    @pytest.mark.asyncio
    async def test_resolve_within_contexts_empty_contexts(self, mock_browser_adapter):
        """Test resolution with empty contexts list."""
        mock_llm_manager = AsyncMock()

        extractor = ElementContextExtractor(mock_browser_adapter)

        result = await extractor.resolve_within_contexts(
            [],
            "submit button",
            mock_llm_manager
        )

        assert result["contexts_processed"] == 0
        assert result["total_matches"] == 0
        assert len(result["matches"]) == 0

    @pytest.mark.asyncio
    async def test_resolve_within_contexts_context_without_html(self, mock_browser_adapter):
        """Test resolution with context missing HTML."""
        mock_llm_manager = AsyncMock()

        extractor = ElementContextExtractor(mock_browser_adapter)
        contexts = [
            {
                "element_html": "",
                "element_xpath": "//div[1]",
                "element_index": 0,
                "is_visible": True,
                "bounds": {}
            }
        ]

        result = await extractor.resolve_within_contexts(
            contexts,
            "submit button",
            mock_llm_manager
        )

        assert result["contexts_processed"] == 1
        assert result["total_matches"] == 0

    @pytest.mark.asyncio
    async def test_resolve_within_contexts_handles_exception(self, mock_browser_adapter):
        """Test that exceptions during resolution are handled."""
        mock_llm_manager = AsyncMock()
        mock_llm_manager.execute.side_effect = Exception("LLM error")

        extractor = ElementContextExtractor(mock_browser_adapter)
        contexts = [
            {
                "element_html": "<div><button>Submit</button></div>",
                "element_xpath": "//div[1]",
                "element_index": 0,
                "is_visible": True,
                "bounds": {}
            }
        ]

        result = await extractor.resolve_within_contexts(
            contexts,
            "submit button",
            mock_llm_manager
        )

        assert result["contexts_processed"] == 1
        assert result["total_matches"] == 0
