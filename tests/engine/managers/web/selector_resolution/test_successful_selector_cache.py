"""Tests for successful selector cache."""

import pytest
import os
import tempfile
import shutil
import json
from unittest.mock import Mock, patch
from lamia.engine.managers.web.selector_resolution.successful_selector_cache import SuccessfulSelectorCache


class TestSuccessfulSelectorCacheInitialization:
    """Test SuccessfulSelectorCache initialization."""
    
    def test_default_initialization(self):
        """Test cache initialization with default settings."""
        cache = SuccessfulSelectorCache()
        
        assert cache.cache_enabled is True
        assert cache.cache_dir_name == '.lamia_cache'
        assert cache.cache_file_name == 'successful_selectors.json'
        assert cache._cache_data == {}
        assert cache._loaded is False
    
    def test_initialization_with_custom_settings(self):
        """Test cache initialization with custom settings."""
        cache = SuccessfulSelectorCache(cache_enabled=False, cache_dir_name='custom_cache')
        
        assert cache.cache_enabled is False
        assert cache.cache_dir_name == 'custom_cache'
        assert cache.cache_file_name == 'successful_selectors.json'
        assert cache._cache_data == {}
        assert cache._loaded is False
    
    def test_disabled_cache_initialization(self):
        """Test cache initialization when disabled."""
        cache = SuccessfulSelectorCache(cache_enabled=False)
        
        assert cache.cache_enabled is False
        assert cache._cache_data == {}


class TestSuccessfulSelectorCacheBasicOperations:
    """Test SuccessfulSelectorCache basic operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.cache = SuccessfulSelectorCache(
            cache_enabled=True, 
            cache_dir_name=os.path.join(self.temp_dir, '.lamia_cache')
        )
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_cache_miss_empty_cache(self):
        """Test cache miss when cache is empty."""
        result = self.cache.get_cached_selector("submit_button", "https://example.com")
        assert result is None
    
    def test_cache_disabled_returns_none(self):
        """Test that disabled cache always returns None."""
        disabled_cache = SuccessfulSelectorCache(cache_enabled=False)
        result = disabled_cache.get_cached_selector("submit_button", "https://example.com")
        assert result is None
    
    def test_cache_and_retrieve_selector(self):
        """Test caching and retrieving a successful selector."""
        selector_key = "submit_button"
        url = "https://example.com"
        successful_selector = ".btn-submit"
        
        self.cache.cache_successful(selector_key, successful_selector, url)
        result = self.cache.get_cached_selector(selector_key, url)
        
        assert result == successful_selector
    
    def test_cache_different_urls_separate(self):
        """Test that different URLs create separate cache entries."""
        selector_key = "submit_button"
        url1 = "https://example.com"
        url2 = "https://different.com"
        selector1 = ".btn-submit"
        selector2 = "#submit-btn"
        
        self.cache.cache_successful(selector_key, selector1, url1)
        self.cache.cache_successful(selector_key, selector2, url2)
        
        result1 = self.cache.get_cached_selector(selector_key, url1)
        result2 = self.cache.get_cached_selector(selector_key, url2)
        
        assert result1 == selector1
        assert result2 == selector2
    
    def test_cache_different_selector_keys_separate(self):
        """Test that different selector keys create separate cache entries."""
        url = "https://example.com"
        key1 = "submit_button"
        key2 = "cancel_button"
        selector1 = ".btn-submit"
        selector2 = ".btn-cancel"
        
        self.cache.cache_successful(key1, selector1, url)
        self.cache.cache_successful(key2, selector2, url)
        
        result1 = self.cache.get_cached_selector(key1, url)
        result2 = self.cache.get_cached_selector(key2, url)
        
        assert result1 == selector1
        assert result2 == selector2
    
    def test_cache_overwrite_existing(self):
        """Test overwriting existing cache entry."""
        selector_key = "submit_button"
        url = "https://example.com"
        selector1 = ".btn-submit"
        selector2 = "#submit-button"
        
        self.cache.cache_successful(selector_key, selector1, url)
        self.cache.cache_successful(selector_key, selector2, url)
        
        result = self.cache.get_cached_selector(selector_key, url)
        assert result == selector2


class TestSuccessfulSelectorCacheUrlNormalization:
    """Test URL normalization functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.cache = SuccessfulSelectorCache()
    
    def test_url_normalization_removes_query_params(self):
        """Test that URL normalization removes query parameters."""
        url1 = "https://example.com/page?param=value"
        url2 = "https://example.com/page"
        
        normalized1 = self.cache._normalize_url(url1)
        normalized2 = self.cache._normalize_url(url2)
        
        assert normalized1 == normalized2
        assert normalized1 == "https://example.com/page"
    
    def test_url_normalization_removes_fragments(self):
        """Test that URL normalization removes fragments."""
        url1 = "https://example.com/page#section"
        url2 = "https://example.com/page"
        
        normalized1 = self.cache._normalize_url(url1)
        normalized2 = self.cache._normalize_url(url2)
        
        assert normalized1 == normalized2
        assert normalized1 == "https://example.com/page"
    
    def test_url_normalization_preserves_path(self):
        """Test that URL normalization preserves path."""
        url = "https://example.com/path/to/page?param=value#section"
        normalized = self.cache._normalize_url(url)
        
        assert normalized == "https://example.com/path/to/page"
    
    def test_url_normalization_different_schemes(self):
        """Test URL normalization with different schemes."""
        url1 = "http://example.com/page"
        url2 = "https://example.com/page"
        
        normalized1 = self.cache._normalize_url(url1)
        normalized2 = self.cache._normalize_url(url2)
        
        assert normalized1 != normalized2
        assert normalized1 == "http://example.com/page"
        assert normalized2 == "https://example.com/page"
    
    def test_cache_with_url_variations(self):
        """Test caching with URL variations that should normalize to the same key."""
        selector_key = "button"
        base_url = "https://example.com/page"
        url_with_params = "https://example.com/page?param=value"
        url_with_fragment = "https://example.com/page#section"
        selector = ".btn"
        
        # Cache with URL that has params
        self.cache.cache_successful(selector_key, selector, url_with_params)
        
        # Should be able to retrieve with base URL
        result1 = self.cache.get_cached_selector(selector_key, base_url)
        assert result1 == selector
        
        # Should be able to retrieve with URL that has fragment
        result2 = self.cache.get_cached_selector(selector_key, url_with_fragment)
        assert result2 == selector


