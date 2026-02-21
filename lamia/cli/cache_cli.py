"""CLI tool for managing Lamia selector resolution cache."""

import argparse
import json
import os
import sys
from typing import Optional
from datetime import datetime

from lamia.engine.config_provider import ConfigProvider

class CacheCLI:
    """Command-line interface for cache management."""
    
    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize cache CLI.
        
        Args:
            cache_dir: Directory containing cache files
        """
        self.cache_dir = cache_dir if cache_dir else ConfigProvider({}).get_cache_dir()
        self.cache_file = os.path.join(cache_dir, 'selectors', 'selector_resolutions.json')
    
    def _load_cache(self) -> dict:
        """Load cache from file."""
        if not os.path.exists(self.cache_file):
            return {}
        
        try:
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"Error loading cache: {e}", file=sys.stderr)
            return {}
    
    def _save_cache(self, cache_data: dict) -> None:
        """Save cache to file."""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
        except (OSError, IOError) as e:
            print(f"Error saving cache: {e}", file=sys.stderr)
            sys.exit(1)
    
    def list_cache(self, url_filter: Optional[str] = None, description_filter: Optional[str] = None) -> None:
        """List all cached selectors.
        
        Args:
            url_filter: Optional URL to filter by
            description_filter: Optional description to filter by
        """
        cache_data = self._load_cache()
        
        if not cache_data:
            print("Cache is empty")
            return
        
        # Filter entries
        filtered_entries = []
        for key, selector in cache_data.items():
            parts = key.split('|', 1)
            if len(parts) != 2:
                continue
            
            description, url = parts
            
            # Apply filters
            if url_filter and url_filter not in url:
                continue
            if description_filter and description_filter not in description:
                continue
            
            filtered_entries.append((description, url, selector))
        
        if not filtered_entries:
            print("No matching cache entries found")
            return
        
        # Display
        print(f"\n{'='*80}")
        print(f"Cached Selector Resolutions ({len(filtered_entries)} entries)")
        if url_filter:
            print(f"Filtered by URL: {url_filter}")
        if description_filter:
            print(f"Filtered by description: {description_filter}")
        print(f"{'='*80}\n")
        
        for i, (description, url, selector) in enumerate(filtered_entries, 1):
            print(f"{i}. Description: \"{description}\"")
            print(f"   URL: {url}")
            print(f"   Resolved to: {selector}")
            print()
    
    def clear_cache(
        self, 
        description: Optional[str] = None, 
        url: Optional[str] = None,
        all_entries: bool = False
    ) -> None:
        """Clear cache entries.
        
        Args:
            description: Clear entries matching this description
            url: Clear entries matching this URL
            all_entries: Clear all cache entries
        """
        cache_data = self._load_cache()
        
        if not cache_data:
            print("Cache is already empty")
            return
        
        original_count = len(cache_data)
        
        if all_entries:
            # Clear everything
            self._save_cache({})
            print(f"✓ Cleared entire cache ({original_count} entries removed)")
            return
        
        # Filter and remove
        keys_to_remove = []
        for key in cache_data:
            parts = key.split('|', 1)
            if len(parts) != 2:
                continue
            
            desc, key_url = parts
            
            # Match description or URL
            if description and description in desc:
                keys_to_remove.append(key)
            elif url and url in key_url:
                keys_to_remove.append(key)
        
        if not keys_to_remove:
            print("No matching cache entries found")
            return
        
        # Remove entries
        for key in keys_to_remove:
            del cache_data[key]
        
        self._save_cache(cache_data)
        print(f"✓ Removed {len(keys_to_remove)} cache entries")
    
    def stats(self) -> None:
        """Show cache statistics."""
        cache_data = self._load_cache()
        
        if not cache_data:
            print("Cache is empty")
            return
        
        # Gather stats
        total_entries = len(cache_data)
        urls = set()
        descriptions = set()
        
        for key in cache_data:
            parts = key.split('|', 1)
            if len(parts) == 2:
                description, url = parts
                descriptions.add(description)
                urls.add(url)
        
        # File size
        file_size = 0
        if os.path.exists(self.cache_file):
            file_size = os.path.getsize(self.cache_file)
        
        # Display
        print(f"\n{'='*80}")
        print("Cache Statistics")
        print(f"{'='*80}\n")
        print(f"Total entries:        {total_entries}")
        print(f"Unique descriptions:  {len(descriptions)}")
        print(f"Unique URLs:          {len(urls)}")
        print(f"Cache file size:      {file_size:,} bytes ({file_size/1024:.1f} KB)")
        print(f"Cache location:       {self.cache_file}")
        print()
    
    def add_selector(
        self, 
        original_selector: str, 
        resolved_selector: str, 
        url: str,
        parent_context: Optional[str] = None
    ) -> None:
        """Add a selector resolution to the cache.
        
        Args:
            original_selector: The original selector that failed
            resolved_selector: The working selector to use instead
            url: URL where this resolution applies
            parent_context: Optional parent context for scoped cache
        """
        cache_data = self._load_cache()
        
        cache_key = f"{original_selector}|{url}"
        
        # Add to cache
        cache_data[cache_key] = resolved_selector
        
        self._save_cache(cache_data)
        
        context_info = f" (within context: {parent_context})" if parent_context else ""


def main():
    """Main entry point for lamia-cache CLI."""
    parser = argparse.ArgumentParser(
        description='Manage Lamia selector resolution cache',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all cached selectors
  lamia-cache list
  
  # List selectors for specific URL
  lamia-cache list --url linkedin.com
  
  # List selectors matching description
  lamia-cache list --description "submit button"
  
  # Clear specific description
  lamia-cache clear --description "submit button"
  
  # Clear all for a URL
  lamia-cache clear --url linkedin.com
  
  # Clear entire cache
  lamia-cache clear --all
  
  # Show cache statistics
  lamia-cache stats
  
  # Add a working selector to cache
  lamia-cache add "button[aria-label*='Easy Apply']" ".jobs-apply-button" "https://www.linkedin.com/jobs/"
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List cached selectors')
    list_parser.add_argument('--url', help='Filter by URL')
    list_parser.add_argument('--description', help='Filter by description')
    list_parser.add_argument('--cache-dir', default=DEFAULT_CACHE_DIR, help='Cache directory (default: .lamia_cache)')
    
    # Clear command
    clear_parser = subparsers.add_parser('clear', help='Clear cache entries')
    clear_parser.add_argument('--description', help='Clear entries matching description')
    clear_parser.add_argument('--url', help='Clear entries matching URL')
    clear_parser.add_argument('--all', action='store_true', help='Clear entire cache')
    clear_parser.add_argument('--cache-dir', default=DEFAULT_CACHE_DIR, help='Cache directory (default: .lamia_cache)')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show cache statistics')
    stats_parser.add_argument('--cache-dir', default=DEFAULT_CACHE_DIR, help='Cache directory (default: .lamia_cache)')
    
    # Add command
    add_parser = subparsers.add_parser('add', help='Add a selector resolution to cache')
    add_parser.add_argument('original', help='Original selector that failed')
    add_parser.add_argument('resolved', help='Working selector to use instead')
    add_parser.add_argument('url', help='URL where this resolution applies')
    add_parser.add_argument('--context', help='Optional parent context for scoped cache')
    add_parser.add_argument('--cache-dir', default=DEFAULT_CACHE_DIR, help='Cache directory (default: .lamia_cache)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Create CLI instance
    cli = CacheCLI(cache_dir=args.cache_dir)
    
    # Execute command
    if args.command == 'list':
        cli.list_cache(url_filter=args.url, description_filter=args.description)
    elif args.command == 'clear':
        if not (args.description or args.url or args.all):
            print("Error: Must specify --description, --url, or --all", file=sys.stderr)
            sys.exit(1)
        cli.clear_cache(description=args.description, url=args.url, all_entries=args.all)
    elif args.command == 'stats':
        cli.stats()
    elif args.command == 'add':
        cli.add_selector(
            original_selector=args.original,
            resolved_selector=args.resolved,
            url=args.url,
            parent_context=args.context
        )


if __name__ == '__main__':
    main()




