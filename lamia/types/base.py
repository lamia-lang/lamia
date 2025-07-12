from abc import ABC, abstractmethod
from typing import Any, Generic, Optional, Type, TypeVar
from pydantic import BaseModel
from lamia.validation.base import BaseValidator, ValidationResult

T = TypeVar('T', bound=BaseModel)

class ValidatingType(ABC, Generic[T]):
    """
    Base class for type wrappers that provide easy access to validated content.
    
    This class implements the common logic for validation and provides
    access to validated_text and result_type through a simple interface.
    """
    
    def __init__(self, model: Optional[Type[T]] = None):
        """
        Initialize the type wrapper.
        
        Args:
            model: Optional Pydantic model class for structured validation
        """
        self.model = model
        self._validator = self._create_validator()
        self._validation_result: Optional[ValidationResult] = None
    
    @abstractmethod
    def _create_validator(self) -> BaseValidator:
        """
        Create the appropriate validator instance.
        
        Returns:
            BaseValidator: The validator instance to use
        """
        pass
    
    async def get_instance(self, response: str) -> ValidationResult:
        """
        Validate the response and return self for method chaining.
        
        Args:
            response: The response string to validate
            
        Returns:
            TypeWrapper: Self for method chaining
            
        Raises:
            ValueError: If validation fails
        """
        self._validation_result = await self._validator.validate(response)
        
        return self._validation_result