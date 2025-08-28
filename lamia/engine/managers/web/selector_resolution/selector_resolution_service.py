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

CRITICAL RULE: You MUST check for ALL elements that could match the description. If there are 2 or more possible matches, you MUST use AMBIGUOUS format. Do NOT pick just one - always report ambiguity when multiple options exist.

FORMAT 1 - Single match found (ONLY if exactly one element matches):
Return only the CSS selector, no brackets or extra text.

FORMAT 2 - Multiple ambiguous matches found (REQUIRED when 2+ elements match):
AMBIGUOUS
OPTION1: "descriptive_text_1" -> css_selector_1
OPTION2: "descriptive_text_2" -> css_selector_2
...

IMPORTANT: For AMBIGUOUS format, make the option texts DISTINCTIVE and DESCRIPTIVE so users can tell them apart. Examples:
- Instead of: "Sign in" and "Sign in"
- Use: "Sign in (main form)" and "Sign in with Apple"
- Instead of: "Submit" and "Submit" 
- Use: "Submit form" and "Submit search"

Search Strategy:
1. First scan ALL buttons, links, and clickable elements
2. Check text content, aria-labels, and surrounding text
3. Count how many could reasonably match the description
4. If count >= 2, use AMBIGUOUS format immediately

HTML:
{page_context}

Natural language selector: "{original_selector}"

Step 1: Search for ALL elements containing words like "sign", "login", "signin", etc.
Step 2: Count potential matches for "{original_selector}"
Step 3: If 2+ matches found, return AMBIGUOUS format. If exactly 1 match, return selector.

Your response:"""

            # Use llm_manager to get raw response first (no validation yet)
            llm_command = LLMCommand(prompt=prompt)
            
            result = await self.llm_manager.execute(llm_command)
            response = result.validated_text.strip()
            
            if not response:
                raise ValueError("LLM returned empty response")
            
            # Parse response format first to check for ambiguity
            resolved_selector = self._parse_ai_response(response, original_selector)
            
            # Only validate if we got a single selector (not ambiguous)
            from .validators.ai_resolved_selector_validator import AIResolvedSelectorValidator
            browser_adapter = await self.get_browser_adapter()
            validator = AIResolvedSelectorValidator(browser_adapter)
            
            validation_result = await validator.validate_strict(resolved_selector)
            if not validation_result.is_valid:
                raise ValueError(f"AI-resolved selector validation failed: {validation_result.error_message}")
                
        except ValueError as e:
            # Check if this is an ambiguity error that should be surfaced to the user
            if "🚨 AMBIGUOUS SELECTOR:" in str(e):
                # This is a user-friendly ambiguity error - surface it prominently
                print(f"\n{str(e)}")  # Print to stdout so user sees it immediately
                logger.info(f"Ambiguous selector detected for '{original_selector}'")
                # Re-raise the ValueError as-is so the user gets the helpful suggestions
                raise e
            else:
                logger.error(f"AI resolution failed for '{original_selector}': {e}")
                raise ValueError(f"Failed to resolve selector '{original_selector}': {e}")
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
                # Format the error message to be very clear and actionable for the user
                error_lines = [
                    f"\n🚨 AMBIGUOUS SELECTOR: '{original_selector}'",
                    f"",
                    f"Multiple elements match your description. Please be more specific by using one of these exact texts:",
                    f""
                ]
                
                for i, (text, selector) in enumerate(options, 1):
                    # Try to make option more descriptive based on selector
                    descriptive_text = text
                    if "apple" in selector.lower():
                        descriptive_text = f"{text} (Apple Login)"
                    elif "google" in selector.lower():
                        descriptive_text = f"{text} (Google Login)"
                    elif "microsoft" in selector.lower():
                        descriptive_text = f"{text} (Microsoft Login)"
                    elif "btn__primary" in selector or "login_submit" in selector:
                        descriptive_text = f"{text} (Main Login Form)"
                    
                    error_lines.append(f"   Option {i}: \"{descriptive_text}\"")
                    error_lines.append(f"   └─ Selector: {selector}")
                    error_lines.append(f"")
                
                # Get descriptive examples for the instructions
                example1 = options[0][0]
                example2 = options[1][0] if len(options) > 1 else options[0][0]
                
                if "apple" in options[0][1].lower():
                    example1 = f"{options[0][0]} (Apple Login)"
                elif "btn__primary" in options[0][1] or "login_submit" in options[0][1]:
                    example1 = f"{options[0][0]} (Main Login Form)"
                    
                if len(options) > 1:
                    if "apple" in options[1][1].lower():
                        example2 = f"{options[1][0]} (Apple Login)"
                    elif "btn__primary" in options[1][1] or "login_submit" in options[1][1]:
                        example2 = f"{options[1][0]} (Main Login Form)"
                
                error_lines.extend([
                    f"💡 To fix this, replace your selector with one of the exact texts above.",
                    f"   For example, change:",
                    f"   FROM: '{original_selector}'",
                    f"   TO:   '{example1}'  (for option 1)",
                    f"   OR:   '{example2}'  (for option 2)",
                    f""
                ])
                
                user_friendly_error = "\n".join(error_lines)
                logger.error(f"Ambiguous selector detected:\n{user_friendly_error}")
                raise ValueError(user_friendly_error)
        
        # If not ambiguous, treat first line as the selector
        selector = lines[0]
        
        # Clean up common AI formatting issues
        if selector.startswith('[') and selector.endswith(']'):
            selector = selector[1:-1]  # Remove brackets
        
        return selector.strip()