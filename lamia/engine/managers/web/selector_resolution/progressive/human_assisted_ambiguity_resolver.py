"""Human-in-the-loop resolver for ambiguous element matches."""

import logging
from typing import List, Any, Optional

from .element_ambiguity_resolver import ElementAmbiguityResolver
from .progressive_selector_strategy import ProgressiveSelectorStrategyIntent, ElementCount

logger = logging.getLogger(__name__)


class HumanAssistedAmbiguityResolver(ElementAmbiguityResolver):
    """
    Handles cases where multiple elements match and user input is needed.
    
    When selectors match more elements than expected, presents options
    to the user and caches their choice for future use.
    """
    
    def __init__(self, browser_adapter: Any, cache: Any, max_display: int = 10):
        """Initialize the human ambiguity resolver.
        
        Args:
            browser_adapter: Browser adapter for element inspection
            cache: AISelectorCache for storing user choices
            max_display: Maximum number of elements to display to user
        """
        self.browser = browser_adapter
        self.cache = cache
        self.max_display = max_display
    
    async def resolve(
        self,
        description: str,
        elements: List[Any],
        intent: ProgressiveSelectorStrategyIntent,
        page_url: str,
    ) -> Optional[List[Any]]:
        """
        Present matched elements to user and get their choice.
        
        Args:
            description: Original element description
            elements: List of element handles that matched
            intent: The parsed intent from the selector strategy
            page_url: Current page URL for caching
            
        Returns:
            List containing the selected element, or None if cancelled
        """
        # Only handle single element selection for now
        if intent.element_count != ElementCount.SINGLE:
            logger.debug("Human resolver only supports single element selection")
            return None
        
        if len(elements) > self.max_display:
            logger.debug(f"Too many elements ({len(elements)}) for human selection")
            return None
        
        logger.info(f"Requesting human input for {len(elements)} ambiguous elements")
        
        try:
            selected = await self._prompt_user_selection(description, elements, page_url)
            return [selected] if selected else None
        except ValueError as e:
            logger.debug(f"Human selection failed: {e}")
            return None
    
    async def _prompt_user_selection(
        self,
        description: str,
        matched_elements: List[Any],
        page_url: str,
    ) -> Optional[Any]:
        """
        Present matched elements to user and get their choice.
        
        Args:
            description: Original element description
            matched_elements: List of element handles that matched
            page_url: Current page URL
            
        Returns:
            Selected element handle, or None if cancelled
            
        Raises:
            ValueError: If user cancels or invalid selection
        """
        print(f"!!! Found {len(matched_elements)} possible matches for: \"{description}\"")
        
        # Show each option
        for i, elem in enumerate(matched_elements, 1):
            try:
                html = await self._get_outer_html(elem)
                xpath = await self._get_xpath(elem)
                location = await self._get_visual_location(elem)
                
                print(f"{i}. {self._truncate_html(html, max_length=100)}")
                print(f"   XPath: {xpath}")
                print(f"   Location: {location}")
                print()
            except Exception as e:
                logger.debug(f"Failed to get details for element {i}: {e}")
                print(f"{i}. <element details unavailable>")
                print()
        
        # Get user choice
        print(f"Which one should I use? (1-{len(matched_elements)}, or 0 to cancel)")
        choice_str = input("Your choice: ").strip()
        
        try:
            choice = int(choice_str)
            
            if choice == 0:
                raise ValueError("User cancelled element selection")
            
            if 1 <= choice <= len(matched_elements):
                selected = matched_elements[choice - 1]
                
                # Generate selector for the chosen element and cache it
                try:
                    selector = await self._generate_selector_for_element(selected)
                    await self.cache.set(description, page_url, selector)
                    logger.info(f"Cached user's choice: '{description}' -> '{selector}'")
                    print(f"\n✓ Selection cached for future use\n")
                except Exception as e:
                    logger.warning(f"Failed to cache user selection: {e}")
                
                return selected
            else:
                raise ValueError(f"Invalid choice: {choice}. Must be 0-{len(matched_elements)}")
        
        except ValueError as e:
            if "invalid literal" in str(e):
                raise ValueError(f"Invalid input: '{choice_str}'. Please enter a number.")
            raise
    
    async def _get_outer_html(self, element: Any) -> str:
        """Get outer HTML of element."""
        try:
            html = await self.browser.execute_script(
                "return arguments[0].outerHTML",
                element
            )
            return html or "<unknown>"
        except Exception as e:
            logger.debug(f"Failed to get outerHTML: {e}")
            return "<unknown>"
    
    async def _get_xpath(self, element: Any) -> str:
        """Generate XPath for element."""
        try:
            xpath = await self.browser.execute_script("""
                function getXPath(element) {
                    if (element.id) {
                        return '//*[@id="' + element.id + '"]';
                    }
                    if (element === document.body) {
                        return '/html/body';
                    }
                    
                    let ix = 0;
                    const siblings = element.parentNode.childNodes;
                    for (let i = 0; i < siblings.length; i++) {
                        const sibling = siblings[i];
                        if (sibling === element) {
                            return getXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                        }
                        if (sibling.nodeType === 1 && sibling.tagName === element.tagName) {
                            ix++;
                        }
                    }
                }
                return getXPath(arguments[0]);
            """, element)
            return xpath or "<unknown>"
        except Exception as e:
            logger.debug(f"Failed to generate XPath: {e}")
            return "<unknown>"
    
    async def _get_visual_location(self, element: Any) -> str:
        """Get human-readable location description."""
        try:
            location_info = await self.browser.execute_script("""
                const rect = arguments[0].getBoundingClientRect();
                const width = window.innerWidth;
                const height = window.innerHeight;
                
                const x = rect.left + rect.width / 2;
                const y = rect.top + rect.height / 2;
                
                let h_pos = 'left';
                if (x > width * 2/3) h_pos = 'right';
                else if (x > width / 3) h_pos = 'center';
                
                let v_pos = 'top';
                if (y > height * 2/3) v_pos = 'bottom';
                else if (y > height / 3) v_pos = 'middle';
                
                return v_pos + ' ' + h_pos;
            """, element)
            return location_info or "unknown"
        except Exception as e:
            logger.debug(f"Failed to get location: {e}")
            return "unknown"
    
    async def _generate_selector_for_element(self, element: Any) -> str:
        """Generate a unique selector for the chosen element."""
        try:
            selector = await self.browser.execute_script("""
                function getUniqueSelector(element) {
                    // Try ID first
                    if (element.id) {
                        return '#' + element.id;
                    }
                    
                    // Try unique class combination
                    if (element.className) {
                        const classes = element.className.split(' ').filter(c => c).join('.');
                        if (classes) {
                            const selector = element.tagName.toLowerCase() + '.' + classes;
                            if (document.querySelectorAll(selector).length === 1) {
                                return selector;
                            }
                        }
                    }
                    
                    // Try nth-child
                    let path = [];
                    let current = element;
                    while (current && current !== document.body) {
                        let selector = current.tagName.toLowerCase();
                        if (current.id) {
                            path.unshift('#' + current.id);
                            break;
                        }
                        
                        let sibling = current;
                        let nth = 1;
                        while (sibling.previousElementSibling) {
                            sibling = sibling.previousElementSibling;
                            if (sibling.tagName === current.tagName) {
                                nth++;
                            }
                        }
                        
                        if (nth > 1 || current.nextElementSibling) {
                            selector += ':nth-of-type(' + nth + ')';
                        }
                        
                        path.unshift(selector);
                        current = current.parentElement;
                    }
                    
                    return path.join(' > ');
                }
                return getUniqueSelector(arguments[0]);
            """, element)
            
            return selector or await self._get_xpath(element)
        except Exception as e:
            logger.debug(f"Failed to generate selector: {e}")
            return await self._get_xpath(element)
    
    def _truncate_html(self, html: str, max_length: int = 100) -> str:
        """Truncate HTML for display."""
        if len(html) <= max_length:
            return html
        return html[:max_length] + "..."

