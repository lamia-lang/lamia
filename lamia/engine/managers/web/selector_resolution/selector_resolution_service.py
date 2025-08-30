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

IMPORTANT: For AMBIGUOUS format, make the option texts DISTINCTIVE and DESCRIPTIVE so users can tell them apart. Each option text MUST be unique enough that if a user used it as a selector, it would find only ONE element. Examples:
- Instead of: "Sign in" and "Sign in" 
- Use: "Sign in with Google" and "Sign in with Apple" and "Sign in button"
- Instead of: "Submit" and "Submit"
- Use: "Submit search form" and "Submit contact form"
- Add context like: "button", "link", "with [service]", "in [location]", etc.

CRITICAL: Each option text you provide MUST be specific enough to uniquely identify ONE element on the page.

NEVER suggest the original failing selector text as one of your options. If the user's selector was "Sign in button", do NOT include "Sign in button" as an option.

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
            # If ambiguous, this will validate suggestions before raising the error
            resolved_selector = await self._parse_ai_response_with_validation(response, original_selector, page_url)
            
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
                # This is a user-friendly ambiguity error - just log once and re-raise
                logger.info(f"Ambiguous selector detected for '{original_selector}'")
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
        elif operation_type == "type_text":
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
        elif operation_type == "wait_for":
            return """OPERATION: You need to find an element that is visible on the page and can be interacted with. It can become visible after a delay.
Look for elements like:
- Menu items
- Buttons with hover effects
- Links
- Interactive elements"""
        elif operation_type == "get_text":
            return """OPERATION: You need to find an element that has text content.
Look for elements like:
- <p> tags
- <span> tags
- <div> tags
- <h1> tags
- <h2> tags"""
        elif operation_type == "is_visible":
            return """OPERATION: You need to find an element that is visible on the page and can be interacted with.
Look for elements like:
- Menu items
- Buttons with hover effects
- Links
- Interactive elements"""
        elif operation_type == "is_enabled":
            return """OPERATION: You need to find an element that is enabled on the page and can be interacted with.
Look for elements like:
- Menu items
- Buttons with hover effects
- Links
- Interactive elements"""
        else:
            return """OPERATION: Find the element that matches the description."""
    
    async def _parse_ai_response_with_validation(self, response: str, original_selector: str, page_url: str = "unknown") -> str:
        """Parse AI response, validate suggestions if ambiguous, and handle accordingly.
        
        Args:
            response: The AI response text
            original_selector: The original selector for error messages
            
        Returns:
            A single CSS selector
            
        Raises:
            ValueError: If response is ambiguous with validated suggestions, or invalid
        """
        lines = [line.strip() for line in response.split('\n') if line.strip()]
        
        if not lines:
            raise ValueError("Empty AI response")
        
        # Check if response indicates ambiguity
        if response.strip().startswith("AMBIGUOUS"):
            logger.debug("AI response indicates ambiguity, parsing options")
            
            # Special case: if the original selector was an exclusionary description we generated,
            # and the AI still says it's ambiguous, we should trust our deduction and not validate
            if "but not the" in original_selector.lower():
                logger.info(f"Original selector '{original_selector}' is an exclusionary description - will bypass validation for generated suggestions")
                bypass_validation = True
            else:
                bypass_validation = False
            
            # Parse AMBIGUOUS response format
            options = []
            for line in lines[1:]:  # Skip "AMBIGUOUS" line
                if ': "' in line and '" ->' in line:
                    # Parse: OPTION1: "exact text" -> selector
                    parts = line.split(': "', 1)
                    if len(parts) == 2:
                        text_and_selector = parts[1]
                        if '" ->' in text_and_selector:
                            text, selector = text_and_selector.split('" ->', 1)
                            options.append((text.strip(), selector.strip()))
            
            if len(options) > 1:
                # Filter out suggestions that are exactly the same as the original failing selector
                # Only filter exact matches to avoid removing valid suggestions with slight differences
                filtered_options = []
                original_exact = original_selector.strip()
                
                for text, selector in options:
                    text_exact = text.strip()
                    
                    # Only filter if the suggestion is exactly the same as the original (including case)
                    if text_exact.lower() == original_exact.lower():
                        logger.warning(f"AI suggested exactly the same failing selector '{text}' - filtering it out")
                    else:
                        filtered_options.append((text, selector))
                        logger.debug(f"Keeping suggestion: '{text}' (different from original '{original_exact}')")
                
                # Now validate each suggestion to ensure it's actually unique (unless bypassing)
                if len(filtered_options) >= 2:
                    if bypass_validation:
                        logger.info(f"Bypassing validation for exclusionary description - trusting {len(filtered_options)} AI suggestions")
                        validated_options = filtered_options
                        
                        # For exclusionary descriptions, we should return the main CSS selector directly
                        # Find the shortest/simplest option (the main element) and return its CSS selector
                        main_option = min(filtered_options, key=lambda x: len(x[0].split()))
                        logger.info(f"Exclusionary description resolved to main element: '{main_option[0]}' -> {main_option[1]}")
                        
                        # Cache and return the CSS selector
                        await self.cache.set(original_selector, page_url, main_option[1])
                        return main_option[1]
                    else:
                        logger.info(f"Validating {len(filtered_options)} AI suggestions to ensure they're actually unique")
                        validated_options = []
                    
                    if not bypass_validation:
                        for text, selector in filtered_options:
                            try:
                                logger.debug(f"Testing suggestion: '{text}'")
                                
                                # Test if this suggestion would itself be ambiguous
                                page_html = await self.get_page_html()
                                test_prompt = f"""You are a web automation expert. Given the following HTML page and a natural language description of an element, return a response in one of these formats:

OPERATION: You need to find a CLICKABLE element (button, link, clickable text, etc.).

CRITICAL RULE: You MUST check for ALL elements that could match the description. If there are 2 or more possible matches, you MUST use AMBIGUOUS format.

FORMAT 1 - Single match found (ONLY if exactly one element matches):
Return only the CSS selector, no brackets or extra text.

FORMAT 2 - Multiple ambiguous matches found (REQUIRED when 2+ elements match):
AMBIGUOUS
OPTION1: "descriptive_text_1" -> css_selector_1
OPTION2: "descriptive_text_2" -> css_selector_2

HTML:
{page_html}

Natural language selector: "{text}"

Your response:"""
                                
                                llm_command = LLMCommand(prompt=test_prompt)
                                test_result = await self.llm_manager.execute(llm_command)
                                test_response = test_result.validated_text.strip()
                                
                                if test_response.startswith("AMBIGUOUS"):
                                    logger.warning(f"Suggestion '{text}' is still ambiguous, skipping (will try deduction logic)")
                                else:
                                    # This suggestion is unique, keep it
                                    logger.debug(f"Suggestion '{text}' is unique, keeping it")
                                    validated_options.append((text, selector))
                                    
                            except Exception as validation_error:
                                logger.warning(f"Could not validate suggestion '{text}': {validation_error}")
                                # If validation fails, assume it's good and keep it
                                validated_options.append((text, selector))
                    
                    # Apply deduction logic to find the main element
                    deduced_main_element = self._deduce_main_button(filtered_options, original_selector)
                    if deduced_main_element:
                        logger.info(f"Deduced main element: '{deduced_main_element[0]}' -> {deduced_main_element[1]}")
                        
                        # If the deduced main element's exclusionary text matches the original selector,
                        # it means the user is trying to use our suggested exclusionary description.
                        # In this case, we should not be in this ambiguous path at all - 
                        # the exclusionary description should have resolved unambiguously.
                        if deduced_main_element[0] == original_selector:
                            logger.error(f"User is using our exclusionary suggestion '{original_selector}' but AI still found it ambiguous - this should not happen")
                            # This indicates the exclusionary description didn't work as expected
                        
                        # Otherwise, add the deduced main element to validated options if not already there
                        if deduced_main_element not in validated_options:
                            validated_options.insert(0, deduced_main_element)  # Put it first
                    
                    # Check if we have enough suggestions (including deduced main element)
                    if len(validated_options) < 2:
                        logger.error(f"After validation and deduction, only {len(validated_options)} unique suggestions remain")
                        raise ValueError(f"Could not find enough unique alternatives for ambiguous selector '{original_selector}'. All AI suggestions were still ambiguous. Please try using a more specific natural language description or a CSS selector.")
                    else:
                        logger.info(f"Successfully validated {len(validated_options)} unique suggestions (including deduced main element)")
                        options = validated_options
                else:
                    # Not enough options after filtering
                    logger.error(f"AI provided unusable suggestions for '{original_selector}'")
                    raise ValueError(f"Could not find unique alternatives for ambiguous selector '{original_selector}'. The AI suggestions were not specific enough. Please try using a more precise natural language description or a CSS selector.")
                
                # Create user-friendly error message with validated options
                error_lines = [
                    f"\n🚨 AMBIGUOUS SELECTOR: '{original_selector}'",
                    f"",
                    f"Multiple elements match your description. Please be more specific by using one of these exact texts:",
                    f""
                ]
                
                for i, (text, selector) in enumerate(options, 1):
                    error_lines.append(f"   Option {i}: \"{text}\"")
                    error_lines.append(f"   └─ Selector: {selector}")
                    error_lines.append(f"")
                
                # Use AI suggestions directly for examples
                example1 = options[0][0]
                example2 = options[1][0] if len(options) > 1 else options[0][0]
                
                error_lines.extend([
                    f"💡 To fix this, replace your selector with one of the exact texts above.",
                    f"   For example, change:",
                    f"   FROM: '{original_selector}'",
                    f"   TO:   '{example1}'  (for option 1)",
                    f"   OR:   '{example2}'  (for option 2)",
                    f""
                ])
                
                user_friendly_error = "\n".join(error_lines)
                raise ValueError(user_friendly_error)
        
        # If not ambiguous, treat first line as the selector
        selector = lines[0]
        
        # Clean up common AI formatting issues
        if selector.startswith('"') and selector.endswith('"'):
            selector = selector[1:-1]
        
        if not selector:
            raise ValueError("AI returned empty selector")
            
        return selector

    def _deduce_main_button(self, all_options: list, original_selector: str) -> tuple:
        """Deduce which option is the primary/main element using purely generic logic.
        
        Simple deduction by counting words in option text:
        - Options with more words are likely more specific/qualified
        - Options with fewer words are likely more generic/main
        - Return the option with the shortest text (fewest words)
        - Enhance the suggestion with context from original selector to make it more descriptive
        
        Args:
            all_options: List of (text, selector) tuples from AI
            original_selector: The original user selector for context
            
        Returns:
            (text, selector) tuple  for the deduced main element, or None if can't deduce
        """
        if len(all_options) < 2:
            return None
            
        # Sort options by text length (word count) - shortest first
        options_by_length = sorted(all_options, key=lambda x: len(x[0].split()))
        
        shortest_option = options_by_length[0]
        shortest_word_count = len(shortest_option[0].split())
        
        # Check if the shortest is significantly shorter than others
        next_shortest_count = len(options_by_length[1][0].split()) if len(options_by_length) > 1 else shortest_word_count + 1
        
        if shortest_word_count < next_shortest_count:
            # Create an exclusionary description that will resolve unambiguously
            exclusionary_text = self._create_exclusionary_description(shortest_option[0], all_options)
            logger.info(f"Deduced main element by simplicity: '{shortest_option[0]}' -> exclusionary description: '{exclusionary_text}' ({shortest_word_count} words vs {next_shortest_count}+ words for others)")
            return (exclusionary_text, shortest_option[1])
        
        logger.debug("Could not deduce main element - all options have similar complexity")
        return None
    
    def _create_exclusionary_description(self, main_text: str, all_options: list) -> str:
        """Create a natural language description that excludes other options.
        
        This generates descriptions like:
        "Sign in button but not the Google or Apple sign in options"
        
        Args:
            main_text: The main text we want to target (e.g., "Sign in")
            all_options: All available options to exclude from
            
        Returns:
            Natural language description that excludes other options
        """
        # Find all the options that are NOT the main one
        exclusions = []
        main_text_lower = main_text.lower()
        
        for text, selector in all_options:
            text_lower = text.lower()
            if text_lower != main_text_lower:
                # Extract the distinguishing part (like "Google", "Apple", etc.)
                # Remove common words to find the unique identifier
                words_to_remove = main_text_lower.split()
                remaining_words = []
                
                for word in text.split():
                    if word.lower() not in words_to_remove:
                        remaining_words.append(word)
                
                if remaining_words:
                    exclusions.append(' '.join(remaining_words))
                else:
                    # Fallback: use the full text if we can't extract distinguishing parts
                    exclusions.append(text)
        
        # Create the exclusionary description
        if exclusions:
            if len(exclusions) == 1:
                exclusion_text = exclusions[0]
            elif len(exclusions) == 2:
                exclusion_text = f"{exclusions[0]} or {exclusions[1]}"
            else:
                exclusion_text = f"{', '.join(exclusions[:-1])}, or {exclusions[-1]}"
            
            # Generate natural language that excludes the others
            enhanced = f"{main_text} but not the {exclusion_text} options"
        else:
            # Fallback if no exclusions found
            enhanced = f"{main_text} button"
            
        return enhanced

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
                # Remove any options that are the same as the original failing selector
                # This prevents the AI from suggesting the same text that just failed
                filtered_options = []
                original_normalized = original_selector.strip().lower()
                logger.debug(f"Original selector normalized: '{original_normalized}'")
                
                for text, selector in options:
                    text_normalized = text.strip().lower()
                    logger.debug(f"Comparing option '{text}' (normalized: '{text_normalized}') with original")
                    
                    if text_normalized != original_normalized:
                        filtered_options.append((text, selector))
                        logger.debug(f"Keeping option: '{text}'")
                    else:
                        logger.warning(f"AI suggested the same failing selector '{text}' - filtering it out")
                        logger.warning(f"  Original: '{original_selector}' -> '{original_normalized}'")
                        logger.warning(f"  Option:   '{text}' -> '{text_normalized}'")
                
                # Use the filtered options (we'll validate later in the calling function)
                options = filtered_options
                
                # Format the error message to be very clear and actionable for the user
                error_lines = [
                    f"\n🚨 AMBIGUOUS SELECTOR: '{original_selector}'",
                    f"",
                    f"Multiple elements match your description. Please be more specific by using one of these exact texts:",
                    f""
                ]
                
                for i, (text, selector) in enumerate(options, 1):
                    # Use the AI's suggestions as-is - they should already be descriptive enough
                    error_lines.append(f"   Option {i}: \"{text}\"")
                    error_lines.append(f"   └─ Selector: {selector}")
                    error_lines.append(f"")
                
                # Use AI suggestions directly for examples
                example1 = options[0][0]
                example2 = options[1][0] if len(options) > 1 else options[0][0]
                
                error_lines.extend([
                    f"💡 To fix this, replace your selector with one of the exact texts above.",
                    f"   For example, change:",
                    f"   FROM: '{original_selector}'",
                    f"   TO:   '{example1}'  (for option 1)",
                    f"   OR:   '{example2}'  (for option 2)",
                    f""
                ])
                
                user_friendly_error = "\n".join(error_lines)
                # Don't log at ERROR level here - will be logged as INFO above
                raise ValueError(user_friendly_error)
        
        # If not ambiguous, treat first line as the selector
        selector = lines[0]
        
        # Clean up common AI formatting issues
        if selector.startswith('[') and selector.endswith(']'):
            selector = selector[1:-1]  # Remove brackets
        
        return selector.strip()