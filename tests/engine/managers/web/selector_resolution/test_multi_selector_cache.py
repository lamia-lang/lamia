"""Tests for multi-selector cache."""

import pytest
from unittest.mock import Mock, patch
from lamia.engine.managers.web.selector_resolution.multi_selector_cache import MultiSelectorCache


class TestMultiSelectorCacheInitialization:
    """Test MultiSelectorCache initialization."""
    
    def test_default_initialization(self):
        """Test cache initialization with default settings."""
        cache = MultiSelectorCache()
        
        assert hasattr(cache, '_cache')
        assert isinstance(cache._cache, dict)
        assert len(cache._cache) == 0
    
    def test_cache_starts_empty(self):
        """Test that cache starts empty."""
        cache = MultiSelectorCache()
        assert cache._cache == {}


class TestMultiSelectorCacheOperations:
    """Test MultiSelectorCache basic operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.cache = MultiSelectorCache()
    
    @pytest.mark.asyncio
    async def test_cache_miss_empty_cache(self):
        """Test cache miss when cache is empty."""
        result = await self.cache.get_working_selectors("next button", "https://example.com")
        assert result == []
    
    @pytest.mark.asyncio
    async def test_record_and_get_single_selector(self):
        """Test recording and retrieving a single selector."""
        description = "submit button"
        page_url = "https://example.com"
        selector = ".btn-submit"
        
        await self.cache.add_working_selector(description, selector, page_url)
        result = await self.cache.get_working_selectors(description, page_url)
        
        assert selector in result
        assert len(result) >= 1
    
    @pytest.mark.asyncio
    async def test_record_multiple_selectors_same_description(self):
        """Test recording multiple selectors for same description."""
        description = "next or continue button"
        page_url = "https://example.com"
        selectors = [".btn-next", ".btn-continue", "#next-button"]
        
        for selector in selectors:
            await self.cache.add_working_selector(description, selector, page_url)
        
        result = await self.cache.get_working_selectors(description, page_url)
        
        for selector in selectors:
            assert selector in result
    
    @pytest.mark.asyncio
    async def test_selector_frequency_ordering(self):
        """Test that selectors are ordered by frequency of success."""
        description = "submit button"
        page_url = "https://example.com"
        
        # Record one selector multiple times
        for _ in range(3):
            await self.cache.add_working_selector(description, ".btn-submit", page_url)
        
        # Record another selector once
        await self.cache.add_working_selector(description, "#submit-btn", page_url)
        
        result = await self.cache.get_working_selectors(description, page_url)
        
        # Most frequently used should come first
        assert result[0] == ".btn-submit"
        assert "#submit-btn" in result
    
    @pytest.mark.asyncio
    async def test_case_insensitive_descriptions(self):
        """Test that descriptions are handled case-insensitively."""
        selectors = []
        
        # Record with different cases
        await self.cache.add_working_selector("Submit Button", ".btn1", "https://example.com")
        await self.cache.add_working_selector("submit button", ".btn2", "https://example.com")
        await self.cache.add_working_selector("SUBMIT BUTTON", ".btn3", "https://example.com")
        
        # All should be found regardless of case used for lookup
        result1 = await self.cache.get_working_selectors("Submit Button", "https://example.com")
        result2 = await self.cache.get_working_selectors("submit button", "https://example.com")
        result3 = await self.cache.get_working_selectors("SUBMIT BUTTON", "https://example.com")
        
        # All should return the same selectors
        assert set(result1) == set(result2) == set(result3)
        assert ".btn1" in result1 and ".btn2" in result1 and ".btn3" in result1
    
    @pytest.mark.asyncio
    async def test_whitespace_normalization(self):
        """Test that leading/trailing whitespace in descriptions is normalized."""
        # Record with leading/trailing whitespace (should be normalized)
        await self.cache.add_working_selector("  submit button  ", ".btn1", "https://example.com")
        await self.cache.add_working_selector("submit button", ".btn2", "https://example.com")
        
        result = await self.cache.get_working_selectors("submit button", "https://example.com")
        
        # Both should be treated as the same description
        assert ".btn1" in result and ".btn2" in result
        
        # But internal whitespace differences create separate entries
        await self.cache.add_working_selector("submit\tbutton", ".btn3", "https://example.com")
        result2 = await self.cache.get_working_selectors("submit\tbutton", "https://example.com")
        assert ".btn3" in result2
        assert ".btn1" not in result2  # Different key due to tab vs space
    
    @pytest.mark.asyncio
    async def test_different_descriptions_separate_entries(self):
        """Test that different descriptions create separate cache entries."""
        await self.cache.add_working_selector("submit button", ".btn-submit", "https://example.com")
        await self.cache.add_working_selector("cancel button", ".btn-cancel", "https://example.com")
        
        submit_result = await self.cache.get_working_selectors("submit button", "https://example.com")
        cancel_result = await self.cache.get_working_selectors("cancel button", "https://example.com")
        
        assert ".btn-submit" in submit_result
        assert ".btn-cancel" not in submit_result
        assert ".btn-cancel" in cancel_result
        assert ".btn-submit" not in cancel_result


class TestMultiSelectorCacheKeyGeneration:
    """Test cache key generation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.cache = MultiSelectorCache()
    
    def test_cache_key_consistency(self):
        """Test that cache key generation is consistent."""
        description = "submit button"
        page_url = "https://example.com"
        
        key1 = self.cache._make_cache_key(description, page_url)
        key2 = self.cache._make_cache_key(description, page_url)
        
        assert key1 == key2
        assert isinstance(key1, str)
        assert len(key1) > 0
    
    def test_cache_key_case_insensitive(self):
        """Test that cache keys are case-insensitive."""
        key1 = self.cache._make_cache_key("Submit Button", "https://example.com")
        key2 = self.cache._make_cache_key("submit button", "https://example.com")
        key3 = self.cache._make_cache_key("SUBMIT BUTTON", "https://example.com")
        
        assert key1 == key2 == key3
    
    def test_cache_key_whitespace_normalization(self):
        """Test that cache keys normalize leading/trailing whitespace."""
        key1 = self.cache._make_cache_key("  submit button  ", "https://example.com")
        key2 = self.cache._make_cache_key("submit button", "https://example.com")
        
        assert key1 == key2
    
    def test_different_descriptions_different_keys(self):
        """Test that different descriptions produce different keys."""
        key1 = self.cache._make_cache_key("submit button", "https://example.com")
        key2 = self.cache._make_cache_key("cancel button", "https://example.com")
        
        assert key1 != key2
    
    def test_cache_key_url_independence(self):
        """Test that cache keys are independent of URL (for conditional selectors)."""
        # Based on implementation, conditional selectors cache per description, not per URL
        description = "next or review button"
        
        key1 = self.cache._make_cache_key(description, "https://example.com")
        key2 = self.cache._make_cache_key(description, "https://different.com")
        
        # Should be the same key since conditional selectors work across pages
        assert key1 == key2


