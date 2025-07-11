from typing import Optional, Type, TypeVar
from pydantic import BaseModel
from lamia.validation.validators.file_validators.html_validator import HTMLValidator
from lamia.validation.validators.file_validators.file_structure.html_structure_validator import HTMLStructureValidator
from .base import ValidatingType

T = TypeVar('T', bound=BaseModel)

class HTML(ValidatingType[T]):
    """
    HTML type wrapper that provides easy access to validated HTML content.
    
    This class provides two constructors:
    1. HTML() - for basic HTML validation (no model)
    2. HTML(model=MyModel) - for structured HTML validation with a Pydantic model
    """
    
    def __init__(self, model: Optional[Type[T]] = None, strict: bool = True):
        """
        Initialize the HTML type wrapper.
        
        Args:
            model: Optional Pydantic model class for structured validation.
                   If None, uses basic HTML validation.
        """
        super().__init__(model)
    
    def _create_validator(self):
        """
        Create the appropriate HTML validator based on whether a model is provided.
        
        Returns:
            BaseValidator: HTMLValidator for basic validation or HTMLStructureValidator for structured validation
        """
        if self.model is not None:
            # Use HTMLStructureValidator for structured validation
            return HTMLStructureValidator(model=self.model, strict=self.strict)
        else:
            # Use HTMLValidator for basic HTML validation
            return HTMLValidator()
  
