from abc import ABC, abstractmethod
from ....base import BaseValidator, ValidationResult
import typing
import re
from typing import get_origin, get_args, Any, Union
from lamia.validation.utlis.type_matcher import TypeMatcher
from pydantic import BaseModel

class ParsingError(ValueError):
    """Custom exception for parsing errors."""
    def __init__(self, message: str, original_exception: Exception = None, original_text: str = None, parsed_text: str = None):
        super().__init__(message)
        self.original_exception = original_exception
        self.original_text = original_text
        self.parsed_text = parsed_text

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

def is_pydantic_model(field_type):
    try:
        return issubclass(field_type, BaseModel)
    except TypeError:
        return False

def is_list_of_models(field_type):
    origin = get_origin(field_type)
    args = get_args(field_type)
    return origin in (list, typing.List) and args and is_pydantic_model(args[0])

class DocumentStructureValidator(BaseValidator, ABC):
    def __init__(self, model, strict=True, generate_hints=False):
        super().__init__(strict=strict, generate_hints=generate_hints)
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
            if permissive:
                elems = self.find_all(tree, field)
                elem = elems[0] if elems else None
            else:
                elem = self.find_element(tree, field)

            if elem is None:
                if is_optional(expected_type):
                    values[field] = None
                    continue
                errors.append(f"Missing <{field}>")
                is_valid = False
                continue

            # Recursive validation for nested models
            if is_pydantic_model(expected_type):
                nested_result = self._validate_tree(elem, expected_type, permissive, fill_model)
                if not nested_result.is_valid:
                    errors.append(f"Field {field}: {nested_result.error_message}")
                    is_valid = False
                    values[field] = None
                else:
                    values[field] = nested_result.result_type if fill_model else None
                continue
            # Recursive validation for lists of models
            if is_list_of_models(expected_type):
                item_type = get_args(expected_type)[0]
                children = list(self.iter_direct_children(elem)) if elem is not None else []
                nested_values = []
                for child in children:
                    nested_result = self._validate_tree(child, item_type, permissive, fill_model)
                    if not nested_result.is_valid:
                        errors.append(f"Field {field}[]: {nested_result.error_message}")
                        is_valid = False
                        nested_values.append(None)
                    else:
                        nested_values.append(nested_result.result_type if fill_model else None)
                values[field] = nested_values
                continue

            # Special handling for str and Any
            if expected_type is str:
                if self.has_nested(elem):
                    errors.append(f"Field {field}: Expected a leaf string, but found nested structure.")
                    is_valid = False
                    values[field] = None
                    continue
            if expected_type is Any:
                # Return the subtree as a string from the original text
                values[field] = self.get_subtree_string(elem)
                continue

            # Use type_matcher for leaf fields
            value = self.get_text(elem)
            match_result = self.type_matcher.validate_and_convert(value, expected_type)
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

    def get_subtree_string(self, elem):
        # Default fallback: just str(elem). Should be overridden in subclasses.
        return str(elem)

    async def validate_strict(self, response: str, fill_model: bool = True, **kwargs) -> ValidationResult:
        try:
            tree = self.parse(response)
        except Exception as e:
            if self.generate_hints:
                return ValidationResult(is_valid=False, error_message=f"Invalid file: {e}", hint=f"Please ensure the response is a valid {self.__class__.name}.")
            else:
                return ValidationResult(is_valid=False, error_message=f"Invalid file: {e}")
        if self.model is None:
            return ValidationResult(is_valid=True, validated_text=response, result_type=None)
        return self.validate_strict_recursive(tree, self.model)

    async def validate_permissive(self, response: str, fill_model: bool = True, **kwargs) -> ValidationResult:
        try:
            tree = self.parse(response)
        except Exception as e:
            return ValidationResult(is_valid=False, error_message=f"Invalid file: {e}", hint=self._generate_hint(e))
        
        if self.model is None:
            return ValidationResult(is_valid=True, validated_text=response, result_type=None)
        return self.validate_permissive_recursive(tree, self.model)

    def validate_strict_recursive(self, tree, model):
        """Shallow wrapper for backward compatibility. Calls unified _validate_tree logic."""
        return self._validate_tree(tree, model, permissive=False)

    def validate_permissive_recursive(self, tree, model):
        """Shallow wrapper for backward compatibility. Calls unified _validate_tree logic."""
        return self._validate_tree(tree, model, permissive=True)
    
    def _generate_hint(self, e: Exception):
        hint = f"Please ensure the response is a valid {self.__class__.name()}."
        if isinstance(e, ParsingError):
            if e.original_text is not None:
                preceding_text = e.original_text[:e.original_text.find(e.parsed_text)]
                following_text = e.original_text[e.original_text.find(e.parsed_text) + len(e.parsed_text):]
                
                if preceding_text:
                    hint += f"The response should not include any text before the {self.__class__.name()}. Please do not include texts like {preceding_text} before the {self.__class__.name()} content."
                if following_text:
                    hint += f"The response should not include any text after the {self.__class__.name()}. Please do not include texts like {following_text} after the {self.__class__.name()} content."

        hint += f"Detailed error: {e}."

        return hint 