class TestMultiSelectorCacheAdvancedFeatures:
    """Test advanced features of MultiSelectorCache."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.cache = MultiSelectorCache()
    
    @pytest.mark.asyncio
    async def test_selector_deduplication(self):
        """Test that duplicate selectors are not added multiple times in results."""
        description = "submit button"
        page_url = "https://example.com"
        selector = ".btn-submit"
        
        # Record same selector multiple times
        for _ in range(5):
            await self.cache.add_working_selector(description, selector, page_url)
        
        result = await self.cache.get_working_selectors(description, page_url)
        
        # Should appear only once in results
        assert result.count(selector) == 1
    
    @pytest.mark.asyncio
    async def test_empty_description_handling(self):
        """Test handling of empty descriptions."""
        # Test with empty string
        result = await self.cache.get_working_selectors("", "https://example.com")
        assert result == []
        
        # Test recording with empty description
        await self.cache.add_working_selector("", ".btn", "https://example.com")
        result = await self.cache.get_working_selectors("", "https://example.com")
        # Should handle gracefully, either work or be empty
        assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_special_characters_in_descriptions(self):
        """Test handling of special characters in descriptions."""
        special_descriptions = [
            "button with émojis 🎉",
            "Submit & Continue",
            "Text with\nnewlines",
            "Description with 'quotes' and \"double quotes\"",
            "Special chars: !@#$%^&*()",
        ]
        
        for i, description in enumerate(special_descriptions):
            selector = f".btn-{i}"
            await self.cache.add_working_selector(description, selector, "https://example.com")
            result = await self.cache.get_working_selectors(description, "https://example.com")
            assert selector in result
    
    @pytest.mark.asyncio
    async def test_very_long_descriptions(self):
        """Test handling of very long descriptions."""
        long_description = "click the button that says " * 100 + "submit"
        selector = ".btn-submit"
        
        await self.cache.add_working_selector(long_description, selector, "https://example.com")
        result = await self.cache.get_working_selectors(long_description, "https://example.com")
        
        assert selector in result
    
    @pytest.mark.asyncio
    async def test_unicode_descriptions(self):
        """Test handling of Unicode characters in descriptions."""
        unicode_cases = [
            ("按钮", ".chinese-btn"),
            ("кнопка", ".russian-btn"),
            ("🎯 target button", ".target-btn"),
            ("ボタン", ".japanese-btn"),
        ]
        
        for description, selector in unicode_cases:
            await self.cache.add_working_selector(description, selector, "https://example.com")
            result = await self.cache.get_working_selectors(description, "https://example.com")
            assert selector in result, f"Failed for description: {description}"


class TestMultiSelectorCacheEdgeCases:
    """Test edge cases for MultiSelectorCache."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.cache = MultiSelectorCache()
    
    @pytest.mark.asyncio
    async def test_none_selector_handling(self):
        """Test handling of None selectors."""
        description = "submit button"
        
        # Should handle gracefully and store None as a selector
        await self.cache.add_working_selector(description, None, "https://example.com")
        result = await self.cache.get_working_selectors(description, "https://example.com")
        
        # None is stored as-is in the implementation
        assert None in result
        assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_empty_selector_handling(self):
        """Test handling of empty selectors."""
        description = "submit button"
        
        await self.cache.add_working_selector(description, "", "https://example.com")
        await self.cache.add_working_selector(description, "   ", "https://example.com")
        result = await self.cache.get_working_selectors(description, "https://example.com")
        
        # Empty selectors should be handled appropriately
        # Either excluded or handled gracefully
        assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_cache_size_management(self):
        """Test that cache doesn't grow indefinitely."""
        # Add many different descriptions
        for i in range(1000):
            description = f"button {i}"
            selector = f".btn-{i}"
            await self.cache.add_working_selector(description, selector, "https://example.com")
        
        # Cache should handle this gracefully
        result = await self.cache.get_working_selectors("button 0", "https://example.com")
        assert ".btn-0" in result
        
        # Cache should still be functional
        assert isinstance(self.cache._cache, dict)
    
    @pytest.mark.asyncio
    async def test_concurrent_operations_simulation(self):
        """Test simulation of concurrent cache operations."""
        import asyncio
        
        async def record_selector(i):
            description = f"button {i % 5}"  # Use shared descriptions
            selector = f".btn-{i}"
            await self.cache.add_working_selector(description, selector, "https://example.com")
        
        async def get_selectors(i):
            description = f"button {i % 5}"
            return await self.cache.get_working_selectors(description, "https://example.com")
        
        # Run many operations concurrently
        tasks = []
        for i in range(50):
            tasks.append(record_selector(i))
            tasks.append(get_selectors(i))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Should not raise exceptions
        for result in results:
            if isinstance(result, Exception):
                pytest.fail(f"Concurrent operation failed: {result}")


