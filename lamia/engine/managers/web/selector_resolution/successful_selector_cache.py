"""Cache for tracking successful selectors to optimize selector chain resolution."""

import os
import json
import logging
from typing import Dict, Optional
from urllib.parse import urlparse

# Type alias for cache structure: {url: {selector_chain_key: successful_selector}}
CacheData = Dict[str, Dict[str, str]]

logger = logging.getLogger(__name__)


class SuccessfulSelectorCache:
    """Caches successful selectors to skip directly to working ones on repeated runs.
    
    When a selector chain succeeds, the working selector is cached for that URL.
    On subsequent runs:
    1. Try the cached selector first
    2. If it works, done (fast path)
    3. If it fails, clear cache and try full chain again
    
    This is more efficient than caching failures because:
    - We only store one selector per URL (not a list of failures)
    - Fast path is O(1) - try cached selector directly
    - Cache invalidation is automatic when selector stops working
    """
    
    def __init__(self, cache_enabled: bool = True, cache_dir_name: str = '.lamia_cache'):
        self.cache_enabled = cache_enabled
        self.cache_dir_name = cache_dir_name
        self.cache_file_name = 'successful_selectors.json'
        self._cache_data: Dict[str, Dict[str, str]] = {}
        self._loaded = False
    
    def get_cached_selector(self, selector_chain_key: str, page_url: str) -> Optional[str]:
        """Get previously successful selector for this chain on this page.
        
        Args:
            selector_chain_key: Hash/key identifying the selector chain (e.g., first selector)
            page_url: Current page URL
            
        Returns:
            Cached successful selector, or None if not cached
        """
        if not self.cache_enabled:
            return None
        
        self._ensure_loaded()
        url_key = self._normalize_url(page_url)
        
        url_cache = self._cache_data.get(url_key, {})
        cached = url_cache.get(selector_chain_key)
        
        if cached:
            logger.debug(f"Cache hit: '{selector_chain_key}' -> '{cached}' on {url_key}")
        
        return cached
    
    def cache_successful(self, selector_chain_key: str, successful_selector: str, page_url: str) -> None:
        """Cache a selector that successfully found an element.
        
        Args:
            selector_chain_key: Hash/key identifying the selector chain
            successful_selector: The selector that worked
            page_url: Current page URL
        """
        if not self.cache_enabled:
            return
        
        self._ensure_loaded()
        url_key = self._normalize_url(page_url)
        
        if url_key not in self._cache_data:
            self._cache_data[url_key] = {}
        
        self._cache_data[url_key][selector_chain_key] = successful_selector
        self._save_cache()
        logger.info(f"Cached successful selector: '{selector_chain_key}' -> '{successful_selector}' for {url_key}")
    
    def invalidate(self, selector_chain_key: str, page_url: str) -> None:
        """Invalidate cached selector when it stops working.
        
        Args:
            selector_chain_key: Hash/key identifying the selector chain
            page_url: Current page URL
        """
        if not self.cache_enabled:
            return
        
        self._ensure_loaded()
        url_key = self._normalize_url(page_url)
        
        if url_key in self._cache_data and selector_chain_key in self._cache_data[url_key]:
            del self._cache_data[url_key][selector_chain_key]
            self._save_cache()
            logger.info(f"Invalidated cached selector for '{selector_chain_key}' on {url_key}")
    
    def clear_for_url(self, page_url: str) -> None:
        """Clear all cached selectors for a specific URL."""
        if not self.cache_enabled:
            return
        
        self._ensure_loaded()
        url_key = self._normalize_url(page_url)
        
        if url_key in self._cache_data:
            del self._cache_data[url_key]
            self._save_cache()
            logger.info(f"Cleared selector cache for {url_key}")
    
    def clear_all(self) -> None:
        """Clear entire selector cache."""
        self._cache_data = {}
        self._save_cache()
        logger.info("Cleared all selector cache")
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for cache key (strip query params, fragments)."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    def _get_cache_file_path(self) -> str:
        """Get path to the selector cache file."""
        cache_dir = os.path.join(os.getcwd(), self.cache_dir_name, 'selectors')
        return os.path.join(cache_dir, self.cache_file_name)
    
    def _ensure_loaded(self) -> None:
        """Load cache from disk if not already loaded (lazy loading, once only)."""
        if self._loaded:
            return
        
        cache_file_path = self._get_cache_file_path()
        try:
            if os.path.exists(cache_file_path):
                with open(cache_file_path, 'r') as f:
                    self._cache_data = json.load(f)
            else:
                self._cache_data = {}
        except (OSError, IOError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load selector cache: {e}")
            self._cache_data = {}
        
        self._loaded = True
    
    def _save_cache(self) -> None:
        """Save cache data to file."""
        if self._cache_data is None:
            return
        
        cache_file_path = self._get_cache_file_path()
        try:
            cache_dir = os.path.dirname(cache_file_path)
            os.makedirs(cache_dir, exist_ok=True)
            
            with open(cache_file_path, 'w') as f:
                json.dump(self._cache_data, f, indent=2)
        except (OSError, IOError) as e:
            logger.warning(f"Failed to save selector cache: {e}")