class TestSuccessfulSelectorCacheInvalidation:
    """Test cache invalidation functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = SuccessfulSelectorCache(
            cache_enabled=True,
            cache_dir_name=os.path.join(self.temp_dir, '.lamia_cache')
        )
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_invalidate_cached_selector(self):
        """Test invalidating a cached selector."""
        selector_key = "submit_button"
        url = "https://example.com"
        selector = ".btn-submit"
        
        # Cache selector
        self.cache.cache_successful(selector_key, selector, url)
        assert self.cache.get_cached_selector(selector_key, url) == selector
        
        # Invalidate
        self.cache.invalidate(selector_key, url)
        assert self.cache.get_cached_selector(selector_key, url) is None
    
    def test_invalidate_nonexistent_selector(self):
        """Test invalidating a selector that doesn't exist."""
        # Should not raise error
        self.cache.invalidate("nonexistent", "https://example.com")
    
    def test_invalidate_with_disabled_cache(self):
        """Test invalidation with disabled cache."""
        disabled_cache = SuccessfulSelectorCache(cache_enabled=False)
        # Should not raise error
        disabled_cache.invalidate("test", "https://example.com")
    
    def test_invalidate_preserves_other_selectors(self):
        """Test that invalidation only removes the specific selector."""
        url = "https://example.com"
        key1 = "button1"
        key2 = "button2"
        selector1 = ".btn1"
        selector2 = ".btn2"
        
        # Cache two selectors
        self.cache.cache_successful(key1, selector1, url)
        self.cache.cache_successful(key2, selector2, url)
        
        # Invalidate one
        self.cache.invalidate(key1, url)
        
        # First should be gone, second should remain
        assert self.cache.get_cached_selector(key1, url) is None
        assert self.cache.get_cached_selector(key2, url) == selector2


