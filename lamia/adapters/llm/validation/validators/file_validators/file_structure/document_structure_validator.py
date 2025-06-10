from abc import ABC, abstractmethod
from ....base import BaseValidator, ValidationResult
import typing

class DocumentStructureValidator(BaseValidator, ABC):
    def __init__(self, model, strict=True):
        super().__init__(strict=strict)
        self.model = model

    @abstractmethod
    def parse(self, response: str):
        """Parse the document string into a navigable structure (tree/dict)."""
        pass

    @abstractmethod
    def find_element(self, tree, key):
        """Find an element or field in the parsed structure."""
        pass

    @abstractmethod
    def get_text(self, element):
        """Extract text from an element (if applicable)."""
        pass

    @abstractmethod
    def has_nested(self, element):
        """Return True if the element has nested elements/fields (not just text)."""
        pass

    @abstractmethod
    def iter_direct_children(self, tree):
        """Iterate over direct children of the tree/element."""
        pass

    @abstractmethod
    def get_name(self, element):
        """Get the name/tag/field of the element."""
        pass

    @abstractmethod
    def find_all(self, tree, key):
        """Find all elements/fields with the given key anywhere in the tree."""
        pass

    def _is_primitive_type(self, t):
        return t in (str, int, float, bool)

    def _normalize_primitive_type(self, t):
        # Normalize to canonical Python primitive types
        if t == str or t == type(str()):
            return str
        if t == int or t == type(int()):
            return int
        if t == float or t == type(float()):
            return float
        if t == bool or t == type(bool()):
            return bool
        return t

    def _get_primitive_value(self, value, expected_type):
        # Always extract text from AST nodes for type checking
        return self.get_text(value)

    def _is_type_match(self, value, expected_type):
        value = self._get_primitive_value(value, expected_type)
        
        origin = typing.get_origin(expected_type)
        args = typing.get_args(expected_type)
        if origin is None:
            # Handle Any and object
            if expected_type is typing.Any or expected_type is object:
                return True
            return isinstance(value, expected_type)
        elif origin is list:
            return isinstance(value, list) and all(self._is_type_match(v, args[0]) for v in value)
        elif origin is dict:
            return isinstance(value, dict)
        elif origin is typing.Union:
            # Handle Optional[X] (which is Union[X, NoneType])
            return any(self._is_type_match(value, arg) for arg in args)
        return False

    def validate_strict_recursive(self, tree, model):
        for field, field_info in model.model_fields.items():
            submodel = self._normalize_primitive_type(field_info.annotation)
            elem = self.find_element(tree, field)
            if elem is None:
                return False, f"Missing <{field}> as direct child."
            
            if submodel is typing.Any or submodel is object:
                continue
            if hasattr(submodel, "model_fields"):
                valid, err = self.validate_strict_recursive(elem, submodel)
                if not valid:
                    return False, err
            else:
                if self.has_nested(elem):
                    return False, f"<{field}> should only contain text, but has nested elements."
                if not self._is_type_match(elem, submodel):
                    return False, f"<{field}> has value {self.get_text(elem)!r} of type {type(self._get_primitive_value(elem, submodel)).__name__}, expected {submodel.__name__ if hasattr(submodel, '__name__') else submodel}."
        model_tags = set(model.model_fields.keys())
        for child in self.iter_direct_children(tree):
            name = self.get_name(child)
            if name and name not in model_tags:
                return False, f"Unexpected tag/field <{name}> found."
        return True, None

    def validate_permissive_recursive(self, tree, model):
        for field, field_info in model.model_fields.items():
            submodel = self._normalize_primitive_type(field_info.annotation)
            elems = self.find_all(tree, field)
            if not elems:
                return False, f"Missing <{field}> tag/field anywhere in document."
            if submodel is typing.Any or submodel is object:
                continue
            if hasattr(submodel, "model_fields"):
                found_valid = False
                for elem in elems:
                    valid, _ = self.validate_permissive_recursive(elem, submodel)
                    if valid:
                        found_valid = True
                        break
                if not found_valid:
                    return False, f"No <{field}> tag/field matches the required nested structure."
            else:
                for elem in elems:
                    if not self._is_type_match(elem, submodel):
                        return False, f"<{field}> has value {self.get_text(elem)!r} of type {type(self._get_primitive_value(elem, submodel)).__name__}, expected {submodel.__name__ if hasattr(submodel, '__name__') else submodel}."
        return True, None

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        try:
            tree = self.parse(response)
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid file: {e}",
                hint=self.initial_hint
            )
        if self.model is None:
            return ValidationResult(is_valid=True)
        valid, err = self.validate_strict_recursive(tree, self.model)
        if not valid:
            return ValidationResult(
                is_valid=False,
                error_message=f"Strict validation failed: {err}",
                hint=self.initial_hint
            )
        return ValidationResult(is_valid=True)

    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        try:
            tree = self.parse(response)
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid file: {e}",
                hint=self.initial_hint
            )
        if self.model is None:
            return ValidationResult(is_valid=True)
        valid, err = self.validate_permissive_recursive(tree, self.model)
        if not valid:
            return ValidationResult(
                is_valid=False,
                error_message=f"Permissive validation failed: {err}",
                hint=self.initial_hint
            )
        return ValidationResult(is_valid=True) 