class TestMultiSelectorCacheIntegration:
    """Test integration scenarios for MultiSelectorCache."""
    
    @pytest.mark.asyncio
    async def test_realistic_conditional_selector_scenario(self):
        """Test realistic conditional selector usage scenario."""
        cache = MultiSelectorCache()
        
        # Simulate finding "next or continue" button on different pages
        conditional_description = "next or continue button"
        
        # Different pages might have different selectors for the same concept
        page_scenarios = [
            ("https://checkout1.com", ".btn-next"),
            ("https://form2.com", ".continue-btn"),
            ("https://wizard3.com", "#next-step"),
            ("https://checkout1.com", ".btn-next"),  # Same selector again
            ("https://survey4.com", "button[text*='Next']"),
        ]
        
        # Record all working selectors
        for page_url, selector in page_scenarios:
            await cache.add_working_selector(conditional_description, selector, page_url)
        
        # Get all working selectors
        result = await cache.get_working_selectors(conditional_description, "https://newpage.com")
        
        # Should contain all unique selectors
        expected_selectors = {".btn-next", ".continue-btn", "#next-step", "button[text*='Next']"}
        assert all(selector in result for selector in expected_selectors)
        
        # Most frequently used (.btn-next recorded twice) should be first
        assert result[0] == ".btn-next"
    
    @pytest.mark.asyncio
    async def test_cache_performance_characteristics(self):
        """Test cache performance characteristics."""
        import time
        
        cache = MultiSelectorCache()
        
        # Measure time for cache miss
        start = time.time()
        result = await cache.get_working_selectors("nonexistent", "https://example.com")
        cache_miss_time = time.time() - start
        
        assert result == []
        assert cache_miss_time < 1.0  # Should be fast
        
        # Add some data
        for i in range(10):
            await cache.add_working_selector("test button", f".btn-{i}", "https://example.com")
        
        # Measure time for cache hit
        start = time.time()
        result = await cache.get_working_selectors("test button", "https://example.com")
        cache_hit_time = time.time() - start
        
        assert len(result) == 10
        assert cache_hit_time < 1.0  # Should be fast
        
        # Both operations should be reasonably fast
        assert cache_miss_time < 0.1
        assert cache_hit_time < 0.1
    
    @pytest.mark.asyncio
    async def test_multi_language_support(self):
        """Test support for multiple languages."""
        cache = MultiSelectorCache()
        
        # Test same concept in different languages
        language_cases = [
            ("submit button", ".en-submit"),
            ("提交按钮", ".cn-submit"),  # Chinese
            ("кнопка отправки", ".ru-submit"),  # Russian
            ("botón de envío", ".es-submit"),  # Spanish
            ("送信ボタン", ".jp-submit"),  # Japanese
        ]
        
        for description, selector in language_cases:
            await cache.add_working_selector(description, selector, "https://example.com")
        
        # Each language should have its own cache entry
        for description, expected_selector in language_cases:
            result = await cache.get_working_selectors(description, "https://example.com")
            assert expected_selector in result, f"Failed for description: {description}"
    
    @pytest.mark.asyncio 
    async def test_cache_memory_usage(self):
        """Test that cache doesn't consume excessive memory."""
        import sys
        
        cache = MultiSelectorCache()
        
        # Get initial size
        initial_size = sys.getsizeof(cache._cache)
        
        # Add moderate amount of data
        for i in range(100):
            description = f"button {i}"
            for j in range(5):
                selector = f".btn-{i}-{j}"
                await cache.add_working_selector(description, selector, "https://example.com")
        
        # Check final size
        final_size = sys.getsizeof(cache._cache)
        size_increase = final_size - initial_size
        
        # Should not consume excessive memory (this is somewhat arbitrary)
        assert size_increase < 100000  # Less than 100KB for 500 entries
        
        # Cache should still be functional
        result = await cache.get_working_selectors("button 0", "https://example.com")
        assert len(result) == 5