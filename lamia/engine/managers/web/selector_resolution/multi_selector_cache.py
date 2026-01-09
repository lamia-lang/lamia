"""Multi-selector cache for handling conditional selectors like 'next or review button'."""

import logging
from typing import List, Dict, Any, Optional
import json
import hashlib

logger = logging.getLogger(__name__)


class MultiSelectorCache:
    """
    Cache that stores multiple working selectors for conditional descriptions.
    
    Instead of caching just one selector per description, stores all selectors 
    that have worked for that description across different page contexts.
    """
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def _make_cache_key(self, description: str, page_url: str = "unknown") -> str:
        """Create cache key from description and page URL."""
        # For conditional selectors, we want to cache per description, not per URL
        # since "next or review button" should work across different pages
        key_data = f"{description.lower().strip()}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def get_working_selectors(self, description: str, page_url: str = "unknown") -> List[str]:
        """Get all selectors that have worked for this description.
        
        Args:
            description: Natural language description
            page_url: Current page URL
            
        Returns:
            List of selectors that have worked before, ordered by success frequency
        """
        cache_key = self._make_cache_key(description, page_url)
        
        if cache_key not in self._cache:
            logger.debug(f"Cache miss for: '{description}'")
            return []
        
        cached_data = self._cache[cache_key]
        selectors_with_counts = cached_data.get('selectors', {})
        
        # Sort by success count (most successful first)
        sorted_selectors = sorted(
            selectors_with_counts.items(),
            key=lambda x: x[1]['success_count'],
            reverse=True
        )
        
        working_selectors = [selector for selector, _ in sorted_selectors]
        
        logger.info(f"Cache hit for '{description}': {len(working_selectors)} working selectors")
        return working_selectors
    
    async def add_working_selector(self, description: str, selector: str, page_url: str = "unknown") -> None:
        """Add a selector that worked for this description.
        
        Args:
            description: Natural language description
            selector: CSS/XPath selector that worked
            page_url: Page URL where it worked
        """
        cache_key = self._make_cache_key(description, page_url)
        
        if cache_key not in self._cache:
            self._cache[cache_key] = {
                'description': description,
                'selectors': {},
                'last_updated': None
            }
        
        cached_data = self._cache[cache_key]
        
        if selector not in cached_data['selectors']:
            cached_data['selectors'][selector] = {
                'success_count': 0,
                'pages': []
            }
        
        # Increment success count
        cached_data['selectors'][selector]['success_count'] += 1
        
        # Track pages where it worked (for debugging)
        if page_url not in cached_data['selectors'][selector]['pages']:
            cached_data['selectors'][selector]['pages'].append(page_url)
        
        cached_data['last_updated'] = self._get_timestamp()
        
        logger.info(f"Added working selector for '{description}': {selector} (success count: {cached_data['selectors'][selector]['success_count']})")
    
    async def remove_failed_selector(self, description: str, selector: str, page_url: str = "unknown") -> None:
        """Remove or downgrade a selector that failed.
        
        Args:
            description: Natural language description
            selector: CSS/XPath selector that failed
            page_url: Page URL where it failed
        """
        cache_key = self._make_cache_key(description, page_url)
        
        if cache_key not in self._cache:
            return
        
        cached_data = self._cache[cache_key]
        
        if selector in cached_data['selectors']:
            # Decrease success count, but don't remove completely
            # (might work on other pages)
            cached_data['selectors'][selector]['success_count'] = max(
                0, cached_data['selectors'][selector]['success_count'] - 1
            )
            
            # If success count reaches 0, remove the selector
            if cached_data['selectors'][selector]['success_count'] == 0:
                del cached_data['selectors'][selector]
                logger.info(f"Removed failed selector for '{description}': {selector}")
            else:
                logger.debug(f"Downgraded selector for '{description}': {selector}")
    
    def clear(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
        logger.info("Cleared multi-selector cache")
    
    def _get_timestamp(self) -> str:
        """Get current timestamp string."""
        import datetime
        return datetime.datetime.now().isoformat()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for debugging."""
        stats = {
            'total_descriptions': len(self._cache),
            'total_selectors': sum(len(data['selectors']) for data in self._cache.values()),
            'descriptions': {}
        }
        
        for cache_key, data in self._cache.items():
            description = data.get('description', 'unknown')
            stats['descriptions'][description] = {
                'selectors_count': len(data['selectors']),
                'selectors': list(data['selectors'].keys())
            }
        
        return stats