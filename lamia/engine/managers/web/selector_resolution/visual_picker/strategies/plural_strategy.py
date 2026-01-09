"""Selection strategy for plural web methods (get_elements)."""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class PluralSelectionStrategy:
    """
    Handles element selection for methods that expect multiple elements.
    
    Methods: get_elements
    
    Features:
    - Progressive scope expansion if no elements found
    - Warning if only one element found
    - Container-focused selection approach
    """
    
    def __init__(self, picker, ui):
        """Initialize plural selection strategy.
        
        Args:
            picker: VisualElementPicker instance
            ui: UI overlay manager
        """
        self.picker = picker
        self.ui = ui
        self._last_working_selector = None
    
    async def handle_selection(self, method_name: str, description: str) -> Dict[str, Any]:
        """
        Handle element selection for a plural method.
        
        Args:
            method_name: Web method name (should be 'get_elements')
            description: Natural language description of elements
            
        Returns:
            Selection result dictionary
        """
        logger.info(f"Handling plural selection for {method_name}('{description}')")
        
        if method_name != 'get_elements':
            logger.warning(f"Plural strategy called for non-plural method: {method_name}")
        
        instruction = f"🔢 Click on ONE example of: '{description}'"
        
        # Show picker for individual element selection (we'll use it as a template)
        result = await self.picker.overlay.pick_single_element(
            instruction=instruction + "\\n(We'll find other similar elements based on your selection)"
        )
        
        # Handle the result based on what was found
        return await self._handle_plural_result(result, description)
    
    async def _handle_plural_result(self, result: Dict[str, Any], description: str) -> Dict[str, Any]:
        """Handle the result from individual element selection (used as template)."""
        
        # Use the selected element as a template to find similar elements
        logger.info("Using selected element as template to find similar elements")
        
        try:
            # Generate selectors based on the template element
            similar_elements = await self._find_similar_elements(result, description)
            found_count = len(similar_elements) if similar_elements else 0
            
            logger.info(f"Found {found_count} similar elements using template approach")
            
            if found_count >= 2:
                # Success! Found multiple similar elements
                await self._show_template_success(found_count, description)
                return {
                    'selected_element': result.get('selected_element'),
                    'selection_type': 'template',
                    'found_elements': similar_elements,
                    'element_count': found_count,
                    'working_selector': self._last_working_selector  # Store the working selector
                }
            elif found_count == 1:
                # Only found the original element
                await self._show_template_warning_single(description)
                return result
            else:
                # No similar elements found
                await self._show_template_warning_none(description)
                return result
                
        except Exception as e:
            logger.error(f"Template-based element finding failed: {e}")
            return result
    
    async def _find_similar_elements(self, template_result: Dict[str, Any], description: str) -> List[Any]:
        """Find elements similar to the template element."""
        
        template_element = template_result.get('selected_element', {})
        tag_name = template_element.get('tagName', '').lower()
        class_name = template_element.get('className', '')
        element_type = template_element.get('type', '')
        
        logger.debug(f"Template element: {tag_name}, class: {class_name}, type: {element_type}")
        
        # Generate candidate selectors based on template element attributes
        candidate_selectors = []
        
        # Strategy 1: Same tag and class
        if tag_name and class_name:
            candidate_selectors.append(f"{tag_name}.{class_name.replace(' ', '.')}")
        
        # Strategy 2: Same tag and type (for inputs)
        if tag_name == 'input' and element_type:
            candidate_selectors.append(f"input[type='{element_type}']")
        
        # Strategy 3: Same tag with similar class patterns
        if tag_name and class_name:
            # Extract class patterns (e.g., 'artdeco-text-input' from class list)
            class_parts = class_name.split()
            for class_part in class_parts:
                if len(class_part) > 5:  # Meaningful class names
                    candidate_selectors.append(f"{tag_name}[class*='{class_part}']")
        
        # Strategy 4: Same tag only
        if tag_name:
            candidate_selectors.append(tag_name)
        
        # Try each selector and return the first one that finds multiple elements
        for selector in candidate_selectors:
            try:
                elements = await self._test_selector(selector)
                if elements and len(elements) >= 2:
                    logger.info(f"Found {len(elements)} elements with selector: {selector}")
                    self._last_working_selector = selector  # Store the working selector
                    return elements
            except Exception as e:
                logger.debug(f"Selector '{selector}' failed: {e}")
                continue
        
        logger.warning("No selector found multiple similar elements")
        return []
    
    async def _test_selector(self, selector: str) -> List[Any]:
        """Test a selector and return found elements."""
        from lamia.internal_types import BrowserActionParams
        
        try:
            # Get browser adapter from picker overlay
            browser = self.picker.overlay.browser
            params = BrowserActionParams(selector=selector)
            elements = await browser.get_elements(params)
            return elements if elements else []
        except Exception as e:
            logger.debug(f"Selector test failed for '{selector}': {e}")
            return []
    
    async def _show_template_success(self, count: int, description: str):
        """Show success message for template selection."""
        await self.ui.show_user_message(
            title="Template Selection Successful!",
            message=f"Found {count} elements similar to your selection for '{description}'",
            timeout=3
        )
    
    async def _show_template_warning_single(self, description: str):
        """Show warning when only one element found."""
        await self.ui.show_user_message(
            title="Only One Element Found",
            message=f"Only found the element you selected for '{description}'. No similar elements detected.",
            timeout=4
        )
    
    async def _show_template_warning_none(self, description: str):
        """Show warning when no similar elements found."""
        await self.ui.show_user_message(
            title="No Similar Elements Found", 
            message=f"Could not find elements similar to your selection for '{description}'",
            timeout=4
        )
    
    async def _find_elements_in_container(
        self, 
        container_result: Dict[str, Any], 
        description: str
    ) -> Optional[List[Any]]:
        """
        Find elements matching description within the selected container.
        
        This is a preview to see how many elements would be found.
        """
        try:
            # Generate a simple scoped selector for preview
            selected_element = container_result.get('selected_element', {})
            container_xpath = selected_element.get('xpath', '')
            
            if not container_xpath:
                return None
            
            # Create a basic scoped selector for preview
            # In real implementation, this would use the full AI selector generation
            preview_selectors = [
                f"{container_xpath}//*[contains(@placeholder, '{description.split()[0]}')]",
                f"{container_xpath}//input",
                f"{container_xpath}//button", 
                f"{container_xpath}//*"
            ]
            
            from lamia.internal_types import BrowserActionParams
            
            # Try each preview selector
            for selector in preview_selectors:
                try:
                    params = BrowserActionParams(selector=selector)
                    elements = await self.picker.browser.get_elements(params)
                    if elements:
                        return elements
                except Exception:
                    continue
            
            return []
            
        except Exception as e:
            logger.warning(f"Failed to preview elements in container: {e}")
            return None
    
    async def _try_progressive_expansion(
        self, 
        result: Dict[str, Any], 
        description: str
    ) -> Dict[str, Any]:
        """Try progressively expanding scope if no elements found."""
        
        selected_element = result.get('selected_element', {})
        
        for level in range(1, 4):  # Try 3 levels up
            logger.info(f"Trying scope expansion level {level}")
            
            try:
                # Expand scope by going up parent levels
                expanded_element = await self.picker.overlay.expand_scope(selected_element, level)
                
                # Check if expanded scope contains elements
                expanded_result = {
                    'selected_element': expanded_element,
                    'selection_type': 'container_expanded',
                    'expansion_level': level
                }
                
                elements = await self._find_elements_in_container(expanded_result, description)
                element_count = len(elements) if elements else 0
                
                if element_count > 0:
                    # Ask user if they want to use this expanded scope
                    use_expanded = await self._ask_user_expand_scope(level, element_count, description)
                    
                    if use_expanded:
                        logger.info(f"Using expanded scope (level {level}) with {element_count} elements")
                        await self._show_scope_expanded_success(level, element_count)
                        return expanded_result
                
            except Exception as e:
                logger.warning(f"Failed to expand scope at level {level}: {e}")
                continue
        
        # No suitable scope found
        await self._show_no_elements_error(description)
        raise ValueError(f"No elements found for '{description}' even with expanded scope")
    
    async def _ask_user_expand_scope(
        self, 
        level: int, 
        element_count: int, 
        description: str
    ) -> bool:
        """Ask user if they want to use expanded scope."""
        
        # For now, auto-accept if we found multiple elements
        # In future, could show actual UI dialog
        if element_count > 1:
            logger.info(f"Auto-accepting scope expansion: found {element_count} elements at level {level}")
            return True
        
        # For single element, ask user preference
        logger.info(f"Found {element_count} element at expansion level {level}, using it")
        return True
    
    async def _show_single_element_warning(self, description: str) -> None:
        """Show warning when plural method finds only one element."""
        
        warning_message = (
            f"get_elements('{description}') found only 1 element.\n\n"
            "Consider using get_element() for single elements.\n\n"
            "This is still valid - continuing..."
        )
        
        try:
            await self.picker.overlay.show_user_message(
                title="Single Element Found",
                message=warning_message,
                timeout=4
            )
        except Exception as e:
            logger.warning(f"Failed to show single element warning: {e}")
        
        logger.warning(f"⚠️ get_elements('{description}') found only 1 element")
    
    async def _show_multiple_found_success(self, count: int, description: str) -> None:
        """Show success message when multiple elements found."""
        
        success_message = f"✅ Found {count} elements for '{description}'"
        
        try:
            await self.picker.overlay.show_user_message(
                title="Multiple Elements Found",
                message=success_message,
                timeout=2
            )
        except Exception as e:
            logger.warning(f"Failed to show success message: {e}")
        
        logger.info(f"Successfully found {count} elements for get_elements('{description}')")
    
    async def _show_scope_expanded_success(self, level: int, count: int) -> None:
        """Show message when scope expansion finds elements."""
        
        success_message = (
            f"✅ Expanded scope by {level} level(s)\n\n"
            f"Found {count} elements in broader area"
        )
        
        try:
            await self.picker.overlay.show_user_message(
                title="Scope Expanded",
                message=success_message,
                timeout=3
            )
        except Exception as e:
            logger.warning(f"Failed to show scope expansion success: {e}")
        
        logger.info(f"Scope expansion successful: {count} elements found at level {level}")
    
    async def _show_no_elements_error(self, description: str) -> None:
        """Show error when no elements found even with expansion."""
        
        error_message = (
            f"❌ No elements found for '{description}'\n\n"
            "Tried expanding scope but still found nothing.\n\n"
            "Please try selecting a different area or use a more specific description."
        )
        
        try:
            await self.picker.overlay.show_user_message(
                title="No Elements Found",
                message=error_message,
                timeout=6
            )
        except Exception as e:
            logger.warning(f"Failed to show no elements error: {e}")
        
        logger.error(f"No elements found for get_elements('{description}') even with scope expansion")