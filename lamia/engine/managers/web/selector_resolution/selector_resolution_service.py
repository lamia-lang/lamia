"""Orchestrator service for AI-powered selector resolution."""

import logging
from typing import Any, Optional, Callable, Awaitable
from .ai_selector_cache import AISelectorCache
from .selector_parser import SelectorParser, SelectorType
from .response_parser import ResponseParser, AmbiguousFormatResponseParser
from .progressive.strategy_resolver import ProgressiveSelectorResolver
from lamia.interpreter.commands import LLMCommand
from lamia.engine.config_provider import ConfigProvider

logger = logging.getLogger(__name__)

class SelectorResolutionService:
    """Orchestrates AI-powered selector resolution with caching."""
    
    def __init__(self, llm_manager, config_provider: ConfigProvider, get_page_html_func: Optional[Callable[[], Awaitable[str]]] = None, get_browser_adapter_func: Optional[Callable[[], Awaitable]] = None, response_parser: Optional[ResponseParser] = None):
        """Initialize the selector resolution service.
        
        Args:
            llm_manager: LLM manager for AI-powered selector resolution
            config_provider: Configuration provider
            get_page_html_func: Function to get current page HTML (optional)
            get_browser_adapter_func: Function to get browser adapter for validation (optional)
            response_parser: Custom response parser implementation (defaults to AmbiguousFormatResponseParser)
        """
        self.parser = SelectorParser()
        self.llm_manager = llm_manager
        self.get_page_html = get_page_html_func
        self.get_browser_adapter = get_browser_adapter_func
        self.config_provider = config_provider
        self.cache = AISelectorCache(config_provider)
        self.response_parser = response_parser or AmbiguousFormatResponseParser()
        self._progressive_resolver = None  # Lazy initialized
        self._visual_picker = None  # Lazy initialized
        
    async def resolve_selector(self, selector: str, page_url: str, page_context: Optional[str] = None, operation_type: Optional[str] = None, parent_context: Optional[str] = None, scope_element_handle: Optional[Any] = None) -> str:
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
        
        context_desc = f" (within {parent_context})" if parent_context else ""
        cached_result = await self.cache.get(original_selector, page_url, parent_context)
        if cached_result:
            logger.info(f"Using cached resolution: '{original_selector}' → '{cached_result}'{context_desc}")
            return cached_result
        
        # Use AI to resolve the selector
        try:
            logger.info(f"Sending selector '{original_selector}' to AI for resolution")
            
            resolved_selector = None

            # For natural language selectors, use visual picker as primary method
            if selector_type == SelectorType.NATURAL_LANGUAGE:
                logger.info(f"Natural language selector detected: '{original_selector}', operation_type: '{operation_type}'")
                
                try:
                    logger.info("Using progressive selector resolution (fallback method)")
                    
                    # Initialize progressive resolver lazily
                    if self._progressive_resolver is None:
                        if self.get_browser_adapter is None:
                            raise ValueError("Browser adapter function not provided for progressive resolution")
                        
                        if self.config_provider is None:
                            raise ValueError("Config provider not provided for progressive resolution")
                        
                        browser_adapter = await self.get_browser_adapter()
                        self._progressive_resolver = ProgressiveSelectorResolver(
                            browser_adapter,
                            self.llm_manager,
                            self.cache,
                            self.config_provider
                        )
                    
                    resolved_selector, found_elements = await self._progressive_resolver.resolve(
                        original_selector,
                        page_url,
                        scope_element_handle=scope_element_handle,
                    )
                    
                    logger.info(f"Progressive resolution succeeded: '{original_selector}' → '{resolved_selector}'")
                except Exception as e:
                    logger.error(f"Progressive resolution failed: {e}.")
              
                if resolved_selector is None and self.config_provider.is_human_in_loop_enabled():
                    logger.info("Falling back to visual picker for element selection (fallback method)")
                    
                    try:
                        resolved_selector = await self._resolve_with_visual_picker(
                            original_selector,
                            page_url,
                            operation_type or "get_element"
                        )
                        
                        logger.info(f"✅ Visual picker succeeded: '{original_selector}' → '{resolved_selector}'")
                        await self.cache.set(original_selector, page_url, resolved_selector, parent_context)
                        
                    except Exception as visual_error:
                        logger.warning(f"Visual picker failed: {visual_error}")
                else:
                    logger.debug("Visual picker is not used because human-in-loop is disabled")

                if resolved_selector is None:
                    raise ValueError("Failed to resolve the selector for the natural language selector")
                
                await self.cache.set(original_selector, page_url, resolved_selector, parent_context)
                logger.info(f"Cached resolution: '{original_selector}' → '{resolved_selector}'")
                
                return resolved_selector
            
            else:
                # For invalid CSS/XPath (fix syntax)
                logger.info("Using legacy resolution for invalid CSS/XPath")
                
                # Get current page HTML if not provided
                if page_context is None:
                    if self.get_page_html is None:
                        raise ValueError("Page HTML function not provided for legacy resolution")
                    page_context = await self.get_page_html()
                
                # Create operation-specific instructions and build prompt using parser
                operation_instructions = self._get_operation_instructions(operation_type or "")
                prompt = self.response_parser.get_full_prompt_template(operation_instructions, page_context, original_selector)

                # Use llm_manager to get raw response first (no validation yet)
                llm_command = LLMCommand(prompt=prompt)
                
                result = await self.llm_manager.execute(llm_command)
                response = result.validated_text.strip()
                
                if not response:
                    raise ValueError("LLM returned empty response")
                
                # Parse response using the configured parser
                parse_result = self.response_parser.parse_response(response, original_selector)
                
                if parse_result.is_ambiguous:
                    # Handle ambiguous response with validation and deduction
                    resolved_selector = await self._handle_ambiguous_response(parse_result.options, original_selector, page_url, operation_type or "", parent_context)
                else:
                    resolved_selector = parse_result.selector
                
                # Only validate if we got a single selector (not ambiguous)
                from .validators.ai_resolved_selector_validator import AIResolvedSelectorValidator
                
                if self.get_browser_adapter is None:
                    raise ValueError("Browser adapter function not provided for validation")
                
                browser_adapter = await self.get_browser_adapter()
                validator = AIResolvedSelectorValidator(browser_adapter)
                
                if resolved_selector is None:
                    raise ValueError("Resolved selector is None")
                
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
        
        # Cache the legacy resolution
        logger.debug(f"Caching legacy resolution: '{original_selector}' on '{page_url}' → '{resolved_selector}'")
        await self.cache.set(original_selector, page_url, resolved_selector, parent_context)
        logger.info(f"Legacy resolution cached: '{original_selector}' → '{resolved_selector}'")
        
        return resolved_selector
    
    async def clear_cache(self) -> None:
        """Clear all cached selector resolutions."""
        self.cache.clear()
        logger.info("Cleared selector resolution cache")
    
    async def invalidate_cached_selector(self, original_selector: str, page_url: str) -> None:
        """Invalidate a specific cached selector across all caches.
        
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
    
    async def _handle_ambiguous_response(self, options: list, original_selector: str, page_url: str, operation_type: str, parent_context: Optional[str] = None) -> str:
        """Handle an ambiguous AI response by validating suggestions and applying deduction logic.
        
        Args:
            options: List of (text, selector) tuples from AI response
            original_selector: The original selector for context
            page_url: Page URL for caching
            operation_type: Type of operation for validation
            
        Returns:
            A single CSS selector (if exclusionary description works)
            
        Raises:
            ValueError: If ambiguity cannot be resolved
        """
        logger.debug("AI response indicates ambiguity, processing options")
        
        # Special case: if the original selector was an exclusionary description we generated,
        # and the AI still says it's ambiguous, we should trust our deduction and not validate
        if "but not the" in original_selector.lower():
            logger.info(f"Original selector '{original_selector}' is an exclusionary description - will bypass validation for generated suggestions")
            bypass_validation = True
        else:
            bypass_validation = False
        
        if len(options) > 1:
            # Filter out suggestions that are exactly the same as the original failing selector
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
                    await self.cache.set(original_selector, page_url, main_option[1], parent_context)
                    return main_option[1]
                else:
                    logger.info(f"Validating {len(filtered_options)} AI suggestions to ensure they're actually unique")
                    validated_options = await self._validate_ai_suggestions(filtered_options, original_selector, operation_type)
                
                # Handle final options and show ambiguity error
                final_options = self._prepare_final_options_with_deduction(validated_options, original_selector)
                self._raise_ambiguity_error(original_selector, final_options)
            else:
                # Not enough options after filtering
                self._raise_insufficient_options_error(original_selector)
        else:
            # Single option or no options - this shouldn't happen in ambiguous case
            raise ValueError("AI reported ambiguity but provided insufficient options")
        
        # This line should never be reached, but satisfies type checker
        raise ValueError("Ambiguity resolution failed")
    
    async def _resolve_with_visual_picker(
        self,
        original_selector: str,
        page_url: str,
        operation_type: str
    ) -> str:
        """
        Resolve selector using visual picker.
        
        Args:
            original_selector: Natural language description
            page_url: Current page URL
            operation_type: Browser operation type (click, get_element, etc.)
            
        Returns:
            Resolved CSS/XPath selector
        """
        try:
            # Initialize visual picker lazily
            if self._visual_picker is None:
                from .visual_picker import VisualElementPicker
                
                if self.get_browser_adapter is None:
                    raise ValueError("Browser adapter function not provided for visual picker")
                
                browser_adapter = await self.get_browser_adapter()
                self._visual_picker = VisualElementPicker(
                    browser_adapter,
                    self.llm_manager,
                    self.config_provider
                )
            
            # Use visual picker to resolve selector
            resolved_selector, found_elements = await self._visual_picker.pick_element_for_method(
                method_name=operation_type,
                description=original_selector,
                page_url=page_url
            )
            
            if not resolved_selector:
                raise ValueError("Visual picker returned no selector")
            
            return resolved_selector
            
        except Exception as e:
            logger.error(f"Visual picker resolution failed: {e}")
            raise ValueError(f"Visual picker could not resolve '{original_selector}': {e}")
    
    async def resolve_within_visual_context(
        self,
        visual_xpath: str,
        inner_selector: str,
        page_url: str
    ) -> dict:
        """
        Two-phase resolution: First get elements using visual XPath, then resolve within each context.
        
        This method is used when you have a cached visual picker XPath and need to find 
        specific elements (like "question" or "answer") within each matched element.
        
        Args:
            visual_xpath: XPath from visual picker that finds the element groups
            inner_selector: Natural language description of what to find within each element
            page_url: Current page URL for caching
            
        Returns:
            Dictionary with matches found in each context
        """
        logger.info(f"🔍 Two-phase resolution: visual_xpath='{visual_xpath}', inner='{inner_selector}'")
        
        # Initialize context extractor
        from .visual_picker.context_extractor import ElementContextExtractor
        
        if self.get_browser_adapter is None:
            raise ValueError("Browser adapter function required for context extraction")
        
        browser_adapter = await self.get_browser_adapter()
        context_extractor = ElementContextExtractor(browser_adapter)
        
        # Phase 1: Extract HTML contexts for all elements matched by visual XPath
        contexts = await context_extractor.extract_contexts_for_xpath(visual_xpath)
        
        if not contexts:
            logger.warning(f"No contexts found for visual XPath: {visual_xpath}")
            return {'matches': [], 'contexts_processed': 0, 'total_matches': 0}
        
        logger.info(f"📋 Phase 1 complete: Found {len(contexts)} element contexts")
        
        # Phase 2: Resolve inner selector within each context
        resolution_result = await context_extractor.resolve_within_contexts(
            contexts,
            inner_selector,
            self.llm_manager
        )
        
        logger.info(f"✅ Phase 2 complete: Found {resolution_result['total_matches']} matches across {resolution_result['contexts_processed']} contexts")
        
        return resolution_result
    
    def _get_operation_instructions(self, operation_type: Optional[str], for_validation: bool = False) -> str:
        """Get operation-specific instructions for the AI prompt.
        
        Args:
            operation_type: The browser operation type (click, type, etc.)
            for_validation: If True, returns validation-specific instructions
            
        Returns:
            Operation-specific instruction text
        """
        if operation_type == "click":
            base_instruction = """OPERATION: You need to find a CLICKABLE element (button, link, clickable text, etc.).
