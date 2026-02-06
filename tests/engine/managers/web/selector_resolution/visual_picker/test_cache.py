"""Tests for VisualSelectionCache."""

import pytest
import tempfile
import shutil
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock

from lamia.engine.managers.web.selector_resolution.visual_picker.cache import VisualSelectionCache
from lamia.engine.config_provider import ConfigProvider


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory."""
    cache_dir = tmp_path / "test_cache"
    cache_dir.mkdir()
    return str(cache_dir)


@pytest.fixture
def config_provider(temp_cache_dir):
    """Create config provider with cache enabled."""
    config = MagicMock(spec=ConfigProvider)
    config.is_cache_enabled = Mock(return_value=True)
    config.get_cache_dir = Mock(return_value=temp_cache_dir)
    return config


@pytest.fixture
def disabled_config_provider():
    """Create config provider with cache disabled."""
    config = MagicMock(spec=ConfigProvider)
    config.is_cache_enabled = Mock(return_value=False)
    config.get_cache_dir = Mock(return_value=".lamia_cache")
    return config


class TestVisualSelectionCacheInitialization:
    """Test VisualSelectionCache initialization."""

    def test_cache_initialization_with_config_provider(self, config_provider):
        """Test cache initialization with config provider."""
        cache = VisualSelectionCache(config_provider)

        assert cache.enabled is True
        assert cache.cache_dir is not None
        assert isinstance(cache.cache_dir, Path)

    def test_cache_initialization_disabled(self, disabled_config_provider):
        """Test cache initialization when disabled."""
        cache = VisualSelectionCache(disabled_config_provider)

        assert cache.enabled is False
        assert cache.cache_data == {}

    def test_cache_creates_directory_when_enabled(self, config_provider):
        """Test that cache creates directory when enabled."""
        cache = VisualSelectionCache(config_provider)

        assert cache.cache_dir.exists()
        assert cache.cache_dir.is_dir()


class TestVisualSelectionCacheOperations:
    """Test VisualSelectionCache cache operations."""

    @pytest.mark.asyncio
    async def test_get_cache_miss(self, config_provider):
        """Test getting cached selector when cache miss."""
        cache = VisualSelectionCache(config_provider)

        result = await cache.get(
            method_name="click",
            description="submit button",
            page_url="https://example.com/page"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get_cache_hit(self, config_provider):
        """Test caching and retrieving a selector."""
        cache = VisualSelectionCache(config_provider)

        selection_data = {
            "selector": "button#submit",
            "element_count": 1
        }

        await cache.set(
            method_name="click",
            description="submit button",
            page_url="https://example.com/page",
            selection_data=selection_data
        )

        result = await cache.get(
            method_name="click",
            description="submit button",
            page_url="https://example.com/page"
        )

        assert result is not None
        assert result["selection_data"]["selector"] == "button#submit"
        assert result["method_name"] == "click"
        assert result["description"] == "submit button"
        assert result["page_url"] == "https://example.com/page"
        assert "cached_at" in result

    @pytest.mark.asyncio
    async def test_get_normalizes_url(self, config_provider):
        """Test that cache key normalizes URL by removing query params."""
        cache = VisualSelectionCache(config_provider)

        selection_data = {"selector": "button#submit", "element_count": 1}

        await cache.set(
            method_name="click",
            description="submit button",
            page_url="https://example.com/page?param=value#fragment",
            selection_data=selection_data
        )

        result = await cache.get(
            method_name="click",
            description="submit button",
            page_url="https://example.com/page?other=value"
        )

        assert result is not None
        assert result["selection_data"]["selector"] == "button#submit"


    @pytest.mark.asyncio
    async def test_cache_hit_on_not_matching_urls(self, config_provider):
        """Test that cache key normalizes URL by removing query params."""
        cache = VisualSelectionCache(config_provider)

        selection_data = {"selector": "button#submit", "element_count": 1}

        await cache.set(
            method_name="click",
            description="submit button",
            page_url="https://website.com/",
            selection_data=selection_data
        )

        result = await cache.get(
            method_name="click",
            description="submit button",
            page_url="https://another-website.com/"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_hit_on_another_action(self, config_provider):
        """Test that cache key normalizes URL by removing query params."""
        cache = VisualSelectionCache(config_provider)

        selection_data = {"selector": "button#submit", "element_count": 1}

        await cache.set(
            method_name="click",
            description="submit button",
            page_url="https://example.com/",
            selection_data=selection_data
        )

        result = await cache.get(
            method_name="another_action",
            description="submit button",
            page_url="https://example.com/"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_hit_on_another_selector(self, config_provider):
        """Test that cache key normalizes URL by removing query params."""
        cache = VisualSelectionCache(config_provider)

        selection_data = {"selector": "button#submit", "element_count": 1}

        await cache.set(
            method_name="click",
            description="submit button",
            page_url="https://example.com/",
            selection_data=selection_data
        )

        result = await cache.get(
            method_name="click",
            description="reset button",
            page_url="https://example.com/"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_invalidate_cache_entry(self, config_provider):
        """Test invalidating a specific cache entry."""
        cache = VisualSelectionCache(config_provider)

        selection_data = {"selector": "button#submit", "element_count": 1}
        await cache.set("click", "submit button", "https://example.com/page", selection_data)

        result = await cache.invalidate("click", "submit button", "https://example.com/page")
        assert result is True

        cached = await cache.get("click", "submit button", "https://example.com/page")
        assert cached is None

    @pytest.mark.asyncio
    async def test_invalidate_nonexistent_entry(self, config_provider):
        """Test invalidating a cache entry that doesn't exist."""
        cache = VisualSelectionCache(config_provider)

        result = await cache.invalidate("click", "nonexistent", "https://example.com/page")
        assert result is False

    @pytest.mark.asyncio
    async def test_invalidate_by_url(self, config_provider):
        """Test invalidating all cache entries for a URL."""
        cache = VisualSelectionCache(config_provider)

        await cache.set("click", "button1", "https://example.com/page", {"selector": "#btn1"})
        await cache.set("type_text", "input1", "https://example.com/page", {"selector": "#input1"})
        await cache.set("click", "button2", "https://other.com/page", {"selector": "#btn2"})

        count = await cache.invalidate_by_url("https://example.com/page")
        assert count == 2

        result1 = await cache.get("click", "button1", "https://example.com/page")
        result2 = await cache.get("click", "button2", "https://other.com/page")

        assert result1 is None
        assert result2 is not None

    @pytest.mark.asyncio
    async def test_invalidate_by_url_normalizes(self, config_provider):
        """Test that invalidate_by_url normalizes URL."""
        cache = VisualSelectionCache(config_provider)

        await cache.set("click", "button1", "https://example.com/page", {"selector": "#btn1"})
        await cache.set("click", "button2", "https://example.com/page?param=value", {"selector": "#btn2"})

        count = await cache.invalidate_by_url("https://example.com/page?other=value")
        assert count == 2

    @pytest.mark.asyncio
    async def test_clear_all_cache(self, config_provider):
        """Test clearing all cache entries."""
        cache = VisualSelectionCache(config_provider)

        await cache.set("click", "button1", "https://example.com/page1", {"selector": "#btn1"})
        await cache.set("click", "button2", "https://example.com/page2", {"selector": "#btn2"})

        count = cache.clear_all()
        assert count == 2

        result1 = await cache.get("click", "button1", "https://example.com/page1")
        result2 = await cache.get("click", "button2", "https://example.com/page2")

        assert result1 is None
        assert result2 is None

    @pytest.mark.asyncio
    async def test_cache_disabled_returns_none(self, disabled_config_provider):
        """Test that disabled cache always returns None."""
        cache = VisualSelectionCache(disabled_config_provider)

        await cache.set("click", "button", "https://example.com", {"selector": "#btn"})
        result = await cache.get("click", "button", "https://example.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_disabled_set_does_nothing(self, disabled_config_provider):
        """Test that disabled cache set does nothing."""
        cache = VisualSelectionCache(disabled_config_provider)

        await cache.set("click", "button", "https://example.com", {"selector": "#btn"})
        assert len(cache.cache_data) == 0

    @pytest.mark.asyncio
    async def test_cache_disabled_invalidate_returns_false(self, disabled_config_provider):
        """Test that disabled cache invalidate returns False."""
        cache = VisualSelectionCache(disabled_config_provider)

        result = await cache.invalidate("click", "button", "https://example.com")
        assert result is False

    @pytest.mark.asyncio
    async def test_cache_disabled_invalidate_by_url_returns_zero(self, disabled_config_provider):
        """Test that disabled cache invalidate_by_url returns 0."""
        cache = VisualSelectionCache(disabled_config_provider)

        count = await cache.invalidate_by_url("https://example.com")
        assert count == 0

    @pytest.mark.asyncio
    async def test_cache_disabled_clear_all_returns_zero(self, disabled_config_provider):
        """Test that disabled cache clear_all returns 0."""
        cache = VisualSelectionCache(disabled_config_provider)

        count = cache.clear_all()
        assert count == 0


class TestVisualSelectionCacheStatistics:
    """Test VisualSelectionCache statistics tracking."""

    def test_get_stats_empty(self, config_provider):
        """Test getting cache statistics when empty."""
        cache = VisualSelectionCache(config_provider)

        stats = cache.get_stats()

        assert stats["enabled"] is True
        assert stats["total_entries"] == 0
        assert "cache_file" in stats
        assert "cache_size_bytes" in stats

    @pytest.mark.asyncio
    async def test_get_stats_with_entries(self, config_provider):
        """Test getting cache statistics with entries."""
        cache = VisualSelectionCache(config_provider)

        await cache.set("click", "button1", "https://example.com/page1", {"selector": "#btn1"})
        await cache.set("type_text", "input1", "https://example.com/page1", {"selector": "#input1"})
        await cache.set("click", "button2", "https://example.com/page2", {"selector": "#btn2"})

        stats = cache.get_stats()

        assert stats["total_entries"] == 3
        assert "by_method" in stats
        assert stats["by_method"]["click"] == 2
        assert stats["by_method"]["type_text"] == 1
        assert "by_url" in stats
        assert len(stats["by_url"]) == 2

    def test_get_stats_disabled(self, disabled_config_provider):
        """Test getting cache statistics when disabled."""
        cache = VisualSelectionCache(disabled_config_provider)

        stats = cache.get_stats()

        assert stats["enabled"] is False


class TestVisualSelectionCacheListEntries:
    """Test VisualSelectionCache list_entries method."""

    @pytest.mark.asyncio
    async def test_list_entries_empty(self, config_provider):
        """Test listing entries when cache is empty."""
        cache = VisualSelectionCache(config_provider)

        entries = cache.list_entries()

        assert entries == []

    @pytest.mark.asyncio
    async def test_list_entries_all(self, config_provider):
        """Test listing all entries."""
        cache = VisualSelectionCache(config_provider)

        await cache.set("click", "button1", "https://example.com/page1", {"selector": "#btn1", "element_count": 1})
        await cache.set("type_text", "input1", "https://example.com/page1", {"selector": "#input1", "element_count": 1})
        await cache.set("click", "button2", "https://example.com/page2", {"selector": "#btn2", "element_count": 1})

        entries = cache.list_entries()

        assert len(entries) == 3
        assert all("key" in entry for entry in entries)
        assert all("method_name" in entry for entry in entries)
        assert all("description" in entry for entry in entries)
        assert all("page_url" in entry for entry in entries)

    @pytest.mark.asyncio
    async def test_list_entries_filter_by_method(self, config_provider):
        """Test listing entries filtered by method name."""
        cache = VisualSelectionCache(config_provider)

        await cache.set("click", "button1", "https://example.com/page1", {"selector": "#btn1"})
        await cache.set("type_text", "input1", "https://example.com/page1", {"selector": "#input1"})
        await cache.set("click", "button2", "https://example.com/page2", {"selector": "#btn2"})

        entries = cache.list_entries(method_name="click")

        assert len(entries) == 2
        assert all(entry["method_name"] == "click" for entry in entries)

    @pytest.mark.asyncio
    async def test_list_entries_filter_by_url(self, config_provider):
        """Test listing entries filtered by page URL."""
        cache = VisualSelectionCache(config_provider)

        await cache.set("click", "button1", "https://example.com/page1", {"selector": "#btn1"})
        await cache.set("click", "button2", "https://example.com/page2", {"selector": "#btn2"})
        await cache.set("click", "button3", "https://other.com/page", {"selector": "#btn3"})

        entries = cache.list_entries(page_url="https://example.com")

        assert len(entries) == 2
        assert all("example.com" in entry["page_url"] for entry in entries)

    @pytest.mark.asyncio
    async def test_list_entries_filter_by_both(self, config_provider):
        """Test listing entries filtered by both method and URL."""
        cache = VisualSelectionCache(config_provider)

        await cache.set("click", "button1", "https://example.com/page1", {"selector": "#btn1"})
        await cache.set("type_text", "input1", "https://example.com/page1", {"selector": "#input1"})
        await cache.set("click", "button2", "https://example.com/page2", {"selector": "#btn2"})

        entries = cache.list_entries(method_name="click", page_url="https://example.com/page1")

        assert len(entries) == 1
        assert entries[0]["method_name"] == "click"
        assert entries[0]["page_url"] == "https://example.com/page1"

    @pytest.mark.asyncio
    async def test_list_entries_disabled_returns_empty(self, disabled_config_provider):
        """Test that disabled cache list_entries returns empty list."""
        cache = VisualSelectionCache(disabled_config_provider)

        entries = cache.list_entries()

        assert entries == []
