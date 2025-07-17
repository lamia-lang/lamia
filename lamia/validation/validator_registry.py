import os
import sys
import importlib
import pkgutil
import inspect
import asyncio
from typing import Dict, Type, Any, Optional, Tuple, List
from pathlib import Path
import logging

from lamia.validation.base import BaseValidator
from lamia.validation.contract_checker import check_validator_contracts, ContractViolation
import lamia.validation.validators as validators_pkg

logger = logging.getLogger(__name__)

class ValidatorRegistry:
    """Handles discovery and loading of built-in validator classes."""
    
    def __init__(self):
        # Load built-in validators once at initialization
        self._built_in_validators = self._discover_validators_recursively(validators_pkg)
    
    def get_registry(self) -> Dict[str, Type[BaseValidator]]:
        """Get the registry of built-in validators."""
        return self._built_in_validators.copy()
        
    def is_built_in(self, validator_class: Type[BaseValidator]) -> bool:
        """Check if a validator class is built-in."""
        return any(
            validator_class is cls 
            for cls in self._built_in_validators.values()
        )
        
    def check_validator(self, validator_class: Type[BaseValidator]) -> Tuple[bool, List[ContractViolation]]:
        """
        Check if a validator class meets all contracts.
        Only runs checks for non-built-in validators since built-ins are pre-tested.
        
        Args:
            validator_class: The validator class to check
            
        Returns:
            Tuple of (passed, violations)
        """
        # Skip contract checks for built-in validators
        if self.is_built_in(validator_class):
            return True, []
            
        # Run contract checks for user-defined validators
        passed, violations = check_validator_contracts(validator_class)
        if not passed:
            logger.error(f"Contract violations found in {validator_class.__name__}:")
            for violation in violations:
                logger.error(f"  - {violation.method_name}: Expected {violation.expected}, got {violation.actual}")
                if violation.error_message:
                    logger.error(f"    {violation.error_message}")
                    
        return passed, violations

    def _discover_validators_recursively(self, package) -> dict:
        validator_class_map = {}
        for finder, name, ispkg in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
            module = importlib.import_module(name)
            for _, cls in inspect.getmembers(module, inspect.isclass):
                if (
                    cls.__module__ == module.__name__ and
                    issubclass(cls, BaseValidator) and
                    hasattr(cls, 'name') and
                    callable(getattr(cls, 'name'))
                ):
                    validator_class_map[cls.name()] = cls
            if ispkg:
                try:
                    validator_class_map.update(self._discover_validators_recursively(module))
                except Exception as e:
                    logger.warning(f"Could not import submodule {name}: {e}")
        return validator_class_map