Look for elements like:
- <button> tags
- <a> tags with href
- Elements with onclick handlers
- Clickable text or icons
- Submit buttons
- Navigation links"""
            if for_validation:
                return base_instruction + "\n\nVALIDATION: Check if the description matches MULTIPLE clickable elements. If so, use AMBIGUOUS format."
            return base_instruction
        elif operation_type == "type_text":
            base_instruction = """OPERATION: You need to find an INPUT element where text can be typed.
Look for elements like:
- <input> tags (text, email, password, etc.)
- <textarea> tags
- Editable elements with contenteditable="true"
- Search boxes
- Form fields"""
            if for_validation:
                return base_instruction + "\n\nVALIDATION: Check if the description matches MULTIPLE input elements. If so, use AMBIGUOUS format."
            return base_instruction
        elif operation_type == "select":
            base_instruction = """OPERATION: You need to find a SELECT dropdown element.
Look for elements like:
- <select> tags
- Dropdown menus
- Option lists"""
            if for_validation:
                return base_instruction + "\n\nVALIDATION: Check if the description matches MULTIPLE select elements. If so, use AMBIGUOUS format."
            return base_instruction
        elif operation_type == "hover":
            base_instruction = """OPERATION: You need to find an element that can be hovered over.
Look for elements like:
- Menu items
- Buttons with hover effects
- Links
- Interactive elements"""
            if for_validation:
                return base_instruction + "\n\nVALIDATION: Check if the description matches MULTIPLE hoverable elements. If so, use AMBIGUOUS format."
            return base_instruction
        elif operation_type == "wait_for":
            base_instruction = """OPERATION: You need to find an element that is visible on the page and can be interacted with. It can become visible after a delay.
