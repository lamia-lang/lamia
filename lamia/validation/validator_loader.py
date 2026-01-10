import os
import sys
import importlib
import inspect
import logging
import asyncio
from typing import Type, Tuple, List, Optional

from lamia.validation.base import BaseValidator
from lamia.validation.contract_checker import check_validator_contracts, ContractViolation

logger = logging.getLogger(__name__)

class ValidatorLoader:
    """Handles loading and contract checking of user-defined validators."""
    
    @staticmethod
    def load_validator_from_file(file_path: str) -> Optional[Type[BaseValidator]]:
        """
        Load a validator class from a Python file and verify its contract.
        
        Args:
            file_path: Path to the Python file containing the validator
            
        Returns:
            The validator class if it passes contract checks, None otherwise
        """
        try:
            # Add file's directory to sys.path temporarily
            file_dir = os.path.dirname(os.path.abspath(file_path))
            sys.path.insert(0, file_dir)
            
            try:
                module_name = os.path.splitext(os.path.basename(file_path))[0]
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if not spec or not spec.loader:
                    logger.error(f"Could not load module spec from {file_path}")
                    return None
                    
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Find validator class in module
                for _, cls in inspect.getmembers(module, inspect.isclass):
                    if (
                        issubclass(cls, BaseValidator) and 
                        cls is not BaseValidator and
                        hasattr(cls, 'name') and
                        callable(getattr(cls, 'name'))
                    ):
                        # Run contract checks
                        passed, violations = asyncio.run(check_validator_contracts(cls))
                        if not passed:
                            logger.error(f"Contract violations found in {cls.__name__}:")
                            for violation in violations:
                                logger.error(f"  - {violation.method_name}: Expected {violation.expected}, got {violation.actual}")
                                if violation.error_message:
                                    logger.error(f"    {violation.error_message}")
                            return None
                            
                        return cls
                        
                logger.error(f"No valid validator class found in {file_path}")
                return None
                
            finally:
                sys.path.pop(0)
                
        except Exception as e:
            logger.error(f"Error loading validator from {file_path}: {e}")
            return None
            
    @staticmethod
    def load_validator_from_function(func, name: str) -> Optional[Type[BaseValidator]]:
        """
        Create a validator class from a function and verify its contract.
        
        Args:
            func: The validation function
            name: Name for the validator
            
        Returns:
            The validator class if it passes contract checks, None otherwise
        """
        try:
            # Create validator class dynamically
            class FunctionValidator(BaseValidator):
                @classmethod
                def name(cls) -> str:
                    return name
                    
                async def validate(self, content: str) -> bool:
                    return await func(content)
                    
            # Run contract checks
            passed, violations = asyncio.run(check_validator_contracts(FunctionValidator))
            if not passed:
                logger.error(f"Contract violations found in function validator {name}:")
                for violation in violations:
                    logger.error(f"  - {violation.method_name}: Expected {violation.expected}, got {violation.actual}")
                    if violation.error_message:
                        logger.error(f"    {violation.error_message}")
                return None
                
            return FunctionValidator
            
        except Exception as e:
            logger.error(f"Error creating validator from function: {e}")
            return None 