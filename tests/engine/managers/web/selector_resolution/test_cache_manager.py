"""Tests for cache manager."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from lamia.engine.managers.web.selector_resolution.cache_manager import CacheManager
from lamia.engine.managers.web.selector_resolution.ai_selector_cache import AISelectorCache


class TestCacheManagerInitialization:
    """Test CacheManager initialization."""
    
    def test_initialization_with_cache(self):
        """Test cache manager initialization with AISelectorCache."""
        cache = Mock(spec=AISelectorCache)
        manager = CacheManager(cache)
        
        assert manager._cache == cache
    
    def test_initialization_with_none_cache(self):
        """Test cache manager initialization with None cache."""
        # Should work but will fail when used
        manager = CacheManager(None)
        assert manager._cache is None


class TestCacheManagerResetOperations:
    """Test CacheManager reset operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_cache = Mock(spec=AISelectorCache)
        self.manager = CacheManager(self.mock_cache)
    
    @pytest.mark.asyncio
    async def test_reset_by_description(self):
        """Test reset cache by description."""
        self.mock_cache.reset_for_description = AsyncMock(return_value=5)
        
        with patch('builtins.print') as mock_print:
            result = await self.manager.reset(description="submit button")
        
        assert result == 5
        self.mock_cache.reset_for_description.assert_called_once_with("submit button")
        mock_print.assert_called_once_with("✓ Reset cache for description 'submit button': 5 entries removed")
    
    @pytest.mark.asyncio
    async def test_reset_by_url(self):
        """Test reset cache by URL."""
        self.mock_cache.reset_for_url = AsyncMock(return_value=3)
        
        with patch('builtins.print') as mock_print:
            result = await self.manager.reset(url="https://example.com")
        
        assert result == 3
        self.mock_cache.reset_for_url.assert_called_once_with("https://example.com")
        mock_print.assert_called_once_with("✓ Reset cache for URL 'https://example.com': 3 entries removed")
    
    @pytest.mark.asyncio
    async def test_reset_all(self):
        """Test reset entire cache."""
        self.mock_cache.reset_all = AsyncMock(return_value=10)
        
        with patch('builtins.print') as mock_print:
            result = await self.manager.reset()
        
        assert result == 10
        self.mock_cache.reset_all.assert_called_once_with()
        mock_print.assert_called_once_with("✓ Reset entire cache: 10 entries removed")
    
    @pytest.mark.asyncio
    async def test_reset_with_both_description_and_url(self):
        """Test reset with both description and url (description takes precedence)."""
        self.mock_cache.reset_for_description = AsyncMock(return_value=2)
        
        with patch('builtins.print') as mock_print:
            result = await self.manager.reset(description="button", url="https://example.com")
        
        # Description takes precedence
        assert result == 2
        self.mock_cache.reset_for_description.assert_called_once_with("button")
        self.mock_cache.reset_for_url.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_reset_empty_description(self):
        """Test reset with empty description."""
        self.mock_cache.reset_for_description = AsyncMock(return_value=0)
        
        with patch('builtins.print') as mock_print:
            result = await self.manager.reset(description="")
        
        assert result == 0
        self.mock_cache.reset_for_description.assert_called_once_with("")
        mock_print.assert_called_once_with("✓ Reset cache for description '': 0 entries removed")
    
    @pytest.mark.asyncio
    async def test_reset_returns_zero_when_nothing_removed(self):
        """Test reset returns 0 when no entries are removed."""
        self.mock_cache.reset_all = AsyncMock(return_value=0)
        
        with patch('builtins.print') as mock_print:
            result = await self.manager.reset()
        
        assert result == 0
        mock_print.assert_called_once_with("✓ Reset entire cache: 0 entries removed")


