"""Orchestrator service for AI-powered selector resolution."""

import logging
from typing import Optional, Callable, Awaitable
from .selector_cache import SelectorCache
from .selector_parser import SelectorParser, SelectorType
from lamia.interpreter.commands import LLMCommand

logger = logging.getLogger(__name__)


class SelectorResolutionService:
    """Orchestrates AI-powered selector resolution with caching."""
    
    def __init__(self, llm_manager, get_page_html_func: Optional[Callable[[], Awaitable[str]]] = None, cache_enabled: bool = True):
        """Initialize the selector resolution service.
        
        Args:
            llm_manager: LLM manager for AI-powered selector resolution
            get_page_html_func: Function to get current page HTML (optional)
            cache_enabled: Whether to enable caching of resolved selectors
        """
        self.parser = SelectorParser()
        self.llm_manager = llm_manager
        self.get_page_html = get_page_html_func
        self.cache = SelectorCache(cache_enabled=cache_enabled)
        
    async def resolve_selector(self, selector: str, page_url: str, page_context: Optional[str] = None) -> str:
        """Resolve a selector using AI if needed, with caching.
        
        Args:
            selector: Original selector (valid, invalid, or natural language)
            page_url: Current page URL for caching
            page_context: Optional HTML content for natural language resolution
            
        Returns:
            A resolved CSS selector
            
        Raises:
            ValueError: If selector cannot be resolved or is empty
        """
        if not selector or not selector.strip():
            raise ValueError("Selector cannot be empty")
            
        original_selector = selector.strip()
        logger.info(f"Resolving selector: '{original_selector}'")
        
        # Classify the selector
        try:
            selector_type = self.parser.classify(original_selector)
            logger.debug(f"Classified selector as: {selector_type.value}")
        except ValueError as e:
            raise ValueError(f"Invalid selector: {e}")
        
        # If it's already valid, return as-is
        if selector_type in [SelectorType.VALID_CSS, SelectorType.VALID_XPATH]:
            logger.debug(f"Selector is already valid, returning as-is")
            return original_selector
        
        # Check cache for resolved version
        cached_result = await self.cache.get(original_selector, page_url)
        if cached_result:
            logger.info(f"Using cached resolution: '{original_selector}' → '{cached_result}'")
            return cached_result
        
        # Use AI to resolve the selector
        try:
            logger.info(f"Sending selector '{original_selector}' to AI for resolution")
            
            # Get current page HTML if not provided
            if page_context is None:
                page_context = await self.get_page_html()
            
            # Create prompt for LLM
            prompt = f"""You are a web automation expert. Given the following HTML page and a natural language description of an element, return only a valid CSS selector that would find that element.

HTML:
{page_context}

Natural language selector: "{original_selector}"

Return only the CSS selector, no explanation or extra text:"""

            # Use llm_manager to get resolved selector
            llm_command = LLMCommand(prompt=prompt)
            result = await self.llm_manager.execute(llm_command)
            resolved_selector = result.validated_text.strip()
            
            logger.info(f"AI resolved selector '{original_selector}' to '{resolved_selector}'")
            
            if not resolved_selector:
                raise ValueError("LLM returned empty selector")
                
        except Exception as e:
            logger.error(f"AI resolution failed for '{original_selector}': {e}")
            raise ValueError(f"Failed to resolve selector '{original_selector}': {e}")
        
        # Cache the resolution
        await self.cache.set(original_selector, page_url, resolved_selector)
        logger.info(f"Resolved and cached: '{original_selector}' → '{resolved_selector}'")
        
        return resolved_selector
    
    async def clear_cache(self) -> None:
        """Clear all cached selector resolutions."""
        self.cache.clear()
        logger.info("Cleared selector resolution cache")
    
    def get_cache_size(self) -> int:
        """Get number of cached selector resolutions.
        
        Returns:
            Number of cached entries
        """
        return self.cache.size()