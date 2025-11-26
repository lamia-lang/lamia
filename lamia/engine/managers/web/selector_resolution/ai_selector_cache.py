"""Filesystem cache for storing AI-resolved selectors."""

import os
import json
import logging
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)


class AISelectorCache:
    """Filesystem-based cache for AI-resolved selectors to avoid repeated LLM calls."""
    
    def __init__(self, cache_enabled: bool = True, cache_dir_name: str = '.lamia_cache'):
        """Initialize the cache.
        
        Args:
            cache_enabled: Whether caching is enabled
            cache_dir_name: Name of cache directory
        """
        self.cache_enabled = cache_enabled
        self.cache_dir_name = cache_dir_name
        self.cache_file_name = 'selector_resolutions.json'
        self._cache_data = None  # Lazy loaded
    
    async def get(self, original_selector: str, page_url: str) -> Optional[str]:
        """Get cached resolved selector.
        
        Args:
            original_selector: The original selector that was resolved
            page_url: URL of the page where selector was used
            
        Returns:
            Cached resolved selector or None if not found
        """
        if not self.cache_enabled:
            return None
            
        cache_data = self._load_cache()
        cache_key = self._create_cache_key(original_selector, page_url)
        
        resolved = cache_data.get(cache_key)
        if resolved:
            logger.debug(f"Cache hit for selector '{original_selector}' on {page_url}")
        else:
            logger.debug(f"Cache miss for selector '{original_selector}' on {page_url}")
            
        return resolved
    
    async def set(self, original_selector: str, page_url: str, resolved_selector: str) -> None:
        """Store resolved selector in cache.
        
        Args:
            original_selector: The original selector that was resolved
            page_url: URL of the page where selector was used
            resolved_selector: The AI-resolved selector
        """
        if not self.cache_enabled:
            return
            
        if not resolved_selector or not resolved_selector.strip():
            logger.warning(f"Not caching empty resolved selector for '{original_selector}'")
            return
            
        cache_data = self._load_cache()
        cache_key = self._create_cache_key(original_selector, page_url)
        cache_data[cache_key] = resolved_selector.strip()
        
        self._save_cache(cache_data)
        logger.info(f"Saved selector to cache: '{original_selector}' -> '{resolved_selector}' for {page_url}")
    
    def _create_cache_key(self, original_selector: str, page_url: str) -> str:
        """Create cache key from selector and URL.
        
        Args:
            original_selector: The original selector
            page_url: The page URL
            
        Returns:
            Cache key string
        """
        cache_key = f"{original_selector}|{page_url}"
        logger.debug(f"Created cache key: '{cache_key}'")
        return cache_key
    
    def _get_cache_file_path(self) -> str:
        """Get path to the selector cache file."""
        cache_dir = os.path.join(os.getcwd(), self.cache_dir_name, 'selectors')
        return os.path.join(cache_dir, self.cache_file_name)
    
    def _load_cache(self) -> Dict[str, str]:
        """Load cache data from file."""
        if self._cache_data is not None:
            return self._cache_data
            
        cache_file_path = self._get_cache_file_path()
        
        try:
            if os.path.exists(cache_file_path):
                with open(cache_file_path, 'r') as f:
                    self._cache_data = json.load(f)
            else:
                self._cache_data = {}
        except (OSError, IOError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load cache file {cache_file_path}: {e}")
            self._cache_data = {}
        
        return self._cache_data
    
    def _save_cache(self, cache_data: Dict[str, str]) -> None:
        """Save cache data to file."""
        cache_file_path = self._get_cache_file_path()
        
        try:
            cache_dir = os.path.dirname(cache_file_path)
            os.makedirs(cache_dir, exist_ok=True)
            
            with open(cache_file_path, 'w') as f:
                json.dump(cache_data, f, indent=2)
                
            self._cache_data = cache_data  # Update in-memory copy
            logger.info(f"Cache file saved to: {cache_file_path} with {len(cache_data)} entries")
        except (OSError, IOError) as e:
            logger.warning(f"Failed to save cache file {cache_file_path}: {e}")
    
    def clear(self) -> None:
        """Clear all cached entries."""
        if not self.cache_enabled:
            return
            
        cache_file_path = self._get_cache_file_path()
        cleared_count = 0
        
        if os.path.exists(cache_file_path):
            try:
                with open(cache_file_path, 'r') as f:
                    cache_data = json.load(f)
                    cleared_count = len(cache_data)
                    
                # Write empty cache
                self._save_cache({})
                logger.info(f"Cleared {cleared_count} cached selector resolutions")
            except (OSError, IOError, json.JSONDecodeError) as e:
                logger.warning(f"Failed to clear cache: {e}")
        
        self._cache_data = {}
    
    def size(self) -> int:
        """Get current cache size.
        
        Returns:
            Number of cached entries
        """
        if not self.cache_enabled:
            return 0
            
        cache_data = self._load_cache()
        return len(cache_data)
    
    async def invalidate(self, original_selector: str, page_url: str) -> None:
        """Invalidate a specific cached selector resolution.
        
        Args:
            original_selector: The original selector to invalidate
            page_url: URL of the page where selector was used
        """
        if not self.cache_enabled:
            return
            
        cache_data = self._load_cache()
        cache_key = self._create_cache_key(original_selector, page_url)
        
        if cache_key in cache_data:
            del cache_data[cache_key]
            self._save_cache(cache_data)
            logger.info(f"Invalidated cached selector: '{original_selector}' for {page_url}")
        else:
            logger.debug(f"No cached entry to invalidate for: '{original_selector}' on {page_url}")