class TestCacheManagerShowOperations:
    """Test CacheManager show operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_cache = Mock(spec=AISelectorCache)
        self.manager = CacheManager(self.mock_cache)
    
    @pytest.mark.asyncio
    async def test_show_empty_cache(self):
        """Test showing empty cache."""
        self.mock_cache.show = AsyncMock(return_value={})
        
        with patch('builtins.print') as mock_print:
            await self.manager.show()
        
        mock_print.assert_called_once_with("Cache is empty")
    
    @pytest.mark.asyncio
    async def test_show_cache_with_entries(self):
        """Test showing cache with entries."""
        mock_entries = {
            "key1": ("submit button", "https://example.com", ".btn-submit"),
            "key2": ("cancel link", "https://test.com", ".cancel-link"),
            "key3": ("search field", "https://search.com", "#search-input")
        }
        self.mock_cache.show = AsyncMock(return_value=mock_entries)
        
        with patch('builtins.print') as mock_print:
            await self.manager.show()
        
        # Should call print multiple times for the formatted output
        assert mock_print.call_count > 1
        
        # Check that the header is printed with correct count
        header_calls = [call for call in mock_print.call_args_list 
                       if "Cached Selector Resolutions (3 entries)" in str(call)]
        assert len(header_calls) == 1
        
        # Check that each entry details are printed
        entry_calls = [call for call in mock_print.call_args_list 
                      if "Description:" in str(call)]
        assert len(entry_calls) == 3
    
    @pytest.mark.asyncio
    async def test_show_single_entry(self):
        """Test showing cache with single entry."""
        mock_entries = {
            "key1": ("login button", "https://login.com", ".btn-login")
        }
        self.mock_cache.show = AsyncMock(return_value=mock_entries)
        
        with patch('builtins.print') as mock_print:
            await self.manager.show()
        
        # Verify proper formatting for single entry
        calls_text = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "login button" in calls_text
        assert "https://login.com" in calls_text
        assert ".btn-login" in calls_text
    
    @pytest.mark.asyncio
    async def test_show_with_special_characters(self):
        """Test showing cache entries with special characters."""
        mock_entries = {
            "key1": ("button with émojis 🎉", "https://test.com", ".emoji-btn"),
            "key2": ("Submit & Continue", "https://form.com", "#submit-continue")
        }
        self.mock_cache.show = AsyncMock(return_value=mock_entries)
        
        with patch('builtins.print') as mock_print:
            await self.manager.show()
        
        # Should handle special characters gracefully
        calls_text = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "émojis 🎉" in calls_text
        assert "Submit & Continue" in calls_text


class TestCacheManagerSizeOperations:
    """Test CacheManager size operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_cache = Mock(spec=AISelectorCache)
        self.manager = CacheManager(self.mock_cache)
    
    @pytest.mark.asyncio
    async def test_size_empty_cache(self):
        """Test size of empty cache."""
        self.mock_cache.size = Mock(return_value=0)
        
        result = await self.manager.size()
        
        assert result == 0
        self.mock_cache.size.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_size_with_entries(self):
        """Test size with cache entries."""
        self.mock_cache.size = Mock(return_value=15)
        
        result = await self.manager.size()
        
        assert result == 15
        self.mock_cache.size.assert_called_once()


class TestCacheManagerClearOperations:
    """Test CacheManager clear operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_cache = Mock(spec=AISelectorCache)
        self.manager = CacheManager(self.mock_cache)
    
    @pytest.mark.asyncio
    async def test_clear_calls_reset(self):
        """Test that clear calls reset internally."""
        self.mock_cache.reset_all = AsyncMock(return_value=7)
        
        with patch('builtins.print') as mock_print:
            result = await self.manager.clear()
        
        assert result == 7
        self.mock_cache.reset_all.assert_called_once()
        mock_print.assert_called_once_with("✓ Reset entire cache: 7 entries removed")
    
    @pytest.mark.asyncio
    async def test_clear_empty_cache(self):
        """Test clearing empty cache."""
        self.mock_cache.reset_all = AsyncMock(return_value=0)
        
        with patch('builtins.print') as mock_print:
            result = await self.manager.clear()
        
        assert result == 0
        mock_print.assert_called_once_with("✓ Reset entire cache: 0 entries removed")


class TestCacheManagerEdgeCases:
    """Test CacheManager edge cases."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_cache = Mock(spec=AISelectorCache)
        self.manager = CacheManager(self.mock_cache)
    
    @pytest.mark.asyncio
    async def test_operations_with_cache_exceptions(self):
        """Test operations when underlying cache raises exceptions."""
        self.mock_cache.reset_all = AsyncMock(side_effect=Exception("Cache error"))
        
        # Should propagate the exception
        with pytest.raises(Exception, match="Cache error"):
            await self.manager.reset()
    
    @pytest.mark.asyncio
    async def test_show_with_malformed_cache_data(self):
        """Test show with malformed cache data."""
        # Missing tuple element - this will cause ValueError
        mock_entries = {
            "key1": ("description only",),  # Missing URL and selector
        }
        self.mock_cache.show = AsyncMock(return_value=mock_entries)
        
        # Should raise ValueError due to tuple unpacking
        with pytest.raises(ValueError, match="not enough values to unpack"):
            await self.manager.show()
    
    @pytest.mark.asyncio
    async def test_operations_with_none_cache(self):
        """Test operations with None cache."""
        manager = CacheManager(None)
        
        # Should raise AttributeError when trying to call methods on None
        with pytest.raises(AttributeError):
            await manager.reset()
        
        with pytest.raises(AttributeError):
            await manager.show()
        
        with pytest.raises(AttributeError):
            await manager.size()


