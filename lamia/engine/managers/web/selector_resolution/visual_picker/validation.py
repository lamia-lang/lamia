"""Selection validation for visual element picker."""

import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


class SelectionValidator:
    """
    Validates visual element selections to ensure they make sense for the requested operation.
    """
    
    def __init__(self):
        """Initialize the selection validator."""
        pass
    
    def validate_selection_for_method(
        self, 
        method_name: str, 
        description: str,
        selected_element: Dict[str, Any],
        found_elements: List[Any]
    ) -> Tuple[bool, str]:
        """
        Validate that the selection is appropriate for the web method.
        
        Args:
            method_name: Web method name (click, type_text, etc.)
            description: Natural language description
            selected_element: Information about the selected element
            found_elements: List of elements found with generated selector
            
        Returns:
            (is_valid, error_message) tuple
        """
        element_count = len(found_elements)
        
        # Check basic element count requirements
        if element_count == 0:
            return False, f"No elements found for '{description}'"
        
        # Method-specific validations
        validation_result = self._validate_by_method(method_name, selected_element, element_count)
        if not validation_result[0]:
            return validation_result
        
        # Element-specific validations
        return self._validate_element_properties(method_name, selected_element)
    
    def _validate_by_method(
        self, 
        method_name: str, 
        selected_element: Dict[str, Any], 
        element_count: int
    ) -> Tuple[bool, str]:
        """Validate selection based on web method requirements."""
        
        # Singular methods - should find exactly one element (or warn about multiple)
        singular_methods = ['click', 'type_text', 'get_element', 'hover', 'wait_for', 'select_option', 'upload_file']
        
        if method_name in singular_methods:
            if element_count > 1:
                return False, f"{method_name}('{selected_element.get('description', '')}') is ambiguous - found {element_count} elements. Please select a more specific area."
        
        # Plural methods - multiple elements expected
        elif method_name == 'get_elements':
            if element_count == 1:
                # This is valid but worth a warning (handled elsewhere)
                logger.info(f"get_elements found only 1 element - this is valid but unusual")
        
        return True, ""
    
    def _validate_element_properties(
        self, 
        method_name: str, 
        selected_element: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Validate that the selected element has appropriate properties for the method."""
        
        tag_name = selected_element.get('tagName', '').upper()
        attributes = selected_element.get('attributes', {})
        is_visible = selected_element.get('isVisible', True)
        is_clickable = selected_element.get('isClickable', False)
        
        # Visibility check for most methods
        if method_name not in ['wait_for'] and not is_visible:
            return False, f"Selected element is not visible - {method_name} requires visible elements"
        
        # Method-specific property validations
        if method_name == 'click':
            return self._validate_clickable_element(tag_name, attributes, is_clickable)
        
        elif method_name == 'type_text':
            return self._validate_input_element(tag_name, attributes)
        
        elif method_name == 'select_option':
            return self._validate_select_element(tag_name, attributes)
        
        elif method_name == 'upload_file':
            return self._validate_file_input(tag_name, attributes)
        
        elif method_name == 'hover':
            return self._validate_hoverable_element(tag_name, attributes, is_visible)
        
        # For other methods (get_element, get_elements, wait_for), any element is fine
        return True, ""
    
    def _validate_clickable_element(
        self, 
        tag_name: str, 
        attributes: Dict[str, str], 
        is_clickable: bool
    ) -> Tuple[bool, str]:
        """Validate element is clickable."""
        
        clickable_tags = ['BUTTON', 'A', 'INPUT']
        clickable_types = ['button', 'submit', 'reset']
        clickable_roles = ['button', 'link', 'tab']
        
        # Check tag name
        if tag_name in clickable_tags:
            # For INPUT, check type
            if tag_name == 'INPUT':
                input_type = attributes.get('type', '').lower()
                if input_type not in clickable_types:
                    return False, f"Selected input element has type '{input_type}' which is not clickable"
            return True, ""
        
        # Check role attribute
        role = attributes.get('role', '').lower()
        if role in clickable_roles:
            return True, ""
        
        # Check if JavaScript detected it as clickable
        if is_clickable:
            return True, ""
        
        return False, "Selected element does not appear to be clickable"
    
    def _validate_input_element(
        self, 
        tag_name: str, 
        attributes: Dict[str, str]
    ) -> Tuple[bool, str]:
        """Validate element accepts text input."""
        
        # Check for standard input elements
        if tag_name == 'TEXTAREA':
            return True, ""
        
        if tag_name == 'INPUT':
            input_type = attributes.get('type', 'text').lower()
            text_input_types = ['text', 'email', 'password', 'search', 'url', 'tel']
            
            if input_type in text_input_types:
                return True, ""
            else:
                return False, f"Selected input element has type '{input_type}' which doesn't accept text"
        
        # Check for contenteditable elements
        content_editable = attributes.get('contenteditable', '').lower()
        if content_editable == 'true':
            return True, ""
        
        return False, "Selected element is not a text input field"
    
    def _validate_select_element(
        self, 
        tag_name: str, 
        attributes: Dict[str, str]
    ) -> Tuple[bool, str]:
        """Validate element is a select dropdown."""
        
        if tag_name == 'SELECT':
            return True, ""
        
        # Check for custom dropdowns with role
        role = attributes.get('role', '').lower()
        if role in ['combobox', 'listbox']:
            return True, ""
        
        return False, "Selected element is not a select dropdown"
    
    def _validate_file_input(
        self, 
        tag_name: str, 
        attributes: Dict[str, str]
    ) -> Tuple[bool, str]:
        """Validate element is a file input."""
        
        if tag_name == 'INPUT' and attributes.get('type', '').lower() == 'file':
            return True, ""
        
        return False, "Selected element is not a file input"
    
    def _validate_hoverable_element(
        self, 
        tag_name: str, 
        attributes: Dict[str, str], 
        is_visible: bool
    ) -> Tuple[bool, str]:
        """Validate element can be hovered."""
        
        # Most visible elements can be hovered
        if is_visible:
            return True, ""
        
        return False, "Selected element is not visible for hovering"
    
    def validate_element_count_for_description(
        self, 
        description: str, 
        element_count: int, 
        is_plural_method: bool
    ) -> List[str]:
        """
        Generate warnings about element count vs description expectations.
        
        Args:
            description: Natural language description
            element_count: Number of elements found
            is_plural_method: Whether this is a plural method (get_elements)
            
        Returns:
            List of warning messages
        """
        warnings = []
        
        # Parse description for count hints
        desc_lower = description.lower()
        
        # Check for explicit count expectations
        if 'one ' in desc_lower or 'single ' in desc_lower:
            if element_count > 1:
                warnings.append(f"Description mentions 'one' or 'single' but found {element_count} elements")
        
        elif 'two ' in desc_lower or 'pair ' in desc_lower:
            if element_count != 2:
                warnings.append(f"Description mentions 'two' or 'pair' but found {element_count} elements")
        
        elif any(word in desc_lower for word in ['multiple', 'several', 'many', 'all']):
            if element_count == 1:
                warnings.append(f"Description suggests multiple elements but found only 1")
        
        # Check method vs count mismatch
        if is_plural_method and element_count == 1:
            warnings.append("get_elements() found only 1 element - consider using get_element() instead")
        
        elif not is_plural_method and element_count > 1:
            warnings.append(f"Singular method found {element_count} elements - this may be ambiguous")
        
        return warnings