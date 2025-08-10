"""Validator for checking AI-generated selector correctness."""

from lamia.validation.base import BaseValidator, ValidationResult
from .selector_parser import SelectorParser, SelectorType


class SelectorCorrectnessValidator(BaseValidator):
    """Validates that AI-generated selectors are syntactically correct."""
    
    def __init__(self):
        """Initialize the validator with a selector parser."""
        super().__init__()
        self.parser = SelectorParser()
    
    @property
    def name(self) -> str:
        """Name of the validator."""
        return "selector_correctness"
    
    @property
    def initial_hint(self) -> str:
        """Initial hint for LLM prompt."""
        return "Return only a valid CSS selector or XPath expression, no extra text"
    
    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        """Strict validation - same as permissive for selectors."""
        return await self.validate_permissive(response, **kwargs)
    
    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        """Validate that the response is a syntactically correct CSS or XPath selector.
        
        Args:
            response: AI-generated selector string
            
        Returns:
            ValidationResult indicating if selector is valid
        """
        if not response or not response.strip():
            return ValidationResult(
                is_valid=False,
                result_type=None,
                error_message="Empty selector response"
            )
        
        selector = response.strip()
        
        try:
            selector_type = self.parser.classify(selector)
            
            if selector_type in [SelectorType.VALID_CSS, SelectorType.VALID_XPATH]:
                return ValidationResult(
                    is_valid=True,
                    result_type=selector,
                    error_message=None
                )
            else:
                return ValidationResult(
                    is_valid=False,
                    result_type=None,
                    error_message=f"Invalid selector: {selector_type.value}"
                )
                
        except ValueError as e:
            return ValidationResult(
                is_valid=False,
                result_type=None,
                error_message=str(e)
            )