Look for elements like:
- Menu items
- Buttons with hover effects
- Links
- Interactive elements"""
            if for_validation:
                return base_instruction + "\n\nVALIDATION: Check if the description matches MULTIPLE visible elements. If so, use AMBIGUOUS format."
            return base_instruction
        elif operation_type == "get_text":
            base_instruction = """OPERATION: You need to find an element that has text content.
Look for elements like:
- <p> tags
- <span> tags
- <div> tags
- <h1> tags
- <h2> tags"""
            if for_validation:
                return base_instruction + "\n\nVALIDATION: Check if the description matches MULTIPLE text elements. If so, use AMBIGUOUS format."
            return base_instruction
        elif operation_type == "is_visible":
            base_instruction = """OPERATION: You need to find an element that is visible on the page and can be interacted with.
Look for elements like:
- Menu items
- Buttons with hover effects
- Links
- Interactive elements"""
            if for_validation:
                return base_instruction + "\n\nVALIDATION: Check if the description matches MULTIPLE visible elements. If so, use AMBIGUOUS format."
            return base_instruction
        elif operation_type == "is_enabled":
            base_instruction = """OPERATION: You need to find an element that is enabled on the page and can be interacted with.
Look for elements like:
- Menu items
- Buttons with hover effects
- Links
- Interactive elements"""
            if for_validation:
                return base_instruction + "\n\nVALIDATION: Check if the description matches MULTIPLE enabled elements. If so, use AMBIGUOUS format."
            return base_instruction
        else:
            base_instruction = """OPERATION: Find the element that matches the description."""
            if for_validation:
                return base_instruction + "\n\nVALIDATION: Check if the description matches MULTIPLE elements. If so, use AMBIGUOUS format."
            return base_instruction
    


    def _deduce_main_element(self, all_options: list, original_selector: str) -> tuple:
        """Deduce which option is the primary/main element using purely generic logic.
        
        This method uses algorithmic analysis to identify the most likely intended element
        when multiple options are available. It works for any element type (buttons, links, 
        inputs, divs, etc.) and any operation (click, type, hover, etc.).
        
        Algorithm:
        - Analyzes word count in option text (shorter = more generic/main)
        - Creates exclusionary natural language descriptions
        - Returns enhanced suggestion that can be resolved unambiguously by AI
        
        Args:
            all_options: List of (text, selector) tuples from AI response
            original_selector: The original user selector for context
            
        Returns:
            (enhanced_text, css_selector) tuple for the deduced main element, or None if can't deduce
        """
        if len(all_options) < 2:
            return None  # type: ignore[return-value]
            
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
        return None  # type: ignore[return-value]
    
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

    async def _validate_ai_suggestions(self, filtered_options: list, original_selector: str, operation_type: str) -> list:
        """Validate each AI suggestion to ensure it's actually unique by testing with AI.
        
        Args:
            filtered_options: List of (text, selector) tuples to validate
            original_selector: Original selector for context
            operation_type: Type of operation for generating appropriate prompt
            
        Returns:
            List of validated (text, selector) tuples that are actually unique
        """
        logger.info(f"Validating {len(filtered_options)} AI suggestions to ensure they're actually unique")
        validated_options = []
        
        for text, selector in filtered_options:
            try:
                logger.debug(f"Testing suggestion: '{text}'")
                
                # Test if this suggestion would itself be ambiguous using validation prompt
                if self.get_page_html is None:
                    logger.warning("Cannot validate suggestions without page HTML function")
                    validated_options.append((text, selector))
                    continue
                
                page_html = await self.get_page_html()
                operation_instructions = self._get_operation_instructions(operation_type, for_validation=True)
                
                test_prompt = self.response_parser.get_validation_prompt_template(operation_instructions, page_html, text)
                
                llm_command = LLMCommand(prompt=test_prompt)
                test_result = await self.llm_manager.execute(llm_command)
                test_response = test_result.validated_text.strip()
                
                if self.response_parser.is_ambiguous_response(test_response):
                    logger.warning(f"Suggestion '{text}' is still ambiguous, skipping (will try deduction logic)")
                else:
                    # This suggestion is unique, keep it
                    logger.debug(f"Suggestion '{text}' is unique, keeping it")
                    validated_options.append((text, selector))
                    
            except Exception as validation_error:
                logger.warning(f"Could not validate suggestion '{text}': {validation_error}")
                # If validation fails, assume it's good and keep it
                validated_options.append((text, selector))
        
        return validated_options
    
    def _prepare_final_options_with_deduction(self, validated_options: list, original_selector: str) -> list:
        """Prepare final options for ambiguity error, applying deduction logic if needed.
        
        Args:
            validated_options: List of validated (text, selector) tuples
            original_selector: Original selector for context
            
        Returns:
            Final list of options with deduced main element prioritized
        """
        # Check if we have enough suggestions for ambiguity handling
        if len(validated_options) < 2:
            logger.error(f"After validation, only {len(validated_options)} unique suggestions remain")
            raise ValueError(f"Could not find enough unique alternatives for ambiguous selector '{original_selector}'. All AI suggestions were still ambiguous. Please try using a more specific natural language description or a CSS selector.")
        
        logger.info(f"Successfully validated {len(validated_options)} unique suggestions")
        options = validated_options
        
        # Apply deduction logic only when we're about to show ambiguity to the user
        # This helps prioritize the most likely intended element
        deduced_main_element = self._deduce_main_element(options, original_selector)
        if deduced_main_element:
            logger.info(f"Deduced main element: '{deduced_main_element[0]}' -> {deduced_main_element[1]}")
            
            # If the deduced main element's exclusionary text matches the original selector,
            # it means the user is trying to use our suggested exclusionary description.
            # In this case, we should not be in this ambiguous path at all - 
            # the exclusionary description should have resolved unambiguously.
            if deduced_main_element[0] == original_selector:
                logger.error(f"User is using our exclusionary suggestion '{original_selector}' but AI still found it ambiguous - this should not happen")
                # This indicates the exclusionary description didn't work as expected
            
            # Add the deduced main element to options if not already there (prioritize it)
            if deduced_main_element not in options:
                options.insert(0, deduced_main_element)  # Put it first
        
        return options
    
    def _raise_ambiguity_error(self, original_selector: str, options: list) -> None:
        """Raise a user-friendly ambiguity error with suggested options.
        
        Args:
            original_selector: The original selector that was ambiguous
            options: List of (text, selector) tuples to suggest to user
        """
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
    
    def _raise_insufficient_options_error(self, original_selector: str) -> None:
        """Raise an error when not enough unique options are available.
        
        Args:
            original_selector: The original selector that failed
        """
        logger.error(f"AI provided unusable suggestions for '{original_selector}'")
        raise ValueError(f"Could not find unique alternatives for ambiguous selector '{original_selector}'. The AI suggestions were not specific enough. Please try using a more precise natural language description or a CSS selector.")

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