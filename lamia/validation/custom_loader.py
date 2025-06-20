import importlib.util
import inspect
from pathlib import Path
from typing import Type, Optional

from lamia.validation.base import BaseValidator, ValidationResult

def load_validator_from_file(file_path: str) -> Optional[Type[BaseValidator]]:
    """Load a custom validator class from a Python file.
    
    Args:
        file_path: Path to the Python file containing the validator
        
    Returns:
        The validator class if found, None otherwise
        
    Example file content:
        from adapters.llm.validation.base import BaseValidator, ValidationResult
        
        class MyCustomValidator(BaseValidator):
            @property
            def name(self) -> str:
                return "my_custom"
                
            async def validate(self, response: str, **kwargs) -> ValidationResult:
                # Custom validation logic
                return ValidationResult(is_valid=True)
    """
    try:
        # Convert to absolute path
        abs_path = str(Path(file_path).resolve())
        
        # Load the module
        spec = importlib.util.spec_from_file_location("custom_validator", abs_path)
        if not spec or not spec.loader:
            raise ImportError(f"Could not load spec for {file_path}")
            
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Find validator class in module
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                issubclass(obj, BaseValidator) and 
                obj != BaseValidator):
                return obj
                
        raise ValueError(f"No validator class found in {file_path}")
        
    except Exception as e:
        raise ValueError(f"Error loading validator from {file_path}: {str(e)}")

def load_validator_from_function(func_path: str) -> Type[BaseValidator]:
    """Create a validator class from a validation function.
    
    Args:
        func_path: Path to function in format "module.submodule:function_name"
        
    Returns:
        A validator class wrapping the function
        
    Example function:
        def validate_response(response: str) -> tuple[bool, str]:
            # Return (is_valid, error_message)
            return True, ""
    """
    try:
        # Split module path and function name
        module_path, func_name = func_path.split(":")
        
        # Import the module
        module = importlib.import_module(module_path)
        
        # Get the function
        func = getattr(module, func_name)
        if not callable(func):
            raise ValueError(f"{func_name} is not callable")
        
        # Create a validator class wrapping the function
        class FunctionValidator(BaseValidator):
            @property
            def name(self) -> str:
                return f"func_{func_name}"
            
            async def validate(self, response: str, **kwargs) -> ValidationResult:
                try:
                    # Call the function
                    result = func(response)
                    
                    # Handle different return types
                    if isinstance(result, bool):
                        return ValidationResult(
                            is_valid=result,
                            error_message="" if result else "Validation failed"
                        )
                    elif isinstance(result, tuple) and len(result) == 2:
                        is_valid, error_msg = result
                        return ValidationResult(
                            is_valid=is_valid,
                            error_message=error_msg
                        )
                    else:
                        raise ValueError(
                            "Validation function must return bool or tuple[bool, str]"
                        )
                        
                except Exception as e:
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"Validation error: {str(e)}"
                    )
        
        return FunctionValidator
        
    except Exception as e:
        raise ValueError(f"Error loading validator function {func_path}: {str(e)}") 