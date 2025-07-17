import os
import sys
import importlib
import pkgutil
import inspect
import asyncio
from typing import Dict, Type, Any, Optional, Tuple, List, Set
from pathlib import Path
import logging

from lamia.validation.base import BaseValidator
from lamia.validation.contract_checker import ValidatorContractChecker, ContractViolation
import lamia.validation.validators as validators_pkg

logger = logging.getLogger(__name__)

class ValidatorRegistry:
    """Handles discovery and loading of built-in and user-defined validator classes."""
    
    def __init__(self, extensions_folder: str):
        # Load built-in validators once at initialization
        self._built_in_validators = self._discover_builtin_validators_recursively(validators_pkg)
        # Initialize empty dict for user-defined validators
        self._user_validators: Dict[str, Type[BaseValidator]] = {}
        # Cache for validators that passed contract checks
        self._checked_classes: Set[Type[BaseValidator]] = set()
        self.extensions_folder = extensions_folder
        
    def check_validator(self, validator_class: Type[BaseValidator]) -> Tuple[bool, List[ContractViolation]]:
        """
        Check if a validator class meets all contracts.
        Only runs checks for non-built-in validators since built-ins are pre-tested.
        Caches results to avoid re-checking the same class.
        
        Args:
            validator_class: The validator class to check
            
        Returns:
            Tuple of (passed, violations)
        """
        # Skip contract checks for built-in validators
        if self._is_built_in(validator_class):
            return True, []

        # Check caches first
        if validator_class in self._checked_classes:
            return True, []

        passed, violations = ValidatorContractChecker(validator_class).check_contracts()
        
        if passed:
            self._validated_classes.add(validator_class)
        else:
            self._failed_classes.add(validator_class)
            logger.error(f"Contract violations found in {validator_class.__name__}:")
            for violation in violations:
                logger.error(f"  - {violation.method_name}: Expected {violation.expected}, got {violation.actual}")
                if violation.error_message:
                    logger.error(f"    {violation.error_message}")
                    
        return passed, violations
    
    def get_class_from_name(self, name: str) -> Type[BaseValidator]:
        """Get a validator class from its name."""
        # First check built-in validators
        if name in self._built_in_validators:
            return self._built_in_validators[name]
            
        # Then check already loaded user validators
        if name in self._user_validators:
            return self._user_validators[name]
            
        # If not found, try to load from user extensions
        self._load_user_validators()
        if name in self._user_validators:
            return self._user_validators[name]
            
        raise ValueError(f"Validator '{name}' not found")
    
    def _is_built_in(self, validator_class: Type[BaseValidator]) -> bool:
        """Check if a validator class is built-in."""
        return any(
            validator_class is cls 
            for cls in self._built_in_validators.values()
        )

    def _discover_builtin_validators_recursively(self, package) -> dict:
        """Recursively discover all built-in validators in the validators package."""
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
                    validator_class_map.update(self._discover_builtin_validators_recursively(module))
                except Exception as e:
                    logger.warning(f"Could not import submodule {name}: {e}")
        return validator_class_map

    def _load_user_validators(self):
        """Lazily load user-defined validators from extensions folder."""
        validators_path = os.path.join(os.getcwd(), self.extensions_folder, "validators")
        if not os.path.isdir(validators_path):
            return
            
        sys.path.insert(0, validators_path)
        try:
            for file in os.listdir(validators_path):
                if file.endswith(".py") and not file.startswith("__"):
                    module_name = file[:-3]
                    try:
                        spec = importlib.util.spec_from_file_location(
                            module_name, 
                            os.path.join(validators_path, file)
                        )
                        if not spec or not spec.loader:
                            continue
                            
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        
                        for _, cls in inspect.getmembers(module, inspect.isclass):
                            if (
                                issubclass(cls, BaseValidator) and
                                cls is not BaseValidator and
                                hasattr(cls, 'name') and
                                callable(getattr(cls, 'name'))
                            ):
                                name = cls.name()
                                if name in self._built_in_validators:
                                    logger.warning(
                                        f"User validator '{name}' in {file} conflicts with "
                                        "built-in validator - skipping"
                                    )
                                    continue
                                    
                                # Run contract checks
                                passed, violations = self.check_validator(cls)
                                if passed:
                                    self._user_validators[name] = cls
                                else:
                                    logger.error(
                                        f"Skipping user validator '{name}' in {file} "
                                        "due to contract violations"
                                    )
                                    
                    except Exception as e:
                        logger.warning(f"Could not load validator from {file}: {e}")
                        
        finally:
            sys.path.pop(0)