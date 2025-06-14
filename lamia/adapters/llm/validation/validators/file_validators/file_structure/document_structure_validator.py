from abc import ABC, abstractmethod
from ....base import BaseValidator, ValidationResult
import typing
import re
from typing import get_origin, get_args, Any, Union
from lamia.adapters.llm.validation.utlis.type_matcher import TypeMatcher

def is_optional(field_type):
    return get_origin(field_type) is Union and type(None) in get_args(field_type)

def is_any(field_type):
    return field_type is Any

def validate_field_presence(field_name, field_type, data, mode):
    present = field_name in data
    value = data.get(field_name, None)
    optional = is_optional(field_type)
    any_type = is_any(field_type)
    concrete_type = not any_type and not optional

    if mode == "strict":
        if optional:
            # OK if missing or None
            return True
        if not present or value is None:
            return False
        return True
    elif mode == "permissive":
        if optional:
            return True
        if any_type:
            return True
        if concrete_type:
            if not present or value is None:
                return False
            return True
    return True

STRICT_TYPE_MATCH = False

class DocumentStructureValidator(BaseValidator, ABC):
    def __init__(self, model, strict=True):
        super().__init__(strict=strict)
        self.model = model
        self.type_matcher = TypeMatcher(strict=STRICT_TYPE_MATCH, get_text_func=self.get_text)

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

    def _validate_tree(self, tree, model, permissive=False, fill_model=True):
        errors = []
        values = {}
        is_valid = True
        info_loss = {}

        for field, field_info in model.model_fields.items():
            expected_type = field_info.annotation
            elem = self.find_all(tree, field)[0] if permissive else self.find_element(tree, field)

            if elem is None:
                if is_optional(expected_type):
                    values[field] = None
                    continue
                errors.append(f"Missing <{field}>")
                is_valid = False
                continue

            text = self.get_text(elem)
            match_result = self.type_matcher.validate_and_convert(text, expected_type)
            if not match_result.is_valid:
                errors.append(f"Field {field}: {match_result.error}")
                is_valid = False
                values[field] = None
            else:
                values[field] = match_result.value

        model_instance = None
        if is_valid and fill_model:
            try:
                model_instance = model(**values)
            except Exception as e:
                errors.append(f"Model fill error: {e}")
                is_valid = False

        error_message = '; '.join(errors) if errors else None
        return ValidationResult(
            is_valid=is_valid,
            result_type=model_instance if fill_model else None,
            error_message=error_message
        )

    async def validate_strict(self, response: str, fill_model: bool = True, **kwargs) -> ValidationResult:
        try:
            tree = self.parse(response)
        except Exception as e:
            return ValidationResult(is_valid=False, error_message=f"Invalid file: {e}")
        if self.model is None:
            return ValidationResult(is_valid=True, result_type=tree)
        return self.validate_strict_recursive(tree, self.model)

    async def validate_permissive(self, response: str, fill_model: bool = True, **kwargs) -> ValidationResult:
        try:
            tree = self.parse(response)
        except Exception as e:
            return ValidationResult(is_valid=False, error_message=f"Invalid file: {e}")
        if self.model is None:
            return ValidationResult(is_valid=True, result_type=tree)
        return self.validate_permissive_recursive(tree, self.model)

    def validate_strict_recursive(self, tree, model):
        """Shallow wrapper for backward compatibility. Calls unified _validate_tree logic."""
        return self._validate_tree(tree, model, permissive=False)

    def validate_permissive_recursive(self, tree, model):
        """Shallow wrapper for backward compatibility. Calls unified _validate_tree logic."""
        return self._validate_tree(tree, model, permissive=True)