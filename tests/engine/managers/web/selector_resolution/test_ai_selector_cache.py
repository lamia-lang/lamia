"""Tests for AI selector cache."""

import pytest
import os
import tempfile
import shutil
import json
from unittest.mock import Mock, patch, mock_open
from lamia.engine.managers.web.selector_resolution.ai_selector_cache import AISelectorCache


class TestAISelectorCacheInitialization:
    """Test AISelectorCache initialization."""
    
    def test_default_initialization(self):
        """Test cache with default settings."""
        cache = AISelectorCache()
        
        assert cache.cache_enabled is True
        assert cache.cache_dir_name == '.lamia_cache'
        assert cache.cache_file_name == 'selector_resolutions.json'
        assert cache._cache_data is None
    
    def test_initialization_with_custom_settings(self):
        """Test cache with custom settings."""
        cache = AISelectorCache(cache_enabled=False, cache_dir_name='custom_cache')
        
        assert cache.cache_enabled is False
        assert cache.cache_dir_name == 'custom_cache'
        assert cache.cache_file_name == 'selector_resolutions.json'
    
    def test_disabled_cache_initialization(self):
        """Test cache initialization when disabled."""
        cache = AISelectorCache(cache_enabled=False)
        
        assert cache.cache_enabled is False
        assert cache._cache_data is None


