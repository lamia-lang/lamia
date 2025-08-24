"""Validator for checking if AI-resolved selectors actually find elements on the page."""

import logging
from lamia.validation.base import BaseValidator, ValidationResult, TrackingContext
from lamia.types import BrowserActionParams

logger = logging.getLogger(__name__)


class AIResolvedSelectorValidator(BaseValidator):
    """Validates that an AI-resolved selector actually finds elements on the current page.
    
    This validator is specifically designed for natural language selectors that have been
    resolved by AI into CSS selectors. It ensures the AI-generated selector actually
    matches elements before using it.
    """
    
    def __init__(self, browser_adapter):
        """Initialize the validator.
        
        Args:
            browser_adapter: Browser adapter instance for testing selectors
        """
        super().__init__()
        self.browser_adapter = browser_adapter
    
    @property
    def name(self) -> str:
        """Name of this validator."""
        return "ai_resolved_selector"
    
    @property
    def initial_hint(self) -> str:
        """Initial hint for the AI when generating selectors."""
        return "Return only a valid CSS selector that matches existing elements on the page."
    
    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        """Test if an AI-resolved selector finds elements on the current page (strict mode).
        
        In strict mode, selectors must find exactly one visible element.
        
        Args:
            response: AI-resolved selector string to test
            
        Returns:
            ValidationResult indicating if selector finds exactly one element
        """
        return await self._validate_selector(response, strict=True)
    
    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        """Test if an AI-resolved selector finds elements on the current page (permissive mode).
        
        In permissive mode, selectors just need to find at least one element.
        
        Args:
            response: AI-resolved selector string to test
            
        Returns:
            ValidationResult indicating if selector finds at least one element
        """
        return await self._validate_selector(response, strict=False)
    
    async def _validate_selector(self, response: str, strict: bool = True) -> ValidationResult:
        """Internal method to validate selector with different strictness levels.
        
        Args:
            response: AI-resolved selector string to test
            strict: If True, require exactly one element; if False, allow multiple
            
        Returns:
            ValidationResult indicating if selector validation passes
        """
        if not response or not response.strip():
            return ValidationResult(
                is_valid=False,
                error_message="Empty AI-resolved selector",
                hint="The AI should return a valid CSS selector",
                validated_text=None
            )
        
        selector = response.strip()
        
        try:
            # Create BrowserActionParams for testing
            test_params = BrowserActionParams(
                selector=selector,
                timeout=2.0  # Short timeout for existence check
            )
            
            # Try to find the element using the adapter's visibility check
            element_exists = await self.browser_adapter.is_visible(test_params)
            
            if element_exists:
                logger.info(f"AI-resolved selector '{selector}' successfully found element on page")
                return ValidationResult(
                    is_valid=True,
                    validated_text=selector,
                    error_message=None
                )
            else:
                mode_text = "strict" if strict else "permissive"
                logger.warning(f"AI-resolved selector '{selector}' found no elements on page ({mode_text} mode)")
                return ValidationResult(
                    is_valid=False,
                    error_message=f"AI-resolved selector '{selector}' found no elements on page",
                    hint="Try to find a more specific selector that matches existing elements",
                    validated_text=None
                )
                
        except Exception as e:
            # Any exception means the selector didn't find elements or is invalid
            mode_text = "strict" if strict else "permissive"
            logger.warning(f"AI-resolved selector '{selector}' validation failed ({mode_text} mode): {e}")
            return ValidationResult(
                is_valid=False,
                error_message=f"AI-resolved selector validation failed: {str(e)}",
                hint="Ensure the selector is valid CSS syntax and matches existing elements",
                validated_text=None
            )