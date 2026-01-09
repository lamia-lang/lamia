"""Action-specific selection handlers for visual picker."""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ActionSelectionHandler:
    """
    Handles method-specific selection logic and validation.
    
    Provides specialized behavior for different web action types
    beyond the basic singular/plural distinction.
    """
    
    def __init__(self, picker, ui):
        """Initialize action selection handler.
        
        Args:
            picker: VisualElementPicker instance
            ui: UI overlay manager
        """
        self.picker = picker
        self.ui = ui
    
    async def handle_click_selection(self, description: str) -> Dict[str, Any]:
        """Handle selection for click actions with enhanced validation."""
        
        instruction = f"👆 Click on the element you want to CLICK: '{description}'"
        
        # Use click-specific element filter
        element_filter = '''
            function(el) {
                // Highlight clickable elements with better detection
                if (el.tagName === 'BUTTON' || el.tagName === 'A') return true;
                
                if (el.tagName === 'INPUT') {
                    return ['submit', 'button', 'reset'].includes(el.type);
                }
                
                var role = el.getAttribute('role');
                if (['button', 'link', 'tab', 'menuitem'].includes(role)) return true;
                
                // Check for click handlers
                if (el.onclick !== null) return true;
                
                // Check computed styles
                var style = window.getComputedStyle(el);
                if (style.cursor === 'pointer') return true;
                
                // Check for data attributes that suggest clickability
                var attrs = el.attributes;
                for (var i = 0; i < attrs.length; i++) {
                    var name = attrs[i].name;
                    if (name.includes('click') || name.includes('action') || name.includes('handler')) {
                        return true;
                    }
                }
                
                return false;
            }
        '''
        
        result = await self.picker.overlay.pick_single_element(
            instruction=instruction,
            element_filter=element_filter
        )
        
        # Enhanced click validation
        await self._validate_click_element(result, description)
        
        return result
    
    async def handle_type_text_selection(self, description: str) -> Dict[str, Any]:
        """Handle selection for text input actions."""
        
        instruction = f"⌨️ Click on the input field for typing: '{description}'"
        
        # Text input specific filter
        element_filter = '''
            function(el) {
                // Text input elements
                if (el.tagName === 'TEXTAREA') return true;
                
                if (el.tagName === 'INPUT') {
                    var type = el.type.toLowerCase();
                    return ['text', 'email', 'password', 'search', 'url', 'tel', 'number'].includes(type);
                }
                
                // Contenteditable elements
                if (el.contentEditable === 'true') return true;
                
                // Role-based input detection
                var role = el.getAttribute('role');
                if (['textbox', 'searchbox'].includes(role)) return true;
                
                return false;
            }
        '''
        
        result = await self.picker.overlay.pick_single_element(
            instruction=instruction,
            element_filter=element_filter
        )
        
        # Enhanced input validation
        await self._validate_input_element(result, description)
        
        return result
    
    async def handle_select_option_selection(self, description: str) -> Dict[str, Any]:
        """Handle selection for dropdown/select actions."""
        
        instruction = f"📋 Click on the dropdown/select element: '{description}'"
        
        # Select element filter
        element_filter = '''
            function(el) {
                // Standard select elements
                if (el.tagName === 'SELECT') return true;
                
                // Custom dropdowns
                var role = el.getAttribute('role');
                if (['combobox', 'listbox', 'menu'].includes(role)) return true;
                
                // Dropdown indicators by class/attributes
                var className = el.className.toLowerCase();
                var attrs = el.attributes;
                
                if (className.includes('dropdown') || className.includes('select')) return true;
                
                for (var i = 0; i < attrs.length; i++) {
                    var name = attrs[i].name.toLowerCase();
                    var value = attrs[i].value.toLowerCase();
                    if (name.includes('dropdown') || value.includes('dropdown') ||
                        name.includes('select') || value.includes('select')) {
                        return true;
                    }
                }
                
                return false;
            }
        '''
        
        result = await self.picker.overlay.pick_single_element(
            instruction=instruction,
            element_filter=element_filter
        )
        
        # Enhanced select validation
        await self._validate_select_element(result, description)
        
        return result
    
    async def handle_upload_file_selection(self, description: str) -> Dict[str, Any]:
        """Handle selection for file upload actions."""
        
        instruction = f"📁 Click on the file input element: '{description}'"
        
        # File input filter
        element_filter = '''
            function(el) {
                // File input elements
                if (el.tagName === 'INPUT' && el.type === 'file') return true;
                
                // Custom file upload components
                var className = el.className.toLowerCase();
                var attrs = el.attributes;
                
                if (className.includes('file') || className.includes('upload')) return true;
                
                for (var i = 0; i < attrs.length; i++) {
                    var name = attrs[i].name.toLowerCase();
                    var value = attrs[i].value.toLowerCase();
                    if (name.includes('file') || value.includes('file') ||
                        name.includes('upload') || value.includes('upload')) {
                        return true;
                    }
                }
                
                return false;
            }
        '''
        
        result = await self.picker.overlay.pick_single_element(
            instruction=instruction,
            element_filter=element_filter
        )
        
        # Enhanced file input validation
        await self._validate_file_input_element(result, description)
        
        return result
    
    async def _validate_click_element(self, result: Dict[str, Any], description: str) -> None:
        """Enhanced validation for click elements."""
        
        element_info = result.get('selected_element', {})
        tag_name = element_info.get('tagName', '').upper()
        attributes = element_info.get('attributes', {})
        is_visible = element_info.get('isVisible', True)
        
        # Check visibility
        if not is_visible:
            await self._show_validation_error(
                "Click Element Not Visible",
                f"Selected element for '{description}' is not visible.\n\nPlease select a visible clickable element."
            )
            raise ValueError("Click element is not visible")
        
        # Check if element might be disabled
        is_disabled = attributes.get('disabled') == 'true' or attributes.get('aria-disabled') == 'true'
        if is_disabled:
            await self._show_validation_warning(
                "Element May Be Disabled",
                f"Selected element for '{description}' appears to be disabled.\n\nThis might cause click failures."
            )
        
        # Check for common non-clickable elements
        non_clickable_tags = ['DIV', 'SPAN', 'P', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6']
        if tag_name in non_clickable_tags and not element_info.get('isClickable', False):
            await self._show_validation_warning(
                "Element May Not Be Clickable", 
                f"Selected {tag_name.lower()} element might not be clickable.\n\nConsider selecting a button, link, or interactive element instead."
            )
    
    async def _validate_input_element(self, result: Dict[str, Any], description: str) -> None:
        """Enhanced validation for input elements."""
        
        element_info = result.get('selected_element', {})
        tag_name = element_info.get('tagName', '').upper()
        attributes = element_info.get('attributes', {})
        
        # Check if element is readonly
        is_readonly = attributes.get('readonly') == 'true' or attributes.get('readonly') == ''
        if is_readonly:
            await self._show_validation_error(
                "Input Field Is Read-Only",
                f"Selected input for '{description}' is read-only.\n\nPlease select an editable input field."
            )
            raise ValueError("Input element is readonly")
        
        # Check for placeholder text that might give hints
        placeholder = attributes.get('placeholder', '')
        if placeholder and description.lower() not in placeholder.lower():
            await self._show_validation_info(
                "Input Field Context",
                f"Selected input has placeholder: '{placeholder}'\n\nMake sure this matches your intent for '{description}'"
            )
    
    async def _validate_select_element(self, result: Dict[str, Any], description: str) -> None:
        """Enhanced validation for select elements."""
        
        element_info = result.get('selected_element', {})
        tag_name = element_info.get('tagName', '').upper()
        
        if tag_name != 'SELECT':
            await self._show_validation_warning(
                "Custom Dropdown Detected",
                f"Selected element for '{description}' is not a standard <select>.\n\nThis might require different interaction methods."
            )
    
    async def _validate_file_input_element(self, result: Dict[str, Any], description: str) -> None:
        """Enhanced validation for file input elements."""
        
        element_info = result.get('selected_element', {})
        tag_name = element_info.get('tagName', '').upper()
        attributes = element_info.get('attributes', {})
        
        if tag_name != 'INPUT' or attributes.get('type', '').lower() != 'file':
            await self._show_validation_error(
                "Not A File Input",
                f"Selected element for '{description}' is not a file input.\n\nPlease select an <input type='file'> element."
            )
            raise ValueError("Element is not a file input")
        
        # Check for file type restrictions
        accept = attributes.get('accept', '')
        if accept:
            await self._show_validation_info(
                "File Type Restrictions",
                f"This file input accepts: {accept}\n\nMake sure your file matches these requirements."
            )
    
    async def _show_validation_error(self, title: str, message: str) -> None:
        """Show validation error to user."""
        try:
            await self.picker.overlay.show_user_message(
                title=title,
                message=message,
                timeout=8
            )
        except Exception as e:
            logger.warning(f"Failed to show validation error: {e}")
    
    async def _show_validation_warning(self, title: str, message: str) -> None:
        """Show validation warning to user."""
        try:
            await self.picker.overlay.show_user_message(
                title=title,
                message=message,
                timeout=5
            )
        except Exception as e:
            logger.warning(f"Failed to show validation warning: {e}")
    
    async def _show_validation_info(self, title: str, message: str) -> None:
        """Show validation info to user."""
        try:
            await self.picker.overlay.show_user_message(
                title=title,
                message=message,
                timeout=4
            )
        except Exception as e:
            logger.warning(f"Failed to show validation info: {e}")