class TestSuccessfulSelectorCacheClearOperations:
    """Test cache clearing operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = SuccessfulSelectorCache(
            cache_enabled=True,
            cache_dir_name=os.path.join(self.temp_dir, '.lamia_cache')
        )
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_clear_for_url(self):
        """Test clearing cache for a specific URL."""
        url1 = "https://example.com"
        url2 = "https://different.com"
        key = "button"
        selector1 = ".btn1"
        selector2 = ".btn2"
        
        # Cache selectors for different URLs
        self.cache.cache_successful(key, selector1, url1)
        self.cache.cache_successful(key, selector2, url2)
        
        # Clear for one URL
        self.cache.clear_for_url(url1)
        
        # First URL cache should be cleared, second should remain
        assert self.cache.get_cached_selector(key, url1) is None
        assert self.cache.get_cached_selector(key, url2) == selector2
    
    def test_clear_for_nonexistent_url(self):
        """Test clearing cache for URL that doesn't exist."""
        # Should not raise error
        self.cache.clear_for_url("https://nonexistent.com")
    
    def test_clear_all(self):
        """Test clearing entire cache."""
        url1 = "https://example.com"
        url2 = "https://different.com"
        key = "button"
        selector1 = ".btn1"
        selector2 = ".btn2"
        
        # Cache selectors for different URLs
        self.cache.cache_successful(key, selector1, url1)
        self.cache.cache_successful(key, selector2, url2)
        
        # Clear all
        self.cache.clear_all()
        
        # All should be cleared
        assert self.cache.get_cached_selector(key, url1) is None
        assert self.cache.get_cached_selector(key, url2) is None
        assert self.cache._cache_data == {}


class TestSuccessfulSelectorCacheFileOperations:
    """Test file operations for SuccessfulSelectorCache."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = os.path.join(self.temp_dir, '.lamia_cache')
        self.cache = SuccessfulSelectorCache(cache_enabled=True, cache_dir_name=self.cache_dir)
    
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
        
        # Cache a selector to trigger file creation
        self.cache.cache_successful("test", ".test", "https://example.com")
        
        # Directory should be created
        assert os.path.exists(cache_dir)
        assert os.path.exists(cache_file_path)
    
    def test_cache_persistence_across_instances(self):
        """Test that cache persists across different cache instances."""
        selector_key = "submit_button"
        url = "https://example.com"
        selector = ".btn-submit"
        
        # Cache with first instance
        self.cache.cache_successful(selector_key, selector, url)
        
        # Create new instance with same cache directory
        cache2 = SuccessfulSelectorCache(cache_enabled=True, cache_dir_name=self.cache_dir)
        
        # Should retrieve the value
        result = cache2.get_cached_selector(selector_key, url)
        assert result == selector
    
    def test_cache_file_corruption_handling(self):
        """Test handling of corrupted cache file."""
        # Create cache directory and corrupted file
        cache_dir = os.path.join(self.cache_dir, 'selectors')
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, 'successful_selectors.json')
        
        with open(cache_file, 'w') as f:
            f.write("invalid json content {")
        
        # Should handle gracefully and not crash
        result = self.cache.get_cached_selector("test", "https://example.com")
        assert result is None
        
        # Should be able to cache new values
        self.cache.cache_successful("test", ".test", "https://example.com")
    
    def test_lazy_loading(self):
        """Test that cache is loaded lazily."""
        # Initially not loaded
        assert not self.cache._loaded
        
        # First operation triggers loading
        self.cache.get_cached_selector("test", "https://example.com")
        assert self.cache._loaded
        
        # Subsequent operations don't reload
        with patch.object(self.cache, '_ensure_loaded') as mock_ensure:
            self.cache.get_cached_selector("test2", "https://example.com")
            mock_ensure.assert_called_once()


class TestSuccessfulSelectorCacheEdgeCases:
    """Test edge cases for SuccessfulSelectorCache."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.cache = SuccessfulSelectorCache(cache_enabled=True)
    
    def test_empty_selector_key(self):
        """Test caching with empty selector key."""
        url = "https://example.com"
        selector = ".test"
        
        # Should work (not rejected)
        self.cache.cache_successful("", selector, url)
        result = self.cache.get_cached_selector("", url)
        assert result == selector
    
    def test_empty_selector_value(self):
        """Test caching empty selector value."""
        key = "test"
        url = "https://example.com"
        
        # Should work (empty string is a valid selector)
        self.cache.cache_successful(key, "", url)
        result = self.cache.get_cached_selector(key, url)
        assert result == ""
    
    def test_special_characters_in_inputs(self):
        """Test caching with special characters in inputs."""
        special_cases = [
            ("button with émojis 🎉", ".emoji-btn", "https://example.com"),
            ("Submit & Continue", "#submit-continue", "https://test.com/form?param=value"),
            ("Text with\nnewlines", ".multiline-selector", "https://test.org"),
            ("Key with 'quotes' and \"double quotes\"", ".quoted-selector", "https://quotes.test"),
        ]
        
        for key, selector, url in special_cases:
            self.cache.cache_successful(key, selector, url)
            result = self.cache.get_cached_selector(key, url)
            assert result == selector, f"Failed for key: {key}"
    
    def test_very_long_inputs(self):
        """Test caching with very long inputs."""
        long_key = "selector " * 1000  # Very long key
        long_url = "https://example.com/" + "path/" * 100  # Very long URL
        selector = ".btn"
        
        # Should handle without error
        self.cache.cache_successful(long_key, selector, long_url)
        result = self.cache.get_cached_selector(long_key, long_url)
        assert result == selector
    
    def test_unicode_handling(self):
        """Test proper Unicode handling."""
        unicode_cases = [
            ("按钮", "https://中文.com", ".chinese-btn"),
            ("кнопка", "https://русский.ru", ".russian-btn"),
            ("🎯 target", "https://emoji.com", ".target-btn"),
        ]
        
        for key, url, selector in unicode_cases:
            self.cache.cache_successful(key, selector, url)
            result = self.cache.get_cached_selector(key, url)
            assert result == selector
    
    def test_disabled_cache_operations(self):
        """Test all operations with disabled cache."""
        disabled_cache = SuccessfulSelectorCache(cache_enabled=False)
        
        # All operations should work but not actually cache/retrieve anything
        assert disabled_cache.get_cached_selector("test", "https://example.com") is None
        
        # Should not raise errors
        disabled_cache.cache_successful("test", ".test", "https://example.com")
        disabled_cache.invalidate("test", "https://example.com")
        disabled_cache.clear_for_url("https://example.com")
        disabled_cache.clear_all()


