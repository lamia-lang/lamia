import os
import sys
import importlib
import pkgutil
import inspect
from typing import Dict, Type, Any, Optional
from pathlib import Path
import logging

from lamia.validation.base import BaseValidator
from lamia.validation.custom_loader import (
    load_validator_from_file,
    load_validator_from_function
)
import lamia.validation.validators as validators_pkg

logger = logging.getLogger(__name__)

class ValidatorRegistry:
    """Handles discovery and loading of validator classes, both built-in and user-defined."""
    def __init__(self, config: dict, extensions_folder: Optional[str] = None):
        self.config = config
        self.extensions_folder = extensions_folder or "extensions"

    def _load_custom_validator(self, validator_config: dict) -> Optional[Type[BaseValidator]]:
        validator_type = validator_config.get("type")
        if validator_type == "custom_file":
            file_path = validator_config.get("path")
            if not file_path:
                logger.error("Missing 'path' in custom_file validator config")
                return None
            return load_validator_from_file(file_path)
        elif validator_type == "custom_function":
            func_path = validator_config.get("path")
            if not func_path:
                logger.error("Missing 'path' in custom_function validator config")
                return None
            return load_validator_from_function(func_path)
        return None

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

    def _discover_validators_in_path(self, path: str) -> dict:
        import importlib.util
        validator_class_map = {}
        if not os.path.isdir(path):
            return validator_class_map
        sys.path.insert(0, path)
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
                            validator_class_map[cls.name()] = cls
                except Exception as e:
                    logger.warning(f"Could not import validator from {file}: {e}")
        sys.path.pop(0)
        return validator_class_map

    def get_registry(self) -> Dict[str, Type[BaseValidator]]:
        """Preload all validators in the validators folder and extensions, checking for name conflicts."""
        validator_class_map = self._discover_validators_recursively(validators_pkg)
        ext_validators_path = os.path.join(os.getcwd(), self.extensions_folder, "validators")
        ext_validator_class_map = self._discover_validators_in_path(ext_validators_path)
        conflict_names = set(validator_class_map.keys()) & set(ext_validator_class_map.keys())
        if conflict_names:
            raise ValueError(f"User-defined validator name(s) conflict with built-in validators: {', '.join(conflict_names)}")
        validator_class_map.update(ext_validator_class_map)
        registry = {}
        validation_config = self.config.get('validation', {})
        if validation_config.get('validators'):
            for validator_config in validation_config['validators']:
                vtype = validator_config.get("type")
                config_copy = validator_config.copy()
                config_copy.pop("type", None)
                config_copy.pop("strict", None)
                if vtype in validator_class_map:
                    cls = validator_class_map[vtype]
                    registry[cls.name()] = cls
                elif vtype in ["custom_file", "custom_function"]:
                    try:
                        validator_class = self._load_custom_validator(validator_config)
                        if validator_class:
                            registry[validator_class.name()] = validator_class
                    except Exception as e:
                        logger.error(f"Error loading custom validator: {str(e)}")
                else:
                    raise ValueError(f"Unknown validator type: {vtype}")
        return registry 