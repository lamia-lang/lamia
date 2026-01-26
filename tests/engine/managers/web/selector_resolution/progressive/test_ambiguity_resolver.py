"""Tests for AmbiguityResolver."""

import pytest
from unittest.mock import Mock, AsyncMock

from lamia.engine.managers.web.selector_resolution.progressive.ambiguity_resolver import AmbiguityResolver


@pytest.fixture
def mock_browser_adapter():
    """Create a mock browser adapter."""
    browser = Mock()
    browser.get_elements = AsyncMock(return_value=[])
    browser.execute_script = AsyncMock(return_value=None)
    return browser


@pytest.fixture
def mock_cache():
    """Create a mock cache."""
    cache = Mock()
    cache.get = Mock(return_value=None)
    cache.set = Mock()
    return cache


@pytest.mark.asyncio
class TestAmbiguityResolver:

    def test_init(self, mock_browser_adapter, mock_cache):
        """Test basic initialization."""
        resolver = AmbiguityResolver(mock_browser_adapter, mock_cache)

        assert resolver.browser == mock_browser_adapter
        assert resolver.cache == mock_cache

    async def test_get_outer_html(self, mock_browser_adapter, mock_cache):
        """Test getting element outer HTML."""
        mock_browser_adapter.execute_script.return_value = "<button>Click me</button>"

        resolver = AmbiguityResolver(mock_browser_adapter, mock_cache)
        element = Mock()

        html = await resolver._get_outer_html(element)

        assert html == "<button>Click me</button>"

    async def test_get_xpath(self, mock_browser_adapter, mock_cache):
        """Test generating XPath for element."""
        mock_browser_adapter.execute_script.return_value = "//div[@id='content']/button[1]"

        resolver = AmbiguityResolver(mock_browser_adapter, mock_cache)
        element = Mock()

        xpath = await resolver._get_xpath(element)

        assert xpath.startswith("//")

    async def test_get_visual_location(self, mock_browser_adapter, mock_cache):
        """Test getting visual location of element."""
        mock_browser_adapter.execute_script.return_value = "top left"

        resolver = AmbiguityResolver(mock_browser_adapter, mock_cache)
        element = Mock()

        location = await resolver._get_visual_location(element)

        assert location in ["top left", "top center", "top right",
                           "middle left", "middle center", "middle right",
                           "bottom left", "bottom center", "bottom right"]

    def test_truncate_html(self, mock_browser_adapter, mock_cache):
        """Test HTML truncation."""
        resolver = AmbiguityResolver(mock_browser_adapter, mock_cache)

        long_html = "a" * 200
        truncated = resolver._truncate_html(long_html, max_length=50)

        assert len(truncated) <= 53  # 50 + "..."
        assert truncated.endswith("...")

