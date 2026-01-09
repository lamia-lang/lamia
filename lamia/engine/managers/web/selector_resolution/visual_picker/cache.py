"""Visual selection caching for element picker."""

import logging
import json
import os
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class VisualSelectionCache:
    """
    Cache for visual element selections to avoid re-picking the same elements.
    
    Stores selections by (method_name, description, page_url) key.
    """
    
    def __init__(self, enabled: bool = True, cache_dir: Optional[str] = None):
        """Initialize the visual selection cache.
        
        Args:
            enabled: Whether caching is enabled
            cache_dir: Directory for cache files (defaults to .lamia_cache/visual_selections)
        """
        self.enabled = enabled
        
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            # Default to .lamia_cache/visual_selections in current working directory
            self.cache_dir = Path.cwd() / ".lamia_cache" / "visual_selections"
        
        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.cache_file = self.cache_dir / "visual_selections.json"
            self._load_cache()
        else:
            self.cache_data = {}
    
    def _load_cache(self) -> None:
        """Load cache from disk."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    self.cache_data = json.load(f)
                logger.debug(f"Loaded {len(self.cache_data)} visual selections from cache")
            else:
                self.cache_data = {}
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load visual selection cache: {e}")
            self.cache_data = {}
    
    def _save_cache(self) -> None:
        """Save cache to disk."""
        if not self.enabled:
            return
        
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache_data, f, indent=2)
            logger.debug("Visual selection cache saved to disk")
        except IOError as e:
            logger.warning(f"Failed to save visual selection cache: {e}")
    
    def _create_key(self, method_name: str, description: str, page_url: str) -> str:
        """Create cache key from method, description, and URL."""
        # Normalize URL (remove query params and fragments for more stable caching)
        from urllib.parse import urlparse
        parsed = urlparse(page_url)
        normalized_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        
        return f"{method_name}|{description}|{normalized_url}"
    
    async def get(self, method_name: str, description: str, page_url: str) -> Optional[Dict[str, Any]]:
        """Get cached visual selection.
        
        Args:
            method_name: Web method name (click, get_element, etc.)
            description: Natural language description
            page_url: Current page URL
            
        Returns:
            Cached selection data or None if not found
        """
        if not self.enabled:
            return None
        
        key = self._create_key(method_name, description, page_url)
        result = self.cache_data.get(key)
        
        if result:
            logger.debug(f"Visual selection cache hit: {method_name}('{description}')")
            return result
        
        logger.debug(f"Visual selection cache miss: {method_name}('{description}')")
        return None
    
    async def set(
        self, 
        method_name: str, 
        description: str, 
        page_url: str, 
        selection_data: Dict[str, Any]
    ) -> None:
        """Store visual selection in cache.
        
        Args:
            method_name: Web method name
            description: Natural language description
            page_url: Current page URL
            selection_data: Selection result data to cache
        """
        if not self.enabled:
            return
        
        key = self._create_key(method_name, description, page_url)
        
        # Add metadata
        cache_entry = {
            'method_name': method_name,
            'description': description,
            'page_url': page_url,
            'selection_data': selection_data,
            'cached_at': self._get_timestamp()
        }
        
        self.cache_data[key] = cache_entry
        self._save_cache()
        
        logger.info(f"Cached visual selection: {method_name}('{description}') on {page_url}")
    
    async def invalidate(self, method_name: str, description: str, page_url: str) -> bool:
        """Remove cached selection.
        
        Args:
            method_name: Web method name
            description: Natural language description  
            page_url: Current page URL
            
        Returns:
            True if cache entry was removed, False if not found
        """
        if not self.enabled:
            return False
        
        key = self._create_key(method_name, description, page_url)
        
        if key in self.cache_data:
            del self.cache_data[key]
            self._save_cache()
            logger.info(f"Invalidated visual selection cache: {method_name}('{description}')")
            return True
        
        return False
    
    async def invalidate_by_url(self, page_url: str) -> int:
        """Invalidate all cached selections for a specific URL.
        
        Args:
            page_url: Page URL to invalidate
            
        Returns:
            Number of cache entries removed
        """
        if not self.enabled:
            return 0
        
        # Normalize URL for comparison
        from urllib.parse import urlparse
        parsed = urlparse(page_url)
        normalized_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        
        keys_to_remove = []
        for key, entry in self.cache_data.items():
            if entry.get('page_url', '').startswith(normalized_url):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.cache_data[key]
        
        if keys_to_remove:
            self._save_cache()
            logger.info(f"Invalidated {len(keys_to_remove)} visual selections for URL: {page_url}")
        
        return len(keys_to_remove)
    
    def clear_all(self) -> int:
        """Clear all cached visual selections.
        
        Returns:
            Number of cache entries removed
        """
        if not self.enabled:
            return 0
        
        count = len(self.cache_data)
        self.cache_data.clear()
        self._save_cache()
        
        logger.info(f"Cleared all {count} visual selection cache entries")
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        if not self.enabled:
            return {'enabled': False}
        
        stats = {
            'enabled': True,
            'total_entries': len(self.cache_data),
            'cache_file': str(self.cache_file),
            'cache_size_bytes': self.cache_file.stat().st_size if self.cache_file.exists() else 0
        }
        
        # Count by method
        method_counts = {}
        url_counts = {}
        
        for entry in self.cache_data.values():
            method = entry.get('method_name', 'unknown')
            method_counts[method] = method_counts.get(method, 0) + 1
            
            url = entry.get('page_url', 'unknown')
            url_counts[url] = url_counts.get(url, 0) + 1
        
        stats['by_method'] = method_counts
        stats['by_url'] = url_counts
        
        return stats
    
    def list_entries(self, method_name: Optional[str] = None, page_url: Optional[str] = None) -> list:
        """List cache entries with optional filtering.
        
        Args:
            method_name: Optional method name filter
            page_url: Optional page URL filter
            
        Returns:
            List of cache entries matching filters
        """
        if not self.enabled:
            return []
        
        entries = []
        for key, entry in self.cache_data.items():
            # Apply filters
            if method_name and entry.get('method_name') != method_name:
                continue
            if page_url and not entry.get('page_url', '').startswith(page_url):
                continue
            
            entries.append({
                'key': key,
                'method_name': entry.get('method_name'),
                'description': entry.get('description'),
                'page_url': entry.get('page_url'),
                'cached_at': entry.get('cached_at'),
                'element_count': entry.get('selection_data', {}).get('element_count', 0)
            })
        
        return sorted(entries, key=lambda x: x.get('cached_at', ''), reverse=True)
    
    def _get_timestamp(self) -> str:
        """Get current timestamp string."""
        from datetime import datetime
        return datetime.now().isoformat()