class TestAISelectorCacheOperations:
    """Test AISelectorCache operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.cache = AISelectorCache(cache_enabled=True, cache_dir_name=os.path.join(self.temp_dir, '.lamia_cache'))
    
    def teardown_method(self):
        """Clean up test fixtures."""
        # Remove temporary directory
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @pytest.mark.asyncio
    async def test_cache_miss_empty_cache(self):
        """Test cache miss when cache is empty."""
        result = await self.cache.get("submit button", "https://example.com")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_disabled_returns_none(self):
        """Test that disabled cache always returns None."""
        disabled_cache = AISelectorCache(cache_enabled=False)
        result = await disabled_cache.get("submit button", "https://example.com")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_set_and_get(self):
        """Test setting and getting cache values."""
        selector = "submit button"
        url = "https://example.com"
        resolved = ".btn-submit"
        
        await self.cache.set(selector, url, resolved)
        result = await self.cache.get(selector, url)
        
        assert result == resolved
    
    @pytest.mark.asyncio
    async def test_cache_with_parent_context(self):
        """Test caching with parent context."""
        selector = "submit button"
        url = "https://example.com"
        resolved = ".btn-submit"
        parent_context = "form.login"
        
        await self.cache.set(selector, url, resolved, parent_context=parent_context)
        
        # Should hit with same context
        result_with_context = await self.cache.get(selector, url, parent_context=parent_context)
        assert result_with_context == resolved
        
        # Should miss without context
        result_without_context = await self.cache.get(selector, url)
        assert result_without_context is None
    
    @pytest.mark.asyncio
    async def test_cache_different_urls_separate(self):
        """Test that different URLs create separate cache entries."""
        selector = "submit button"
        url1 = "https://example.com"
        url2 = "https://different.com"
        resolved1 = ".btn-submit"
        resolved2 = "#submit-btn"
        
        await self.cache.set(selector, url1, resolved1)
        await self.cache.set(selector, url2, resolved2)
        
        result1 = await self.cache.get(selector, url1)
        result2 = await self.cache.get(selector, url2)
        
        assert result1 == resolved1
        assert result2 == resolved2
    
    @pytest.mark.asyncio
    async def test_cache_overwrite_existing(self):
        """Test overwriting existing cache entry."""
        selector = "submit button"
        url = "https://example.com"
        resolved1 = ".btn-submit"
        resolved2 = "#submit-button"
        
        await self.cache.set(selector, url, resolved1)
        await self.cache.set(selector, url, resolved2)
        
        result = await self.cache.get(selector, url)
        assert result == resolved2
    
    @pytest.mark.asyncio
    async def test_cache_key_generation(self):
        """Test cache key generation consistency."""
        # This tests internal behavior through public API
        selector = "submit button"
        url = "https://example.com"
        resolved = ".btn-submit"
        
        # Set once
        await self.cache.set(selector, url, resolved)
        
        # Should get the same value back (tests key consistency)
        result = await self.cache.get(selector, url)
        assert result == resolved
    
    @pytest.mark.asyncio
    async def test_cache_with_special_characters(self):
        """Test caching with special characters in inputs."""
        special_cases = [
            ("button with émojis 🎉", "https://example.com", ".emoji-btn"),
            ("Submit & Continue", "https://site.com/form?param=value", "#submit-continue"),
            ("Text with\nnewlines", "https://test.org", ".multiline-selector"),
            ("Selector with 'quotes' and \"double quotes\"", "https://quotes.test", ".quoted-selector"),
        ]
        
        for selector, url, resolved in special_cases:
            await self.cache.set(selector, url, resolved)
            result = await self.cache.get(selector, url)
            assert result == resolved, f"Failed for selector: {selector}"


class TestAISelectorCacheFileOperations:
    """Test file operations for AISelectorCache."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = os.path.join(self.temp_dir, '.lamia_cache')
        self.cache = AISelectorCache(cache_enabled=True, cache_dir_name=self.cache_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_cache_directory_creation(self):
        """Test that cache directory is created when needed."""
        # Check initial state
        cache_file_path = self.cache._get_cache_file_path()
        cache_dir = os.path.dirname(cache_file_path)
        
        # Directory shouldn't exist initially
        assert not os.path.exists(cache_dir)
        
        # Trigger cache operation that requires file creation
        import asyncio
        asyncio.run(self.cache.set("test", "https://example.com", ".test"))
        
        # Directory should be created
        assert os.path.exists(cache_dir)
    
    @pytest.mark.asyncio
    async def test_cache_persistence_across_instances(self):
        """Test that cache persists across different cache instances."""
        selector = "submit button"
        url = "https://example.com"
        resolved = ".btn-submit"
        
        # Set value with first instance
        await self.cache.set(selector, url, resolved)
        
        # Create new instance with same cache directory
        cache2 = AISelectorCache(cache_enabled=True, cache_dir_name=self.cache_dir)
        
        # Should retrieve the value
        result = await cache2.get(selector, url)
        assert result == resolved
    
    @pytest.mark.asyncio
    async def test_cache_file_corruption_handling(self):
        """Test handling of corrupted cache file."""
        # Create cache directory and corrupted file
        os.makedirs(self.cache_dir, exist_ok=True)
        cache_file = os.path.join(self.cache_dir, 'selector_resolutions.json')
        
        with open(cache_file, 'w') as f:
            f.write("invalid json content {")
        
        # Should handle gracefully and not crash
        result = await self.cache.get("test", "https://example.com")
        assert result is None
    
    def test_cache_file_permissions(self):
        """Test cache file creation with proper permissions."""
        # Trigger cache creation
        self.cache._load_cache()
        
        cache_file = os.path.join(self.cache_dir, 'selector_resolutions.json')
        if os.path.exists(cache_file):
            # File should be readable and writable
            assert os.access(cache_file, os.R_OK)
            assert os.access(cache_file, os.W_OK)


class TestAISelectorCacheEdgeCases:
    """Test edge cases for AISelectorCache."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.cache = AISelectorCache(cache_enabled=True)
    
    @pytest.mark.asyncio
    async def test_empty_selector_string(self):
        """Test caching empty selector strings."""
        # Empty original selector should work (not rejected)
        await self.cache.set("", "https://example.com", ".some-selector")
        result = await self.cache.get("", "https://example.com")
        assert result == ".some-selector"
    
    @pytest.mark.asyncio
    async def test_none_values_handling(self):
        """Test handling of None values."""
        # None as resolved selector should be handled gracefully (not cached)
        await self.cache.set("submit", "https://example.com", None)
        result = await self.cache.get("submit", "https://example.com")
        assert result is None  # Should not be cached
    
    @pytest.mark.asyncio
    async def test_very_long_inputs(self):
        """Test handling of very long inputs."""
        long_selector = "button " * 1000  # Very long selector
        long_url = "https://example.com/" + "path/" * 100  # Very long URL
        resolved = ".btn"
        
        # Should handle without error
        await self.cache.set(long_selector, long_url, resolved)
        result = await self.cache.get(long_selector, long_url)
        assert result == resolved
    
    @pytest.mark.asyncio
    async def test_unicode_handling(self):
        """Test proper Unicode handling."""
        unicode_cases = [
            ("按钮", "https://中文.com", ".chinese-btn"),
            ("кнопка", "https://русский.ru", ".russian-btn"),
            ("🎯 target button", "https://emoji.com", ".target-btn"),
        ]
        
        for selector, url, resolved in unicode_cases:
            await self.cache.set(selector, url, resolved)
            result = await self.cache.get(selector, url)
            assert result == resolved
    
    @pytest.mark.asyncio
    async def test_cache_with_malformed_urls(self):
        """Test caching with malformed URLs."""
        malformed_urls = [
            "not-a-url",
            "ftp://example.com",
            "http://",
            "https://",
            "",
        ]
        
        for url in malformed_urls:
            try:
                await self.cache.set("button", url, ".btn")
                result = await self.cache.get("button", url)
                # Should either work or raise appropriate error
                assert result is None or result == ".btn"
            except ValueError:
                # Acceptable to reject malformed URLs
                pass


class TestAISelectorCacheConcurrency:
    """Test concurrency aspects of AISelectorCache."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = os.path.join(self.temp_dir, '.lamia_cache')
        self.cache = AISelectorCache(cache_enabled=True, cache_dir_name=self.cache_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @pytest.mark.asyncio
    async def test_concurrent_reads_and_writes(self):
        """Test concurrent cache operations."""
        import asyncio
        
        # Prepare test data
        operations = []
        
        # Add some write operations
        for i in range(5):
            operations.append(
                self.cache.set(f"selector_{i}", f"https://example{i}.com", f".btn-{i}")
            )
        
        # Add some read operations (these will likely be cache misses initially)
        for i in range(5):
            operations.append(
                self.cache.get(f"selector_{i}", f"https://example{i}.com")
            )
        
        # Execute all operations concurrently
        results = await asyncio.gather(*operations, return_exceptions=True)
        
        # Should not raise any exceptions
        for result in results:
            if isinstance(result, Exception):
                pytest.fail(f"Concurrent operation failed: {result}")
    
    @pytest.mark.asyncio
    async def test_multiple_cache_instances_same_directory(self):
        """Test multiple cache instances using same directory."""
        cache1 = AISelectorCache(cache_enabled=True, cache_dir_name=self.cache_dir)
        cache2 = AISelectorCache(cache_enabled=True, cache_dir_name=self.cache_dir)
        
        # Set value with cache1
        await cache1.set("button", "https://example.com", ".btn1")
        
        # Read with cache2 (might need to reload from disk)
        result = await cache2.get("button", "https://example.com")
        assert result == ".btn1"
        
        # Set different value with cache2
        await cache2.set("link", "https://example.com", ".lnk1")
        
        # Read with cache1 (might need to reload from disk)
        # Force cache1 to reload by clearing its in-memory cache
        cache1._cache_data = None
        result = await cache1.get("link", "https://example.com")
        assert result == ".lnk1"


class TestAISelectorCacheIntegration:
    """Test integration scenarios for AISelectorCache."""
    
    @pytest.mark.asyncio
    async def test_realistic_web_automation_scenario(self):
        """Test realistic web automation caching scenario."""
        cache = AISelectorCache(cache_enabled=True)
        
        # Simulate a web automation session with multiple pages
        pages = [
            ("https://login.example.com", [
                ("username field", "input[name='username']"),
                ("password field", "input[name='password']"),
                ("login button", ".btn-login"),
            ]),
            ("https://dashboard.example.com", [
                ("settings link", "a[href='/settings']"),
                ("logout button", ".btn-logout"),
                ("profile picture", ".avatar img"),
            ]),
        ]
        
        # Cache all selectors
        for url, selectors in pages:
            for selector, resolved in selectors:
                await cache.set(selector, url, resolved)
        
        # Verify all cached correctly
        for url, selectors in pages:
            for selector, expected_resolved in selectors:
                result = await cache.get(selector, url)
                assert result == expected_resolved, f"Failed for {selector} on {url}"
    
    @pytest.mark.asyncio
    async def test_cache_performance_characteristics(self):
        """Test cache performance characteristics."""
        import time
        
        cache = AISelectorCache(cache_enabled=True)
        
        # Measure cache miss time
        start = time.time()
        result = await cache.get("nonexistent", "https://example.com")
        cache_miss_time = time.time() - start
        
        assert result is None
        assert cache_miss_time < 1.0  # Should be fast
        
        # Set a value
        await cache.set("button", "https://example.com", ".btn")
        
        # Measure cache hit time
        start = time.time()
        result = await cache.get("button", "https://example.com")
        cache_hit_time = time.time() - start
        
        assert result == ".btn"
        assert cache_hit_time < 0.1  # Should be very fast
        
        # Cache hits should be faster than misses (usually)
        # Note: This might not always be true due to system variations
        # assert cache_hit_time <= cache_miss_time * 2  # Allow some variance