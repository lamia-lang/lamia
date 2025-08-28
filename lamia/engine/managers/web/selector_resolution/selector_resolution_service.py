"""Orchestrator service for AI-powered selector resolution."""

import logging
from typing import Optional, Callable, Awaitable
from .selector_cache import SelectorCache
from .selector_parser import SelectorParser, SelectorType
from lamia.interpreter.commands import LLMCommand

logger = logging.getLogger(__name__)


class SelectorResolutionService:
    """Orchestrates AI-powered selector resolution with caching."""
    
    def __init__(self, llm_manager, get_page_html_func: Optional[Callable[[], Awaitable[str]]] = None, get_browser_adapter_func: Optional[Callable[[], Awaitable]] = None, cache_enabled: bool = True):
        """Initialize the selector resolution service.
        
        Args:
            llm_manager: LLM manager for AI-powered selector resolution
            get_page_html_func: Function to get current page HTML (optional)
            get_browser_adapter_func: Function to get browser adapter for validation (optional)
            cache_enabled: Whether to enable caching of resolved selectors
        """
        self.parser = SelectorParser()
        self.llm_manager = llm_manager
        self.get_page_html = get_page_html_func
        self.get_browser_adapter = get_browser_adapter_func
        self.cache = SelectorCache(cache_enabled=cache_enabled)
        
    async def resolve_selector(self, selector: str, page_url: str, page_context: Optional[str] = None, operation_type: Optional[str] = None) -> str:
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
        logger.debug(f"Checking cache for selector: '{original_selector}' on URL: '{page_url}'")
        cached_result = await self.cache.get(original_selector, page_url)
        if cached_result:
            logger.info(f"Using cached resolution: '{original_selector}' → '{cached_result}'")
            return cached_result
        else:
            logger.debug(f"No cache hit for: '{original_selector}' on '{page_url}'")
        
        # Use AI to resolve the selector
        try:
            logger.info(f"Sending selector '{original_selector}' to AI for resolution")
            
            # Get current page HTML if not provided
            if page_context is None:
                page_context = await self.get_page_html()
            
            # Create operation-specific instructions
            operation_instructions = self._get_operation_instructions(operation_type)
            
            # Create prompt for LLM
            prompt = f"""You are a web automation expert. Given the following HTML page and a natural language description of an element, return a response in one of these formats:

{operation_instructions}

FORMAT 1 - Single match found:
Return only the CSS selector, no brackets or extra text.

FORMAT 2 - Multiple ambiguous matches found:
AMBIGUOUS
OPTION1: "exact_text_1" -> css_selector_1
OPTION2: "exact_text_2" -> css_selector_2
...

HTML:
{page_context}

Natural language selector: "{original_selector}"

Analyze the HTML and respond in the appropriate format above:"""

            # Use llm_manager to get resolved selector with validation
            llm_command = LLMCommand(prompt=prompt)
            
            # Create AI-resolved selector validator (only for natural language selectors)
            from .validators.ai_resolved_selector_validator import AIResolvedSelectorValidator
            browser_adapter = await self.get_browser_adapter()
            validator = AIResolvedSelectorValidator(browser_adapter)
            
            result = await self.llm_manager.execute(llm_command, validator=validator)
            response = result.validated_text.strip()
            
            if not response:
                raise ValueError("LLM returned empty response")
            
            # Parse response format
            resolved_selector = self._parse_ai_response(response, original_selector)
                
        except Exception as e:
            logger.error(f"AI resolution failed for '{original_selector}': {e}")
            raise ValueError(f"Failed to resolve selector '{original_selector}': {e}")
        
        # Cache the resolution
        logger.debug(f"Caching resolution: '{original_selector}' on '{page_url}' → '{resolved_selector}'")
        await self.cache.set(original_selector, page_url, resolved_selector)
        logger.info(f"Resolved and cached: '{original_selector}' → '{resolved_selector}'")
        
        return resolved_selector
    
    async def clear_cache(self) -> None:
        """Clear all cached selector resolutions."""
        self.cache.clear()
        logger.info("Cleared selector resolution cache")
    
    async def invalidate_cached_selector(self, original_selector: str, page_url: str) -> None:
        """Invalidate a specific cached selector when it fails.
        
        Args:
            original_selector: The original selector that failed
            page_url: URL of the page where selector failed
        """
        await self.cache.invalidate(original_selector, page_url)
    
    def get_cache_size(self) -> int:
        """Get number of cached selector resolutions.
        
        Returns:
            Number of cached entries
        """
        return self.cache.size()
    
    def _get_operation_instructions(self, operation_type: Optional[str]) -> str:
        """Get operation-specific instructions for the AI prompt.
        
        Args:
            operation_type: The browser operation type (click, type, etc.)
            
        Returns:
            Operation-specific instruction text
        """
        if operation_type == "click":
            return """OPERATION: You need to find a CLICKABLE element (button, link, clickable text, etc.).
Look for elements like:
- <button> tags
- <a> tags with href
- Elements with onclick handlers
- Clickable text or icons
- Submit buttons
- Navigation links"""
        elif operation_type == "type":
            return """OPERATION: You need to find an INPUT element where text can be typed.
Look for elements like:
- <input> tags (text, email, password, etc.)
- <textarea> tags
- Editable elements with contenteditable="true"
- Search boxes
- Form fields"""
        elif operation_type == "select":
            return """OPERATION: You need to find a SELECT dropdown element.
Look for elements like:
- <select> tags
- Dropdown menus
- Option lists"""
        elif operation_type == "hover":
            return """OPERATION: You need to find an element that can be hovered over.
Look for elements like:
- Menu items
- Buttons with hover effects
- Links
- Interactive elements"""
        else:
            return """OPERATION: Find the element that matches the description."""
    
    def _parse_ai_response(self, response: str, original_selector: str) -> str:
        """Parse AI response and handle ambiguity.
        
        Args:
            response: The AI response text
            original_selector: The original selector for error messages
            
        Returns:
            A single CSS selector
            
        Raises:
            ValueError: If response is ambiguous or invalid
        """
        lines = [line.strip() for line in response.split('\n') if line.strip()]
        
        if not lines:
            raise ValueError("Empty AI response")
        
        # Check if response indicates ambiguity
        if lines[0] == "AMBIGUOUS":
            options = []
            for line in lines[1:]:
                if ': "' in line and '" ->' in line:
                    # Parse: OPTION1: "exact text" -> selector
                    parts = line.split(': "', 1)
                    if len(parts) == 2:
                        text_and_selector = parts[1]
                        if '" ->' in text_and_selector:
                            text, selector = text_and_selector.split('" ->', 1)
                            options.append((text.strip(), selector.strip()))
            
            if len(options) > 1:
                suggestions = []
                for text, selector in options:
                    suggestions.append(f'if you want to click "{text}" use this text in your code "{text}"')
                
                suggestion_text = ", otherwise ".join(suggestions)
                logger.error(f"Multiple matches found for '{original_selector}': {suggestion_text}")
                raise ValueError(f"Ambiguous selector '{original_selector}'. Multiple options found: {suggestion_text}")
        
        # If not ambiguous, treat first line as the selector
        selector = lines[0]
        
        # Clean up common AI formatting issues
        if selector.startswith('[') and selector.endswith(']'):
            selector = selector[1:-1]  # Remove brackets
        
        return selector.strip()