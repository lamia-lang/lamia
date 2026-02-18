"""Core visual element picker orchestrator."""

import logging
import re
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from .overlay import BrowserOverlay
from .cache import VisualSelectionCache
from .validation import SelectionValidator
from lamia.engine.config_provider import ConfigProvider

logger = logging.getLogger(__name__)


class VisualElementPicker:
    """
    Main orchestrator for visual element selection.
    
    Handles the complete flow:
    1. Check cache for previous selections
    2. Show browser overlay for user selection
    3. Validate selection appropriateness 
    4. Generate scoped selectors using AI
    5. Cache the result
    """
    
    def __init__(
        self,
        browser_adapter,
        llm_manager,
        config_provider: ConfigProvider,
    ):
        """Initialize the visual picker.
        
        Args:
            browser_adapter: Browser adapter for overlay injection and element finding
            llm_manager: LLM manager for generating scoped selectors
            config_provider: Configuration provider for cache settings
        """
        self.browser = browser_adapter
        self.llm_manager = llm_manager
        self.overlay = BrowserOverlay(browser_adapter)
        self.cache = VisualSelectionCache(config_provider)
        self.validator = SelectionValidator()
    
    async def pick_element_for_method(
        self,
        method_name: str,
        description: str, 
        page_url: str
    ) -> Tuple[str, List[Any]]:
        """
        Pick element(s) for a specific web method.
        
        Args:
            method_name: Web method name (click, get_element, get_elements, etc.)
            description: Natural language description of target element(s)
            page_url: Current page URL for caching
            
        Returns:
            (resolved_selector, found_elements) tuple
        """
        logger.info(f"Visual picking for {method_name}('{description}') on {page_url}")
        
        # Check cache first
        cached = await self.cache.get(method_name, description, page_url)
        if cached:
            logger.info("Using cached visual selection")
            return await self._use_cached_selection(cached)
        
        # Determine selection strategy based on method
        is_plural = method_name in ['get_elements']
        strategy = 'plural' if is_plural else 'singular'
        
        # Show visual picker
        selection_result = await self._show_picker(method_name, description, strategy)
        
        # Generate scoped selectors using AI
        resolved_selector = await self._generate_scoped_selectors(
            description, 
            selection_result
        )
        
        # Find elements using resolved selector
        elements = await self._find_elements_with_selector(resolved_selector)
        
        # Validate the result makes sense
        await self._validate_result(method_name, description, elements, is_plural)
        
        # Cache the successful selection (filter out non-serializable data)
        cache_data = {
            'selector': resolved_selector,
            'element_count': len(elements)
        }
        
        # Only cache serializable parts of selection_result
        if selection_result:
            cache_data['selection_type'] = selection_result.get('selection_type')
            cache_data['working_selector'] = selection_result.get('working_selector')
            # Skip 'found_elements' and 'selected_element' as they contain WebElement objects
        
        await self.cache.set(method_name, description, page_url, cache_data)
        
        # Log detailed information about the found selector
        logger.info(f"✅ Visual picking successful for '{description}':")
        logger.info(f"   📍 Resolved selector: {resolved_selector}")
        logger.info(f"   🔢 Found {len(elements)} matching elements")
        logger.info(f"   🎯 Selection strategy: {strategy}")
        
        # For template-based selections, log the working selector details
        if selection_result and selection_result.get('selection_type') == 'template':
            working_selector = selection_result.get('working_selector')
            if working_selector:
                logger.info(f"   🔧 Template selector: {working_selector}")
        
        return resolved_selector, elements
    
    async def _show_picker(self, method_name: str, description: str, strategy: str) -> Dict[str, Any]:
        """Show the visual picker overlay and wait for user selection."""
        
        # Get method-specific instruction
        instruction = self._get_instruction_text(method_name, description, strategy)
        
        # Get method-specific element filter
        element_filter = self._get_element_filter(method_name)
        
        # Show overlay and wait for selection
        logger.info(f"Showing visual picker: {instruction}")
        
        if strategy == 'plural':
            # Use our improved template-based approach for plural methods
            from .strategies.plural_strategy import PluralSelectionStrategy
            plural_strategy = PluralSelectionStrategy(self, self.overlay)
            return await plural_strategy.handle_selection(method_name, description)
        else:
            return await self.overlay.pick_single_element(
                instruction=instruction,
                element_filter=element_filter
            )
    
    def _get_instruction_text(self, method_name: str, description: str, strategy: str) -> str:
        """Get user instruction text based on method and strategy."""
        
        if strategy == 'plural':
            return f"Select area with: '{description}'"
        
        return f"Select: '{description}'"
    
    def _get_element_filter(self, method_name: str) -> Optional[str]:
        """Get JavaScript element filter function for method-specific highlighting.
        
        Returns None for most methods to allow selecting any element.
        Only restricts for very specific input types.
        """
        filters = {
            'upload_file': '''
                function(el) {
                    return el.tagName === 'INPUT' && el.type === 'file';
                }
            '''
        }
        
        return filters.get(method_name)
    
    async def _extract_selector_from_template_result(self, selection_result: Dict[str, Any]) -> str:
        """Extract the working selector from template-based selection result."""
        working_selector = selection_result.get('working_selector')
        if working_selector:
            logger.info(f"Extracted working selector from template: {working_selector}")
            return working_selector
        else:
            # Fallback: try to construct a basic selector from the template element
            selected_element = selection_result.get('selected_element', {})
            tag_name = selected_element.get('tagName', '').lower()
            class_name = selected_element.get('className', '')
            
            if tag_name and class_name:
                fallback_selector = f"{tag_name}.{class_name.replace(' ', '.')}"
                logger.warning(f"No working selector found, using fallback: {fallback_selector}")
                return fallback_selector
            elif tag_name:
                logger.warning(f"No working selector found, using tag fallback: {tag_name}")
                return tag_name
            else:
                raise ValueError("Could not extract selector from template result")
    
    async def _generate_scoped_selectors(self, description: str, selection_result: Dict[str, Any]) -> str:
        """Generate CSS/XPath selectors scoped to the user's selection."""
        
        # Template-based selections already have a working selector
        if selection_result.get('selection_type') == 'template':
            logger.info("Using template-based selector (no LLM needed)")
            found_elements = selection_result.get('found_elements', [])
            if found_elements:
                return await self._extract_selector_from_template_result(selection_result)
        
        selected_element = selection_result.get('selected_element', {})

        # For single-element selections, use the element's own xpath/css directly
        if selection_result.get('selection_type') == 'single':
            xpath = selected_element.get('xpath', '')
            css = selected_element.get('cssSelector', '')
            if xpath:
                logger.info(f"Using selected element XPath directly: {xpath}")
                return xpath
            if css:
                logger.info(f"Using selected element CSS selector directly: {css}")
                return css

        # For container/plural selections, ask LLM for a generic selector
        return await self._generate_generic_selector_via_llm(selected_element)

    async def _generate_generic_selector_via_llm(self, selected_element: Dict[str, Any]) -> str:
        """Ask the LLM to produce a generic XPath for container/plural selections."""
        container_html = selected_element.get('outerHTML', '')
        if len(container_html) > 2000:
            container_html = container_html[:2000] + "..."

        prompt = f"""Analyze this selected element and generate a GENERIC XPath that will match ALL SIMILAR elements on the page:

SELECTED ELEMENT:
{container_html}

TASK: Create ONE generic XPath selector that will find ALL elements similar to the selected one.

RULES:
- Return ONLY the XPath string on a single line, nothing else
- Use structural patterns (tag names, class patterns, attribute patterns)
- Avoid specific text content or unique IDs
- Focus on repeatable structural characteristics

EXAMPLE INPUT: <div class="input-group"><label>Name</label><input type="text"></div>
EXAMPLE OUTPUT: //div[contains(@class,'input-group')]

Your XPath:"""

        from lamia.interpreter.commands import LLMCommand
        llm_command = LLMCommand(prompt=prompt)
        result = await self.llm_manager.execute(llm_command)

        xpath_selector = self._extract_xpath_from_llm_response(result.validated_text)

        if xpath_selector:
            logger.info(f"Generated generic XPath selector: {xpath_selector}")
            return xpath_selector

        logger.warning("Failed to extract XPath from LLM response, using fallback")
        return "//div[(.//label or .//span[contains(@class,'label')]) and (.//input or .//textarea)]"

    @staticmethod
    def _extract_xpath_from_llm_response(text: str) -> Optional[str]:
        """Extract the first valid XPath expression from a possibly verbose LLM response."""
        text = text.strip()

        # If the entire response is a clean xpath, use it directly
        if re.match(r'^//[a-zA-Z]', text) and '\n' not in text and len(text) < 200:
            return text

        # Look for xpath patterns in the response (// followed by tag and optional predicates)
        xpath_pattern = re.compile(r'(//[a-zA-Z][\w*]*(?:\[.+?\])*(?:/[a-zA-Z][\w*]*(?:\[.+?\])*)*)')
        matches = xpath_pattern.findall(text)
        if matches:
            # Return the first match that looks reasonable
            for match in matches:
                if len(match) < 300:
                    return match

        # Try CSS-style selectors as fallback
        css_pattern = re.compile(r'([a-zA-Z][\w-]*(?:\.[a-zA-Z][\w-]*)+)')
        css_matches = css_pattern.findall(text)
        if css_matches:
            return css_matches[0]

        return None
    
    async def _find_elements_with_selector(self, selector: str) -> List[Any]:
        """Find elements using the resolved selector."""
        try:
            from lamia.internal_types import BrowserActionParams
            params = BrowserActionParams(selector=selector)
            elements = await self.browser.get_elements(params)
            return elements or []
        except Exception as e:
            logger.warning(f"Failed to find elements with selector '{selector}': {e}")
            return []
    
    async def _validate_result(
        self, 
        method_name: str, 
        description: str, 
        elements: List[Any], 
        is_plural: bool
    ) -> None:
        """Validate that the selection result makes sense."""
        
        element_count = len(elements)
        
        if element_count == 0:
            raise ValueError(f"Visual selection for '{description}' found no elements")
        
        if is_plural and element_count == 1:
            # Warn but allow for plural methods
            logger.warning(f"get_elements('{description}') found only 1 element. Consider using get_element() for single elements.")
            
            # Could show user warning here in the future
            await self._show_single_element_warning(description)
        
        # Method-specific validations
        if method_name in ['click', 'hover'] and element_count > 1:
            raise ValueError(f"Selection for {method_name}('{description}') is ambiguous - found {element_count} elements")
    
    async def _show_single_element_warning(self, description: str) -> None:
        """Show warning when plural method finds only one element."""
        # For now just log, could enhance with UI notification
        logger.warning(f"⚠️ get_elements('{description}') found only 1 element")
    
    async def _use_cached_selection(self, cached: Dict[str, Any]) -> Tuple[str, List[Any]]:
        """Use a cached visual selection."""
        selection_data = cached.get('selection_data', {})
        selector = selection_data.get('selector', '')
        
        # Re-find elements (page might have changed)
        elements = await self._find_elements_with_selector(selector)
        
        if not elements:
            # Cache is stale, need to re-select
            logger.warning("Cached visual selection found no elements - cache may be stale")
            raise ValueError("Cached selection no longer valid")
        
        return selector, elements