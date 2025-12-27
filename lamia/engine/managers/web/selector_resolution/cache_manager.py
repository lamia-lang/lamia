"""User-facing cache management interface."""

import logging
from typing import Dict, Tuple
from .ai_selector_cache import AISelectorCache

logger = logging.getLogger(__name__)


class CacheManager:
    """
    User-facing interface for managing selector resolution cache.
    
    Accessible via web.cache in .hu scripts for easy cache management.
    """
    
    def __init__(self, cache: AISelectorCache):
        """Initialize the cache manager.
        
        Args:
            cache: Underlying AISelectorCache instance
        """
        self._cache = cache
    
    async def reset(self, description: str = None, url: str = None) -> int:
        """
        Reset cache entries.
        
        Args:
            description: Optional selector description to match (resets all if None)
            url: Optional URL to match (resets all if None)
            
        Returns:
            Number of entries removed
            
        Examples:
            # Reset specific description
            web.cache.reset("review button")
            
            # Reset specific URL
            web.cache.reset(url="https://linkedin.com/jobs")
            
            # Reset everything
            web.cache.reset()
        """
        if description is not None:
            count = await self._cache.reset_for_description(description)
            print(f"✓ Reset cache for description '{description}': {count} entries removed")
            return count
        
        elif url is not None:
            count = await self._cache.reset_for_url(url)
            print(f"✓ Reset cache for URL '{url}': {count} entries removed")
            return count
        
        else:
            count = await self._cache.reset_all()
            print(f"✓ Reset entire cache: {count} entries removed")
            return count
    
    async def show(self) -> None:
        """
        Display all cached selector resolutions.
        
        Example:
            web.cache.show()
        """
        entries = await self._cache.show()
        
        if not entries:
            print("Cache is empty")
            return
        
        print(f"\n{'='*70}")
        print(f"Cached Selector Resolutions ({len(entries)} entries)")
        print(f"{'='*70}\n")
        
        for i, (key, (description, url, selector)) in enumerate(entries.items(), 1):
            print(f"{i}. Description: \"{description}\"")
            print(f"   URL: {url}")
            print(f"   Resolved to: {selector}")
            print()
    
    async def size(self) -> int:
        """
        Get number of cached entries.
        
        Returns:
            Number of cached selector resolutions
            
        Example:
            count = web.cache.size()
            print(f"Cache has {count} entries")
        """
        return self._cache.size()
    
    async def clear(self) -> None:
        """
        Clear all cache entries (alias for reset()).
        
        Example:
            web.cache.clear()
        """
        count = await self.reset()
        return count