class TestSuccessfulSelectorCacheIntegration:
    """Test integration scenarios for SuccessfulSelectorCache."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = SuccessfulSelectorCache(
            cache_enabled=True,
            cache_dir_name=os.path.join(self.temp_dir, '.lamia_cache')
        )
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_realistic_selector_optimization_workflow(self):
        """Test realistic selector optimization workflow."""
        # Simulate a form with submit button that gets optimized over time
        form_url = "https://app.com/signup"
        submit_key = "signup_submit"
        
        # Initial run - no cached selector
        assert self.cache.get_cached_selector(submit_key, form_url) is None
        
        # First success - cache the working selector
        working_selector = ".signup-form .btn-primary"
        self.cache.cache_successful(submit_key, working_selector, form_url)
        
        # Next run - should get cached selector immediately
        cached = self.cache.get_cached_selector(submit_key, form_url)
        assert cached == working_selector
        
        # Site update breaks the selector - invalidate cache
        self.cache.invalidate(submit_key, form_url)
        assert self.cache.get_cached_selector(submit_key, form_url) is None
        
        # Find new working selector and cache it
        new_selector = ".signup-container .submit-btn"
        self.cache.cache_successful(submit_key, new_selector, form_url)
        
        # Should now return the new selector
        assert self.cache.get_cached_selector(submit_key, form_url) == new_selector
    
    def test_multi_page_application_scenario(self):
        """Test caching across multiple pages of an application."""
        base_url = "https://app.com"
        pages = [
            f"{base_url}/login",
            f"{base_url}/dashboard",
            f"{base_url}/profile",
            f"{base_url}/settings"
        ]
        
        # Each page has a submit button but with different selector
        selectors = {
            f"{base_url}/login": ".login-form .submit",
            f"{base_url}/dashboard": "#dashboard-save",
            f"{base_url}/profile": ".profile-form .btn-save",
            f"{base_url}/settings": ".settings-panel .apply-btn"
        }
        
        # Cache successful selectors for each page
        for url in pages:
            key = "submit_button"
            selector = selectors[url]
            self.cache.cache_successful(key, selector, url)
        
        # Verify each page has its own cached selector
        for url in pages:
            cached = self.cache.get_cached_selector("submit_button", url)
            assert cached == selectors[url]
        
        # URL normalization should work across query params
        for url in pages:
            url_with_params = f"{url}?session=123&tab=active"
            cached = self.cache.get_cached_selector("submit_button", url_with_params)
            assert cached == selectors[url]
    
    def test_cache_performance_characteristics(self):
        """Test cache performance characteristics."""
        import time
        
        # Create large cache dataset
        for i in range(100):
            key = f"selector_{i}"
            url = f"https://page{i}.com"
            selector = f".btn-{i}"
            self.cache.cache_successful(key, selector, url)
        
        # Measure cache hit performance
        start = time.time()
        result = self.cache.get_cached_selector("selector_50", "https://page50.com")
        hit_time = time.time() - start
        
        assert result == ".btn-50"
        assert hit_time < 0.1  # Should be fast
        
        # Measure cache miss performance
        start = time.time()
        result = self.cache.get_cached_selector("nonexistent", "https://nonexistent.com")
        miss_time = time.time() - start
        
        assert result is None
        assert miss_time < 0.1  # Should also be fast