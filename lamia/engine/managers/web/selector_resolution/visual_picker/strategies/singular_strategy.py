"""Selection strategy for singular web methods (get_element, click, type_text, etc.)."""

import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


class SingularSelectionStrategy:
    """
    Handles element selection for methods that expect a single element.
    
    Methods: click, type_text, get_element, hover, wait_for, select_option, upload_file
    """
    
    def __init__(self, picker, ui):
        """Initialize singular selection strategy.
        
        Args:
            picker: VisualElementPicker instance
            ui: UI overlay manager
        """
        self.picker = picker
        self.ui = ui
    
    async def handle_selection(self, method_name: str, description: str) -> Dict[str, Any]:
        """
        Handle element selection for a singular method.
        
        Args:
            method_name: Web method name (click, get_element, etc.)
            description: Natural language description of element
            
        Returns:
            Selection result dictionary
        """
        logger.info(f"Handling singular selection for {method_name}('{description}')")
        
        instruction = self._get_instruction(method_name, description)
        validation_rules = self._get_validation_rules(method_name)
        element_filter = self._get_element_filter(method_name)
        
        # Show picker for single element selection
        selected = await self.picker.overlay.pick_single_element(
            instruction=instruction,
            element_filter=element_filter
        )
        
        if not selected:
            raise ValueError(f"No element selected for {method_name}")
        
        # Validate the selection is appropriate
        await self._validate_selection(method_name, description, selected, validation_rules)
        
        logger.info(f"Singular selection completed for {method_name}")
        return selected
    
    def _get_instruction(self, method: str, desc: str) -> str:
        """Get user instruction text for the method."""
        
        instructions = {
            'click': f"👆 Click on the element you want to CLICK: '{desc}'",
            'type_text': f"⌨️ Click on the input field for typing: '{desc}'", 
            'get_element': f"🎯 Click on the element: '{desc}'",
            'hover': f"🖱️ Click on the element to hover over: '{desc}'",
            'wait_for': f"⏳ Click on the element to wait for: '{desc}'",
            'select_option': f"📋 Click on the dropdown/select element: '{desc}'",
            'upload_file': f"📁 Click on the file input element: '{desc}'"
        }
        
        return instructions.get(method, f"🎯 Select element for {method}: '{desc}'")
    
    def _get_validation_rules(self, method: str) -> List[str]:
        """Get validation rules for the method."""
        
        rules = {
            'click': ['clickable', 'visible'],
            'type_text': ['input', 'editable', 'visible'],
            'get_element': ['exists'],
            'hover': ['visible'],
            'wait_for': ['exists'],  # Don't require visible for wait_for
            'select_option': ['select', 'visible'],
            'upload_file': ['file_input', 'visible']
        }
        
        return rules.get(method, ['exists'])
    
    def _get_element_filter(self, method: str) -> str:
        """Get JavaScript element filter function for method-specific highlighting."""
        
        filters = {
            'click': '''
                function(el) {
                    // Highlight clickable elements
                    return el.tagName === 'BUTTON' || 
                           el.tagName === 'A' || 
                           el.getAttribute('role') === 'button' ||
                           el.onclick !== null ||
                           (el.tagName === 'INPUT' && ['submit', 'button'].includes(el.type)) ||
                           el.style.cursor === 'pointer';
                }
            ''',
            'type_text': '''
                function(el) {
                    // Highlight text input elements
                    return (el.tagName === 'INPUT' && 
                            ['text', 'email', 'password', 'search', 'url', 'tel'].includes(el.type)) ||
                           el.tagName === 'TEXTAREA' ||
                           el.contentEditable === 'true';
                }
            ''',
            'select_option': '''
                function(el) {
                    // Highlight select elements
                    return el.tagName === 'SELECT' ||
                           el.getAttribute('role') === 'combobox' ||
                           el.getAttribute('role') === 'listbox';
                }
            ''',
            'upload_file': '''
                function(el) {
                    // Highlight file input elements
                    return el.tagName === 'INPUT' && el.type === 'file';
                }
            '''
        }
        
        return filters.get(method, None)  # No filter for generic methods
    
    async def _validate_selection(
        self, 
        method_name: str, 
        description: str, 
        selected: Dict[str, Any], 
        validation_rules: List[str]
    ) -> None:
        """Validate that the selection is appropriate for the method."""
        
        selected_element = selected.get('selected_element', {})
        tag_name = selected_element.get('tagName', '').upper()
        attributes = selected_element.get('attributes', {})
        
        # Run validation rules
        for rule in validation_rules:
            is_valid, error_msg = self._check_validation_rule(
                rule, tag_name, attributes, selected_element
            )
            
            if not is_valid:
                # Show user-friendly error
                await self._show_validation_error(method_name, description, error_msg)
                raise ValueError(f"Invalid selection for {method_name}: {error_msg}")
    
    def _check_validation_rule(
        self, 
        rule: str, 
        tag_name: str, 
        attributes: Dict[str, str], 
        element_info: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Check a specific validation rule."""
        
        if rule == 'clickable':
            return self._is_clickable(tag_name, attributes, element_info)
        
        elif rule == 'input' or rule == 'editable':
            return self._is_text_input(tag_name, attributes)
        
        elif rule == 'visible':
            is_visible = element_info.get('isVisible', True)
            return is_visible, "Element is not visible"
        
        elif rule == 'select':
            return self._is_select_element(tag_name, attributes)
        
        elif rule == 'file_input':
            return self._is_file_input(tag_name, attributes)
        
        elif rule == 'exists':
            return True, ""  # If we got here, element exists
        
        else:
            logger.warning(f"Unknown validation rule: {rule}")
            return True, ""
    
    def _is_clickable(
        self, 
        tag_name: str, 
        attributes: Dict[str, str], 
        element_info: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Check if element is clickable."""
        
        clickable_tags = ['BUTTON', 'A']
        if tag_name in clickable_tags:
            return True, ""
        
        if tag_name == 'INPUT':
            input_type = attributes.get('type', '').lower()
            if input_type in ['button', 'submit', 'reset']:
                return True, ""
            else:
                return False, f"Input type '{input_type}' is not clickable"
        
        # Check role attribute
        role = attributes.get('role', '').lower()
        if role in ['button', 'link', 'tab']:
            return True, ""
        
        # Check if JavaScript detected it as clickable
        if element_info.get('isClickable', False):
            return True, ""
        
        return False, "Element does not appear to be clickable"
    
    def _is_text_input(self, tag_name: str, attributes: Dict[str, str]) -> Tuple[bool, str]:
        """Check if element accepts text input."""
        
        if tag_name == 'TEXTAREA':
            return True, ""
        
        if tag_name == 'INPUT':
            input_type = attributes.get('type', 'text').lower()
            text_types = ['text', 'email', 'password', 'search', 'url', 'tel']
            if input_type in text_types:
                return True, ""
            else:
                return False, f"Input type '{input_type}' doesn't accept text"
        
        # Check contenteditable
        if attributes.get('contenteditable', '').lower() == 'true':
            return True, ""
        
        return False, "Element is not a text input"
    
    def _is_select_element(self, tag_name: str, attributes: Dict[str, str]) -> Tuple[bool, str]:
        """Check if element is a select dropdown."""
        
        if tag_name == 'SELECT':
            return True, ""
        
        role = attributes.get('role', '').lower()
        if role in ['combobox', 'listbox']:
            return True, ""
        
        return False, "Element is not a select dropdown"
    
    def _is_file_input(self, tag_name: str, attributes: Dict[str, str]) -> Tuple[bool, str]:
        """Check if element is a file input."""
        
        if tag_name == 'INPUT' and attributes.get('type', '').lower() == 'file':
            return True, ""
        
        return False, "Element is not a file input"
    
    async def _show_validation_error(self, method_name: str, description: str, error_msg: str) -> None:
        """Show validation error to user."""
        
        error_title = f"Invalid Selection for {method_name}()"
        error_message = f"'{description}'\n\n{error_msg}\n\nPlease select a different element."
        
        try:
            await self.picker.overlay.show_user_message(
                title=error_title,
                message=error_message,
                timeout=8
            )
        except Exception as e:
            logger.warning(f"Failed to show validation error: {e}")
        
        logger.warning(f"Validation failed for {method_name}('{description}'): {error_msg}")