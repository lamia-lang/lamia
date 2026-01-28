"""Tests for HumanAssistedAmbiguityResolver."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from lamia.engine.managers.web.selector_resolution.progressive.human_assisted_ambiguity_resolver import HumanAssistedAmbiguityResolver
from lamia.engine.managers.web.selector_resolution.progressive.progressive_selector_strategy import (
    ProgressiveSelectorStrategyIntent,
    ElementCount,
    Relationship,
    Strictness,
)


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
    cache.set = AsyncMock()
    return cache


@pytest.fixture
def single_element_intent():
    """Create intent for single element selection."""
    return ProgressiveSelectorStrategyIntent(
        element_count=ElementCount.SINGLE,
        relationship=Relationship.NONE,
        strictness=Strictness.STRICT
    )


@pytest.fixture
def multiple_element_intent():
    """Create intent for multiple element selection."""
    return ProgressiveSelectorStrategyIntent(
        element_count=ElementCount.MULTIPLE,
        relationship=Relationship.NONE,
        strictness=Strictness.STRICT
    )


class TestHumanAssistedAmbiguityResolverInit:
    """Test HumanAssistedAmbiguityResolver initialization."""

    def test_init_with_defaults(self, mock_browser_adapter, mock_cache):
        """Test basic initialization with default max_display."""
        resolver = HumanAssistedAmbiguityResolver(mock_browser_adapter, mock_cache)

        assert resolver.browser == mock_browser_adapter
        assert resolver.cache == mock_cache
        assert resolver.max_display == 100

    def test_init_with_custom_max_display(self, mock_browser_adapter, mock_cache):
        """Test initialization with custom max_display."""
        resolver = HumanAssistedAmbiguityResolver(mock_browser_adapter, mock_cache, max_display=5)

        assert resolver.max_display == 5


@pytest.mark.asyncio
class TestHumanAssistedAmbiguityResolverResolveAmbiguity:
    """Test HumanAssistedAmbiguityResolver resolve_ambiguity method."""

    async def test_resolve_ambiguity_with_user_selection(
        self, mock_browser_adapter, mock_cache, single_element_intent
    ):
        """Test successful user selection."""
        mock_browser_adapter.execute_script.side_effect = [
            "<button>Button 1</button>",  # outer HTML
            "//button[1]",  # xpath
            "top left",  # location
            "<button>Button 2</button>",  # outer HTML
            "//button[2]",  # xpath
            "top right",  # location
            "#btn-1",  # generated selector for caching
        ]

        resolver = HumanAssistedAmbiguityResolver(mock_browser_adapter, mock_cache)
        element1 = Mock()
        element2 = Mock()
        elements = [element1, element2]

        with patch('builtins.input', return_value='1'):
            with patch('builtins.print'):
                result = await resolver.resolve_ambiguity(
                    description="login button",
                    elements=elements,
                    intent=single_element_intent,
                    page_url="http://example.com"
                )

        assert result == [element1]
        mock_cache.set.assert_called_once()

    async def test_resolve_ambiguity_with_user_cancellation(
        self, mock_browser_adapter, mock_cache, single_element_intent
    ):
        """Test user cancelling selection (choosing 0)."""
        mock_browser_adapter.execute_script.side_effect = [
            "<button>Button 1</button>",
            "//button[1]",
            "top left",
        ]

        resolver = HumanAssistedAmbiguityResolver(mock_browser_adapter, mock_cache)
        elements = [Mock()]

        with patch('builtins.input', return_value='0'):
            with patch('builtins.print'):
                result = await resolver.resolve_ambiguity(
                    description="login button",
                    elements=elements,
                    intent=single_element_intent,
                    page_url="http://example.com"
                )

        assert result is None

    async def test_resolve_ambiguity_with_invalid_and_then_valid_inputs(
        self, mock_browser_adapter, mock_cache, single_element_intent
    ):
        """Test handling of invalid (non-numeric) input."""
        mock_browser_adapter.execute_script.side_effect = [
            "<button>Button 1</button>",
            "//button[1]",
            "top left",
        ]

        resolver = HumanAssistedAmbiguityResolver(mock_browser_adapter, mock_cache)
        elements = [Mock()]

        with patch('builtins.input', side_effect=['abc', '1']):
            with patch('builtins.print'):
                result = await resolver.resolve_ambiguity(
                    description="login button",
                    elements=elements,
                    intent=single_element_intent,
                    page_url="http://example.com"
                )

        assert result == [elements[0]]

    async def test_resolve_ambiguity_with_out_of_range_selection_then_valid_input(
        self, mock_browser_adapter, mock_cache, single_element_intent
    ):
        """Test handling of out-of-range selection."""
        mock_browser_adapter.execute_script.side_effect = [
            "<button>Button 1</button>",
            "//button[1]",
            "top left",
        ]

        resolver = HumanAssistedAmbiguityResolver(mock_browser_adapter, mock_cache)
        elements = [Mock()]

        with patch('builtins.input', side_effect=['5', '1']):
            with patch('builtins.print'):
                result = await resolver.resolve_ambiguity(
                    description="login button",
                    elements=elements,
                    intent=single_element_intent,
                    page_url="http://example.com"
                )

        assert result == [elements[0]]


@pytest.mark.asyncio
class TestHumanAssistedAmbiguityResolverHelpers:
    """Test helper methods."""

    async def test_get_outer_html(self, mock_browser_adapter, mock_cache):
        """Test getting element outer HTML."""
        mock_browser_adapter.execute_script.return_value = "<button>Click me</button>"

        resolver = HumanAssistedAmbiguityResolver(mock_browser_adapter, mock_cache)
        element = Mock()

        html = await resolver._get_outer_html(element)

        assert html == "<button>Click me</button>"

    async def test_get_outer_html_returns_unknown_on_error(self, mock_browser_adapter, mock_cache):
        """Test that _get_outer_html returns '<unknown>' on exception."""
        mock_browser_adapter.execute_script.side_effect = Exception("Script error")

        resolver = HumanAssistedAmbiguityResolver(mock_browser_adapter, mock_cache)
        element = Mock()

        html = await resolver._get_outer_html(element)

        assert html == "<unknown>"

    async def test_get_xpath(self, mock_browser_adapter, mock_cache):
        """Test generating XPath for element."""
        mock_browser_adapter.execute_script.return_value = "//div[@id='content']/button[1]"

        resolver = HumanAssistedAmbiguityResolver(mock_browser_adapter, mock_cache)
        element = Mock()

        xpath = await resolver._get_xpath(element)

        assert xpath.startswith("//")

    async def test_get_visual_location(self, mock_browser_adapter, mock_cache):
        """Test getting visual location of element."""
        mock_browser_adapter.execute_script.return_value = "top left"

        resolver = HumanAssistedAmbiguityResolver(mock_browser_adapter, mock_cache)
        element = Mock()

        location = await resolver._get_visual_location(element)

        assert location == "top left"

    def test_truncate_html_short_string(self, mock_browser_adapter, mock_cache):
        """Test truncation with short HTML."""
        resolver = HumanAssistedAmbiguityResolver(mock_browser_adapter, mock_cache)

        html = "<button>OK</button>"
        truncated = resolver._truncate_html(html, max_length=50)

        assert truncated == html

    def test_truncate_html_long_string(self, mock_browser_adapter, mock_cache):
        """Test truncation with long HTML."""
        resolver = HumanAssistedAmbiguityResolver(mock_browser_adapter, mock_cache)

        long_html = "a" * 200
        truncated = resolver._truncate_html(long_html, max_length=50)

        assert len(truncated) == 53  # 50 + "..."
        assert truncated.endswith("...")
