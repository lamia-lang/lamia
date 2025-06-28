from abc import ABC, abstractmethod
from ....base import BaseValidator, ValidationResult
import typing
import re
from typing import get_origin, get_args, Any, Union
from lamia.validation.utils.type_matcher import TypeMatcher
from lamia.validation.utils.pydantic_utils import get_pydantic_json_schema
from pydantic import BaseModel
from typing import Callable

# TODO: we can configure type checking to be different from the file validator strict mode with this flag
#STRICT_TYPE_MATCH = False

class BaseValidationError(ValueError):
    """Base exception for validation errors with hint support."""
    def __init__(self, message: str, hint: str = None, original_exception: Exception = None):
        super().__init__(message)
        self.hint = hint
        self.original_exception = original_exception

class TextAroundPayloadError(BaseValidationError):
    def __init__(self, expected_file_format: str, original_text: str, payload_text: str):
        # Generate dynamic message and hint
        message = f"Invalid {expected_file_format}: unexpected text around payload"
        
        hint = f"Please ensure the response is a valid {expected_file_format}."
        
        try:
            preceding_text = original_text[:original_text.find(payload_text)]
            following_text = original_text[original_text.find(payload_text) + len(payload_text):]
            
            if preceding_text:
                hint += f" The response should not include any text before the {expected_file_format}. Please do not include texts like '{preceding_text}' before the {expected_file_format} content."
            if following_text:
                hint += f" The response should not include any text after the {expected_file_format}. Please do not include texts like '{following_text}' after the {expected_file_format} content."
        except (ValueError, AttributeError):
            # Handle cases where find() fails or other text processing issues
            hint += " The response should only contain the expected payload format without any additional text before or after it."
        
        super().__init__(message, hint=hint)

class InvalidPayloadError(BaseValidationError):
    def __init__(self, expected_file_format: str, text: str):
        # Generate dynamic message and hint
        message = f"Invalid {expected_file_format}: no valid {expected_file_format} payload is found in the text: {text}"
        
        hint = f"Please ensure the response is a valid {expected_file_format}."
        
        super().__init__(message, hint=hint)

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
        self.type_matcher = TypeMatcher(strict=strict, get_text_func=self.get_text)

    def parse(self, response: str):
        stripped = response.strip()
        if self.strict:
            payload = response

            if self.generate_hints:
                payload = self.extract_payload(stripped)
                if not payload:
                    raise InvalidPayloadError(
                        expected_file_format=self.file_type(),
                        text=response,
                    )
                if payload != stripped:
                    raise TextAroundPayloadError(
                        expected_file_format=self.file_type(),
                        original_text=response,
                        payload_text=payload
                    )
        else:
            payload = self.extract_payload(stripped)
            if not payload:
                raise InvalidPayloadError(
                    expected_file_format=self.file_type(),
                    text=response,
                )
            
        try:
            return self.load_payload(payload)
        except Exception as e:
            raise InvalidPayloadError(
                expected_file_format=self.file_type(),
                text=payload,
            ) from e

    @classmethod
    @abstractmethod
    def name(cls) -> str:
        pass

    @classmethod
    @abstractmethod
    def file_type(cls) -> str:
        pass

    @abstractmethod
    def _describe_structure(self, model, indent=0):
        """Describe the expected structure from a Pydantic model for this file format."""
        pass

    def _get_model_schema_hint(self) -> str:
        """Get the JSON schema hint for the model. Child classes can use this instead of directly importing schema functions."""
        if self.model is not None:
            schema = get_pydantic_json_schema(self.model)
            return f"Expected target pydantic type in JSON format to be extracted from the {self.file_type().upper()}:\n{schema}"
        return ""

    @property
    def initial_hint(self) -> str:
        if self.model is not None:
            structure_lines = self._describe_structure(self.model)
            schema_hint = self._get_model_schema_hint()
            return (
                f"Please ensure the {self.file_type()} matches the required structure.\n"
                "Expected structure:\n"
                + '\n'.join(structure_lines) + "\n"
                + f"Expected target pydantic type in JSON format to be extracted from the {self.file_type().upper()}:\n"
                + schema_hint
            )
        else:
            return f"Please return only valid {self.file_type()}, with no explanation or extra text."

    @abstractmethod
    def extract_payload(self, response: str) -> str:
        """Extract the relevant data block as a string from the response."""
        pass

    @abstractmethod
    def load_payload(self, payload: str) -> Any:
        """Convert the extracted payload string into a Python object."""
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

    @abstractmethod
    def get_subtree_string(self, elem):
        """Convert an element back to its string representation in the original format."""
        pass

    def _validate_tree(self, tree, model, permissive=False):
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
                nested_result = self._validate_tree(elem, expected_type, permissive)
                if not nested_result.is_valid:
                    errors.append(f"Field {field}: {nested_result.error_message}")
                    is_valid = False
                    values[field] = None
                else:
                    values[field] = nested_result.result_type
                    # Collect nested info loss
                    if nested_result.info_loss:
                        info_loss[field] = nested_result.info_loss
                continue
            # Recursive validation for lists of models
            if is_list_of_models(expected_type):
                item_type = get_args(expected_type)[0]
                children = list(self.iter_direct_children(elem)) if elem is not None else []
                nested_values = []
                field_info_loss = {}
                for idx, child in enumerate(children):
                    nested_result = self._validate_tree(child, item_type, permissive)
                    if not nested_result.is_valid:
                        errors.append(f"Field {field}[{idx}]: {nested_result.error_message}")
                        is_valid = False
                        nested_values.append(None)
                    else:
                        nested_values.append(nested_result.result_type)
                        # Collect nested info loss
                        if nested_result.info_loss:
                            field_info_loss[f"item_{idx}"] = nested_result.info_loss
                values[field] = nested_values
                if field_info_loss:
                    info_loss[field] = field_info_loss
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
                # Collect type conversion info loss
                if match_result.info_loss:
                    info_loss[field] = match_result.info_loss

        model_instance = None
        if is_valid:
            try:
                model_instance = model(**values)
            except Exception as e:
                errors.append(f"Model fill error: {e}")
                is_valid = False

        error_message = '; '.join(errors) if errors else None
        return ValidationResult(
            is_valid=is_valid,
            result_type=model_instance,
            validated_text=self.get_subtree_string(tree),
            error_message=error_message,
            info_loss=info_loss if info_loss else None
        )

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        return self._validare_with_error_handling(response, self.validate_strict_recursive)

    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        return self._validare_with_error_handling(response, self.validate_permissive_recursive)

    def validate_strict_recursive(self, tree, model):
        """Shallow wrapper for backward compatibility. Calls unified _validate_tree logic."""
        return self._validate_tree(tree, model, permissive=False)

    def validate_permissive_recursive(self, tree, model):
        """Shallow wrapper for backward compatibility. Calls unified _validate_tree logic."""
        return self._validate_tree(tree, model, permissive=True)
    
    def _validare_with_error_handling(self, response: str, callback: Callable):
        try:
            tree = self.parse(response)
            if self.model is None:
                return ValidationResult(is_valid=True, validated_text=self.get_subtree_string(tree), result_type=None)
            return callback(tree, self.model)
        except Exception as e:
            if self.generate_hints:
                hint = self.get_retry_hint(e, e.hint if isinstance(e, BaseValidationError) and e.hint else "")
                return ValidationResult(is_valid=False, error_message=f"Invalid file: {str(e)}", hint=hint)
            else:
                return ValidationResult(is_valid=False, error_message=f"Invalid file: {str(e)}")
