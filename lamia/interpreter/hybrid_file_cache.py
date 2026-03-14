"""
Caching utility for hybrid syntax files (.lm -> .py).
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class HybridFileCache:
    """Manages file-based caching of transformed hybrid syntax files."""
    
    def __init__(self, cache_enabled: bool = True, cache_dir_name: str = '.lamia_cache'):
        self.cache_enabled = cache_enabled
        self.cache_dir_name = cache_dir_name
    
    def get_cache_path(self, hybrid_file_path: str) -> str:
        """Get the cached .py file path for a hybrid file."""
        file_dir = os.path.dirname(hybrid_file_path)
        file_name = os.path.splitext(os.path.basename(hybrid_file_path))[0]
        
        cache_dir = os.path.join(file_dir, self.cache_dir_name)
        if self.cache_enabled:
            os.makedirs(cache_dir, exist_ok=True)
        
        return os.path.join(cache_dir, f"{file_name}.py")
    
    def is_cache_valid(self, hybrid_file_path: str, cache_file_path: str) -> bool:
        """Check if cached file is newer than source file."""
        if not self.cache_enabled:
            return False
            
        if not os.path.exists(cache_file_path):
            return False
        
        try:
            source_mtime = os.path.getmtime(hybrid_file_path)
            cache_mtime = os.path.getmtime(cache_file_path)
            return cache_mtime > source_mtime
        except OSError:
            return False
    
    def read_from_cache(self, cache_file_path: str) -> Optional[str]:
        """Read transformed code from cache file."""
        if not self.cache_enabled:
            return None
            
        try:
            with open(cache_file_path, 'r') as f:
                logger.info(f"Using cached file: {cache_file_path}")
                return f.read()
        except (OSError, IOError):
            return None
    
    def write_to_cache(self, cache_file_path: str, transformed_code: str) -> bool:
        """Write transformed code to cache file."""
        if not self.cache_enabled:
            return False
            
        try:
            cache_dir = os.path.dirname(cache_file_path)
            os.makedirs(cache_dir, exist_ok=True)
            
            with open(cache_file_path, 'w') as f:
                f.write(transformed_code)
            
            logger.info(f"Cached transformed code: {cache_file_path}")
            return True
        except (OSError, IOError) as e:
            logger.warning(f"Failed to write cache file {cache_file_path}: {e}")
            return False