class TestCacheManagerIntegration:
    """Test CacheManager integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_realistic_cache_management_scenario(self):
        """Test realistic cache management workflow."""
        mock_cache = Mock(spec=AISelectorCache)
        manager = CacheManager(mock_cache)
        
        # Initial cache is empty
        mock_cache.size.return_value = 0
        size = await manager.size()
        assert size == 0
        
        # After some usage, cache has entries
        mock_cache.size.return_value = 5
        mock_cache.show.return_value = {
            "key1": ("submit", "https://form.com", ".submit"),
            "key2": ("cancel", "https://form.com", ".cancel"),
        }
        
        size = await manager.size()
        assert size == 5
        
        with patch('builtins.print'):
            await manager.show()
        
        # Reset specific entries
        mock_cache.reset_for_description.return_value = 2
        with patch('builtins.print'):
            count = await manager.reset(description="submit")
        assert count == 2
        
        # Clear all remaining
        mock_cache.reset_all.return_value = 3
        with patch('builtins.print'):
            count = await manager.clear()
        assert count == 3
    
    @pytest.mark.asyncio
    async def test_concurrent_operations_simulation(self):
        """Test simulation of concurrent cache manager operations."""
        import asyncio
        
        mock_cache = Mock(spec=AISelectorCache)
        manager = CacheManager(mock_cache)
        
        # Set up mock responses
        mock_cache.reset_for_description.return_value = 1
        mock_cache.reset_for_url.return_value = 1
        mock_cache.size.return_value = 10
        mock_cache.show.return_value = {}
        
        async def reset_desc():
            with patch('builtins.print'):
                return await manager.reset(description="test")
        
        async def reset_url():
            with patch('builtins.print'):
                return await manager.reset(url="https://test.com")
        
        async def get_size():
            return await manager.size()
        
        async def show_cache():
            with patch('builtins.print'):
                return await manager.show()
        
        # Run operations concurrently
        results = await asyncio.gather(
            reset_desc(), reset_url(), get_size(), show_cache(),
            return_exceptions=True
        )
        
        # Should not raise exceptions
        for result in results:
            assert not isinstance(result, Exception)
        
        # Verify expected results
        assert results[0] == 1  # reset_desc
        assert results[1] == 1  # reset_url
        assert results[2] == 10  # get_size
        assert results[3] is None  # show_cache returns None
    
    @pytest.mark.asyncio
    async def test_cache_manager_performance(self):
        """Test cache manager performance characteristics."""
        import time
        
        mock_cache = Mock(spec=AISelectorCache)
        manager = CacheManager(mock_cache)
        
        # Mock fast responses
        mock_cache.size.return_value = 100
        mock_cache.reset_all.return_value = 50
        mock_cache.show.return_value = {}
        
        # Measure operation times
        start = time.time()
        await manager.size()
        size_time = time.time() - start
        
        start = time.time()
        with patch('builtins.print'):
            await manager.reset()
        reset_time = time.time() - start
        
        start = time.time()
        with patch('builtins.print'):
            await manager.show()
        show_time = time.time() - start
        
        # Operations should be fast (mostly just delegation)
        assert size_time < 0.1
        assert reset_time < 0.1
        assert show_time < 0.1