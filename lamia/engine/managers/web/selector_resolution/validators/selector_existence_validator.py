"""Validator for checking if selectors actually find elements on the page."""

import logging
from lamia.validation.validators.base import BaseValidator
from lamia.validation.validators.validation_result import ValidationResult
from lamia.types import BrowserActionParams

logger = logging.getLogger(__name__)


class SelectorExistenceValidator(BaseValidator):
    """Validates that a selector actually finds elements on the current page."""
    
    def __init__(self, browser_adapter):
        """Initialize the validator.
        
        Args:
            browser_adapter: Browser adapter instance for testing selectors
        """
        self.browser_adapter = browser_adapter
    
    async def validate(self, response: str) -> ValidationResult:
        """Test if a selector finds elements on the current page.
        
        Args:
            response: Selector string to test
            
        Returns:
            ValidationResult indicating if selector finds elements
        """
        if not response or not response.strip():
            return ValidationResult(
                is_valid=False,
                parsed_content=None,
                validation_error="Empty selector"
            )
        
        selector = response.strip()
        
        try:
            # Create BrowserActionParams for testing
            test_params = BrowserActionParams(
                selector=selector,
                timeout=2.0  # Short timeout for existence check
            )
            
            # Try to find the element using the adapter's internal method
            element = self.browser_adapter._find_element(test_params)
            
            if element:
                logger.debug(f"Selector '{selector}' found element on page")
                return ValidationResult(
                    is_valid=True,
                    parsed_content=selector,
                    validation_error=None
                )
            else:
                logger.debug(f"Selector '{selector}' found no elements on page")
                return ValidationResult(
                    is_valid=False,
                    parsed_content=None,
                    validation_error=f"Selector '{selector}' found no elements on page"
                )
                
        except Exception as e:
            # Any exception means the selector didn't find elements
            logger.debug(f"Selector '{selector}' validation failed: {e}")
            return ValidationResult(
                is_valid=False,
                parsed_content=None,
                validation_error=f"Selector validation failed: {str(e)}"
            )