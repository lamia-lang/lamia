from abc import ABC, abstractmethod
from typing import Any, Optional, Type, TypeVar
from pydantic import BaseModel
from lamia.validation.base import BaseValidator, ValidationResult

T = TypeVar('T', bound=BaseModel)

class ValidatingType(ABC):
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
        self._last_result: Optional[ValidationResult] = None
    
    @abstractmethod
    def _create_validator(self) -> BaseValidator:
        """
        Create the appropriate validator instance.
        
        Returns:
            BaseValidator: The validator instance to use
        """
        pass
    
    async def get_instance(self, response: str) -> 'TypeWrapper':
        """
        Validate the response and return self for method chaining.
        
        Args:
            response: The response string to validate
            
        Returns:
            TypeWrapper: Self for method chaining
            
        Raises:
            ValueError: If validation fails
        """
        self._last_result = await self._validator.validate(response)
        
        if not self._last_result.is_valid:
            raise ValueError(f"Validation failed: {self._last_result.error_message}")
        
        return self
    
    @property
    def text(self) -> str:
        """
        Get the validated text content.
        
        Returns:
            str: The validated text
            
        Raises:
            RuntimeError: If get_instance() hasn't been called yet
        """
        if self._last_result is None:
            raise RuntimeError("Must call get_instance() before accessing text")
        return self._last_result.validated_text
    
    @property
    def model(self) -> Optional[Any]:
        """
        Get the validated result type (e.g., parsed Pydantic model).
        
        Returns:
            Any: The validated result type, or None if no model was specified
            
        Raises:
            RuntimeError: If get_instance() hasn't been called yet
        """
        if self._last_result is None:
            raise RuntimeError("Must call get_instance() before accessing result_type")
        return self._last_result.result_type