"""Cache for tracking permanently failed selectors to skip on subsequent runs."""

import os
import json
import logging
from typing import Set, Dict, Optional

logger = logging.getLogger(__name__)


class FailedSelectorCache:
    """Tracks selectors that permanently failed to avoid re-trying them.
    
    When a selector fails with a permanent error (DOM is stable but element
    not found), it's cached. On subsequent runs, cached selectors are skipped
    immediately instead of waiting for timeout.
    
    Cache is URL-scoped since the same selector may work on different pages.
    """
    
    def __init__(self, cache_enabled: bool = True, cache_dir_name: str = '.lamia_cache'):
        self.cache_enabled = cache_enabled
        self.cache_dir_name = cache_dir_name
        self.cache_file_name = 'failed_selectors.json'
        self._cache_data: Optional[Dict[str, Set[str]]] = None
    
    def is_known_failed(self, selector: str, page_url: str) -> bool:
        """Check if selector is known to fail on this page.
        
        Args:
            selector: CSS/XPath selector
            page_url: Current page URL
            
        Returns:
            True if selector previously failed permanently on this page
        """
        if not self.cache_enabled:
            return False
        
        cache_data = self._load_cache()
        url_key = self._normalize_url(page_url)
        failed_selectors = cache_data.get(url_key, set())
        
        is_failed = selector in failed_selectors
        if is_failed:
            logger.debug(f"Skipping known-failed selector '{selector}' on {url_key}")
        return is_failed
    
    def mark_failed(self, selector: str, page_url: str) -> None:
        """Mark a selector as permanently failed on this page.
        
        Args:
            selector: CSS/XPath selector that failed
            page_url: Current page URL
        """
        if not self.cache_enabled:
            return
        
        cache_data = self._load_cache()
        url_key = self._normalize_url(page_url)
        
        if url_key not in cache_data:
            cache_data[url_key] = set()
        
        cache_data[url_key].add(selector)
        self._save_cache(cache_data)
        logger.info(f"Cached failed selector '{selector}' for {url_key}")
    
    def clear_for_url(self, page_url: str) -> None:
        """Clear all failed selectors for a specific URL."""
        if not self.cache_enabled:
            return
        
        cache_data = self._load_cache()
        url_key = self._normalize_url(page_url)
        
        if url_key in cache_data:
            del cache_data[url_key]
            self._save_cache(cache_data)
            logger.info(f"Cleared failed selectors cache for {url_key}")
    
    def clear_all(self) -> None:
        """Clear entire failed selector cache."""
        self._cache_data = {}
        self._save_cache({})
        logger.info("Cleared all failed selectors cache")
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for cache key (strip query params, fragments)."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    def _get_cache_file_path(self) -> str:
        """Get path to the failed selector cache file."""
        cache_dir = os.path.join(os.getcwd(), self.cache_dir_name, 'selectors')
        return os.path.join(cache_dir, self.cache_file_name)
    
    def _load_cache(self) -> Dict[str, Set[str]]:
        """Load cache data from file."""
        if self._cache_data is not None:
            return self._cache_data
        
        cache_file_path = self._get_cache_file_path()
        try:
            if os.path.exists(cache_file_path):
                with open(cache_file_path, 'r') as f:
                    raw_data = json.load(f)
                    # Convert lists back to sets
                    self._cache_data = {k: set(v) for k, v in raw_data.items()}
            else:
                self._cache_data = {}
        except (OSError, IOError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load failed selector cache: {e}")
            self._cache_data = {}
        
        return self._cache_data
    
    def _save_cache(self, cache_data: Dict[str, Set[str]]) -> None:
        """Save cache data to file."""
        cache_file_path = self._get_cache_file_path()
        try:
            cache_dir = os.path.dirname(cache_file_path)
            os.makedirs(cache_dir, exist_ok=True)
            
            # Convert sets to lists for JSON serialization
            serializable = {k: list(v) for k, v in cache_data.items()}
            with open(cache_file_path, 'w') as f:
                json.dump(serializable, f, indent=2)
            
            self._cache_data = cache_data
        except (OSError, IOError) as e:
            logger.warning(f"Failed to save failed selector cache: {e}")