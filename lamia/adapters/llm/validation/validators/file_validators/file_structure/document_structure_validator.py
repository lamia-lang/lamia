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

    def _is_primitive_type(self, t):
        return self.type_matcher._is_primitive_type(t)

    def _normalize_primitive_type(self, t):
        return self.type_matcher._normalize_primitive_type(t)

    def _get_primitive_value(self, value, expected_type):
        return self.type_matcher._get_primitive_value(value, expected_type)

    def _is_type_match(self, value, expected_type):
        return self.type_matcher._is_type_match(value, expected_type)

    def _is_type_match_strictly_typed(self, value, expected_type):
        return self.type_matcher._is_type_match_strictly_typed(value, expected_type)

    def validate_strict_recursive(self, tree, model):
        for field, field_info in model.model_fields.items():
            submodel = self._normalize_primitive_type(field_info.annotation)
            elem = self.find_element(tree, field)
            # Use element presence for tag-based trees
            if elem is None:
                if is_optional(field_info.annotation):
                    continue
                return False, f"Missing <{field}> as direct child."
            if submodel is typing.Any or submodel is object:
                continue
            if self._is_primitive_type(submodel):
                if self.has_nested(elem):
                    return False, f"<{field}> should only contain text, but has nested elements."
            elif typing.get_origin(submodel) in (list, dict):
                # Don't check for nested for lists/dicts
                pass
            else:
                if hasattr(submodel, "model_fields"):
                    valid, err = self.validate_strict_recursive(elem, submodel)
                    if not valid:
                        return False, err
                else:
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
            # Use validate_field for presence/null checks
            if not elems:
                if validate_field_presence(field, field_info.annotation, tree, "permissive"):
                    continue
                return False, f"Missing <{field}> tag/field anywhere in document."
            for elem in elems:
                if not validate_field_presence(field, field_info.annotation, {field: elem}, "permissive"):
                    return False, f"<{field}> is null but not Optional."
            if submodel is typing.Any or submodel is object:
                continue
            if self._is_primitive_type(submodel):
                if self.has_nested(elem):
                    return False, f"<{field}> should only contain text, but has nested elements."
            elif typing.get_origin(submodel) in (list, dict):
                # Don't check for nested for lists/dicts
                pass
            else:
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

    def _fill_model_from_tree(self, tree, model, permissive=False, info_loss=None):
        """
        Recursively fill a Pydantic model from the parsed tree (dict, soup, AST, etc.).
        Returns (model_instance, info_loss_dict)
        """
        from pydantic import ValidationError
        values = {}
        info_loss = info_loss or {}
        for field, field_info in model.model_fields.items():
            submodel = self._normalize_primitive_type(field_info.annotation)
            if permissive:
                elems = self.find_all(tree, field)
                elem = elems[0] if elems else None
            else:
                elem = self.find_element(tree, field)
            if elem is None:
                values[field] = None
                continue
            if hasattr(submodel, "model_fields"):
                # Nested Pydantic model
                nested, nested_info_loss = self._fill_model_from_tree(elem, submodel, permissive, info_loss)
                values[field] = nested
                if nested_info_loss:
                    info_loss[field] = nested_info_loss
            elif self._is_primitive_type(submodel):
                text = self.get_text(elem)
                # Info-losing conversion: e.g., float->int
                try:
                    if submodel is int and isinstance(text, float):
                        info_loss[field] = f"float({text}) -> int({int(text)})"
                        values[field] = int(text)
                    elif submodel is str:
                        values[field] = str(text) if text is not None else None
                    else:
                        values[field] = submodel(text) if text is not None else None
                except Exception:
                    values[field] = None
            else:
                values[field] = self.get_text(elem)
        try:
            model_instance = model(**values)
        except ValidationError:
            model_instance = None
        return model_instance, info_loss

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        try:
            tree = self.parse(response)
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid file: {e}",
                raw_text=response,
                hint=self.initial_hint
            )
        if self.model is None:
            return ValidationResult(is_valid=True, raw_text=response, validated_text=response, result_type=tree)
        valid, err = self.validate_strict_recursive(tree, self.model)
        if not valid:
            return ValidationResult(
                is_valid=False,
                error_message=f"Strict validation failed: {err}",
                raw_text=response,
                hint=self.initial_hint
            )
        model_instance, info_loss = self._fill_model_from_tree(tree, self.model, permissive=False)
        return ValidationResult(
            is_valid=True,
            raw_text=response,
            validated_text=response,  # For now, the whole doc; can be improved to just the valid part
            result_type=model_instance,
            info_loss=info_loss if info_loss else None
        )

    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        try:
            tree = self.parse(response)
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid file: {e}",
                raw_text=response,
                hint=self.initial_hint
            )
        if self.model is None:
            return ValidationResult(is_valid=True, raw_text=response, validated_text=response, result_type=tree)
        valid, err = self.validate_permissive_recursive(tree, self.model)
        if not valid:
            return ValidationResult(
                is_valid=False,
                error_message=f"Permissive validation failed: {err}",
                raw_text=response,
                hint=self.initial_hint
            )
        model_instance, info_loss = self._fill_model_from_tree(tree, self.model, permissive=True)
        return ValidationResult(
            is_valid=True,
            raw_text=response,
            validated_text=response,  # For now, the whole doc; can be improved to just the valid part
            result_type=model_instance,
            info_loss=info_loss if info_loss else None
        )