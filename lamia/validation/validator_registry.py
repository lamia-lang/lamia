import os
import sys
import importlib
import pkgutil
import inspect
import asyncio
from typing import Dict, Type, Any, Optional
from pathlib import Path
import logging

from lamia.validation.base import BaseValidator
from lamia.validation.custom_loader import (
    load_validator_from_file,
    load_validator_from_function
)
from lamia.validation.contract_checker import check_validator_contracts, ContractViolation
import lamia.validation.validators as validators_pkg

logger = logging.getLogger(__name__)

class ValidatorRegistry:
    """Handles discovery and loading of validator classes, both built-in and user-defined."""
    def __init__(self, config: dict, extensions_folder: Optional[str] = None, enable_contract_checking: bool = True):
        self.config = config
        self.extensions_folder = extensions_folder or "extensions"
        self.enable_contract_checking = enable_contract_checking
        self._validator_instances = {}  # Store validator instances
        
        # Check if contract checking is disabled in config
        validation_config = config.get('validation', {})
        if 'enable_contract_checking' in validation_config:
            self.enable_contract_checking = validation_config['enable_contract_checking']

    async def _check_validator_contract(self, validator_class: Type[BaseValidator], source: str = "unknown") -> bool:
        """
        Check that a custom validator follows the documented contracts.
        
        Args:
            validator_class: The validator class to check
            source: Description of where the validator came from (for logging)
            
        Returns:
            bool: True if all contracts pass, False otherwise
        """
        if not self.enable_contract_checking:
            return True
            
        try:
            logger.info(f"Running contract checks for {validator_class.__name__} from {source}")
            passed, violations = await check_validator_contracts(validator_class)
            
            if not passed:
                logger.error(f"Contract violations found in {validator_class.__name__}:")
                for violation in violations:
                    logger.error(f"  - {violation.method_name}: Expected {violation.expected}, got {violation.actual}")
                    if violation.error_message:
                        logger.error(f"    {violation.error_message}")
                    if violation.test_input is not None:
                        logger.error(f"    Test input: {repr(violation.test_input)}")
                return False
            else:
                logger.info(f"All contract checks passed for {validator_class.__name__}")
                return True
                
        except Exception as e:
            logger.warning(f"Could not run contract checks for {validator_class.__name__}: {str(e)}")
            # If contract checking fails, we still allow the validator to load
            # but log a warning
            return True

    async def _load_custom_validator(self, validator_config: dict) -> Optional[Type[BaseValidator]]:
        validator_type = validator_config.get("type")
        validator_class = None
        
        if validator_type == "custom_file":
            file_path = validator_config.get("path")
            if not file_path:
                logger.error("Missing 'path' in custom_file validator config")
                return None
            
            try:
                validator_class = load_validator_from_file(file_path)
                source = f"file: {file_path}"
            except Exception as e:
                logger.error(f"Failed to load validator from file {file_path}: {str(e)}")
                return None
                
        elif validator_type == "custom_function":
            func_path = validator_config.get("path")
            if not func_path:
                logger.error("Missing 'path' in custom_function validator config")
                return None
            
            try:
                validator_class = load_validator_from_function(func_path)
                source = f"function: {func_path}"
            except Exception as e:
                logger.error(f"Failed to load validator from function {func_path}: {str(e)}")
                return None
        else:
            return None
            
        # Run contract checks on the loaded validator
        if validator_class:
            contract_passed = await self._check_validator_contract(validator_class, source)
            if not contract_passed:
                logger.error(f"Custom validator {validator_class.__name__} failed contract checks")
                if self.config.get('validation', {}).get('strict_contract_checking', False):
                    # If strict mode is enabled, reject validators that fail contract checks
                    logger.error(f"Rejecting validator {validator_class.__name__} due to contract violations")
                    return None
                else:
                    logger.warning(f"Loading validator {validator_class.__name__} despite contract violations")
            
        return validator_class

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

    async def _discover_validators_in_path(self, path: str) -> dict:
        import importlib.util
        validator_class_map = {}
        if not os.path.isdir(path):
            return validator_class_map
        sys.path.insert(0, path)
        
        try:
            for file in os.listdir(path):
                if file.endswith(".py") and not file.startswith("__"):
                    module_name = file[:-3]
                    try:
                        spec = importlib.util.spec_from_file_location(module_name, os.path.join(path, file))
                        if not spec or not spec.loader:
                            continue
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        for _, cls in inspect.getmembers(module, inspect.isclass):
                            if (
                                issubclass(cls, BaseValidator)
                                and cls is not BaseValidator
                                and hasattr(cls, 'name')
                                and callable(getattr(cls, 'name'))
                            ):
                                # Run contract checks on discovered validators
                                contract_passed = await self._check_validator_contract(
                                    cls, f"extensions file: {file}"
                                )
                                if contract_passed or not self.config.get('validation', {}).get('strict_contract_checking', False):
                                    validator_class_map[cls.name()] = cls
                                else:
                                    logger.error(f"Skipping validator {cls.__name__} due to contract violations")
                                    
                    except Exception as e:
                        logger.warning(f"Could not import validator from {file}: {e}")
        finally:
            sys.path.pop(0)
            
        return validator_class_map

    async def get_registry(self) -> Dict[str, BaseValidator]:
        """Preload all validators in the validators folder and extensions, checking for name conflicts."""
        
        validator_class_map = self._discover_validators_recursively(validators_pkg)
        ext_validators_path = os.path.join(os.getcwd(), self.extensions_folder, "validators")
        ext_validator_class_map = await self._discover_validators_in_path(ext_validators_path)
        conflict_names = set(validator_class_map.keys()) & set(ext_validator_class_map.keys())
        if conflict_names:
            raise ValueError(f"User-defined validator name(s) conflict with built-in validators: {', '.join(conflict_names)}")
        validator_class_map.update(ext_validator_class_map)
        
        validation_config = self.config.get('validation', {})
        if validation_config.get('validators'):
            for validator_config in validation_config['validators']:
                vtype = validator_config.get("type")
                strict = validator_config.get("strict", True)
                config_copy = validator_config.copy()
                config_copy.pop("type", None)
                config_copy.pop("strict", None)
                
                if vtype in validator_class_map:
                    cls = validator_class_map[vtype]
                    # Create singleton instance if not exists
                    if cls.name() not in self._validator_instances:
                        self._validator_instances[cls.name()] = cls(strict=strict, generate_hints=True, **config_copy)
                elif vtype in ["custom_file", "custom_function"]:
                    try:
                        validator_class = await self._load_custom_validator(validator_config)
                        if validator_class:
                            # Create singleton instance if not exists
                            if validator_class.name() not in self._validator_instances:
                                self._validator_instances[validator_class.name()] = validator_class(strict=strict, generate_hints=True, **config_copy)
                    except Exception as e:
                        logger.error(f"Error loading custom validator: {str(e)}")
                else:
                    raise ValueError(f"Unknown validator type: {vtype}")
                    
        return self._validator_instances 