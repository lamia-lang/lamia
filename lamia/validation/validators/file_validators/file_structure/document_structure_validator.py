from abc import ABC, abstractmethod
from ....base import BaseValidator, ValidationResult
import typing
import re
import logging
from typing import get_origin, get_args, Any, Union, Optional, List, Iterator, Type
from lamia.validation.utils.type_matcher import TypeMatcher
from lamia.validation.utils.pydantic_utils import get_pydantic_json_schema, get_ordered_dict_fields
from pydantic import BaseModel, create_model
from typing import Callable
from collections import OrderedDict
from pydantic import create_model
import json

# TODO: we can configure type checking to be different from the file validator strict mode with this flag
#STRICT_TYPE_MATCH = False

SHOULD_GENERATE_JSON_SCHEMA = True

logger = logging.getLogger(__name__)

class BaseValidationError(ValueError):
    """Base exception for validation errors with hint support."""
    def __init__(self, message: str, hint: str = None, original_exception: Exception = None):
        super().__init__(message)
        self.hint = hint
        self.original_exception = original_exception

class TextAroundPayloadError(BaseValidationError):
    def __init__(self, expected_file_format: str, original_text: str, payload_text: str):
        # Generate dynamic message and hint
        message = f"Invalid {expected_file_format}: unexpected text around payload: {original_text}"
        
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
    def __init__(self, expected_file_format: str, text: str, parse_error: Optional[Exception] = None):
        cause_detail = f" Cause: {parse_error}" if parse_error else ""
        message = (
            f"Invalid {expected_file_format}: no valid {expected_file_format} payload "
            f"is found in the text: {text}{cause_detail}"
        )
        hint = f"Please ensure the response is a valid {expected_file_format}."
        
        super().__init__(message, hint=hint)

class DuplicateKeyError(BaseValidationError):
    def __init__(self, key, filetype="object"):
        super().__init__(f"Duplicate key detected in {filetype}: '{key}'") 

def is_optional(field_type: Any) -> bool:
    return get_origin(field_type) is Union and type(None) in get_args(field_type)

def is_any(field_type: Any) -> bool:
    return field_type is Any

def validate_field_presence(field_name: str, field_type: Any, data: dict, mode: str) -> bool:
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

def is_pydantic_model(field_type: Any) -> bool:
    try:
        return issubclass(field_type, BaseModel)
    except TypeError:
        return False

def is_list_of_models(field_type: Any) -> bool:
    origin = get_origin(field_type)
    args = get_args(field_type)
    return origin in (list, typing.List) and args and is_pydantic_model(args[0])





class DocumentStructureValidator(BaseValidator, ABC):
    def __init__(self, model: Optional[Type[BaseModel]] = None, strict: bool = True, generate_hints: bool = False) -> None:
        super().__init__(strict=strict, generate_hints=generate_hints)
        
        # FAIL FAST: OrderedDict patterns validation before anything else
        if model is not None:
            self._validate_no_raw_ordered_dict_patterns(model, "model")
        
        self.model = model
        self.type_matcher = TypeMatcher(strict=strict, get_text_func=self.get_text)
        self.strict = strict
        self.generate_hints = generate_hints

    def _validate_no_raw_ordered_dict_patterns(self, obj: Any, context: str = "model") -> None:
        """Recursively validate that OrderedDict is not used as entire model or in type annotations.
        
        OrderedDict as entire model is no longer supported. Use BaseModel with '__ordered_fields__' 
        class attribute instead.
        
        Args:
            obj: The object/type to validate (can be BaseModel, OrderedDict, type annotation, etc.)
            context: Description of where this object is found (for error messages)
            
        Raises:
            ValueError: If OrderedDict is found as entire model at any nesting level
        """
        # Check if the object is OrderedDict (either instance or type)
        if isinstance(obj, OrderedDict) or obj is OrderedDict:
            raise ValueError(f"OrderedDict in {context} is not supported. "
                           "Use BaseModel with '__ordered_fields__' class attribute instead.")
        
        # If it's a Pydantic model class, check its fields recursively
        if isinstance(obj, type) and issubclass(obj, BaseModel):
            for field_name, field_info in obj.model_fields.items():
                field_type = field_info.annotation
                self._validate_no_raw_ordered_dict_patterns(field_type, f"field '{field_name}'")
        
        # Handle generic types (Union, List, Optional, etc.)
        origin = get_origin(obj)
        args = get_args(obj)
        
        if origin is not None and args:
            # Check each type argument recursively
            for arg in args:
                self._validate_no_raw_ordered_dict_patterns(arg, context)

    def parse(self, response: str) -> Any:
        stripped = self.strip_markdown_fences(response.strip())
        if self.strict:
            payload = stripped

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
        except BaseValidationError:
            # Let semantic validation errors (like DuplicateHeaderError) bubble up unchanged
            raise
        except Exception as e:
            raise InvalidPayloadError(
                expected_file_format=self.file_type(),
                text=payload,
                parse_error=e,
            ) from e

    def prepare_content_for_write(self, existing_content: str, new_content: str) -> str:
        """Structured documents (HTML, JSON, XML, YAML) overwrite by default."""
        return new_content

    @classmethod
    @abstractmethod
    def name(cls) -> str:
        pass

    @classmethod
    @abstractmethod
    def file_type(cls) -> str:
        pass

    @abstractmethod
    def _describe_structure(self, model: BaseModel, indent: int = 0) -> List[str]:
        """Describe the expected structure from a Pydantic model for this file format."""
        pass

    def _generate_field_ordering_hint(self, model: BaseModel, prefix: str = "") -> str:
        """Generate user-friendly field ordering information.
        
        Args:
            model: The Pydantic model to analyze
            prefix: Prefix for nested fields (e.g., "mysubmodel.")
            
        Returns:
            Clean ordering hint text or empty string if no ordering needed
        """
        ordered_fields = get_ordered_dict_fields(model)
        if not ordered_fields:
            return ""
        
        hints = []
        
        # Generate simple ordering hint for top-level fields
        if len(ordered_fields) > 1:
            # Add prefix to field names for nested structures
            prefixed_fields = [f"{prefix}{field}" for field in ordered_fields]
            field_list = ", ".join(prefixed_fields)
            
            # Generate pairwise ordering relationships
            ordering_pairs = []
            for i in range(len(prefixed_fields) - 1):
                ordering_pairs.append(f"{prefixed_fields[i]} should come before {prefixed_fields[i+1]}")
            
            if len(ordering_pairs) == 1:
                hints.append(f"ORDERING: {ordering_pairs[0]}")
            else:
                hints.append(f"ORDERING: {field_list} - key order within these fields must be preserved!")
        
        # Recursively check nested models for additional ordering requirements
        # We need to map __ordered_fields__ keys to actual model fields
        if hasattr(model, '__ordered_fields__') and hasattr(model, 'model_fields'):
            ordered_dict = model.__ordered_fields__
            model_fields = model.model_fields
            
            # Create mapping between ordered fields and actual model fields by type matching
            for ordered_key, ordered_type in ordered_dict.items():
                # Find matching actual field by type
                matching_actual_field = None
                for actual_field_name, field_info in model_fields.items():
                    if field_info.annotation == ordered_type:
                        matching_actual_field = actual_field_name
                        break
                
                if matching_actual_field and is_pydantic_model(ordered_type):
                    # Generate nested hints with both actual field name and ordered field key as prefixes
                    actual_prefix = f"{prefix}{matching_actual_field}."
                    ordered_prefix = f"{prefix}{ordered_key}."
                    
                    # Get nested hints with actual field name prefix
                    actual_nested_hint = self._generate_field_ordering_hint(ordered_type, actual_prefix)
                    if actual_nested_hint:
                        hints.append(actual_nested_hint)
                    
                    # Get nested hints with ordered field key prefix
                    ordered_nested_hint = self._generate_field_ordering_hint(ordered_type, ordered_prefix)
                    if ordered_nested_hint:
                        hints.append(ordered_nested_hint)
                
                # Handle Optional[BaseModel] types
                elif matching_actual_field and hasattr(ordered_type, '__args__'):
                    for arg in ordered_type.__args__:
                        if is_pydantic_model(arg):
                            actual_prefix = f"{prefix}{matching_actual_field}."
                            ordered_prefix = f"{prefix}{ordered_key}."
                            
                            actual_nested_hint = self._generate_field_ordering_hint(arg, actual_prefix)
                            if actual_nested_hint:
                                hints.append(actual_nested_hint)
                            
                            ordered_nested_hint = self._generate_field_ordering_hint(arg, ordered_prefix)
                            if ordered_nested_hint:
                                hints.append(ordered_nested_hint)
        
        return "\n".join(hints)

    @property
    def initial_hint(self) -> str:
        if self.model is not None:
            # Generate original structure description (unchanged)
            structure_lines = self._describe_structure(self.model)
            
            # Generate JSON schema (unchanged)
            schema = get_pydantic_json_schema(self.model)
            
            # Build the base hint exactly as before, but without ordering warnings
            base_hint = (
                f"Please ensure the {self.file_type()} matches the required structure.\n"
                "Expected structure:\n"
                + '\n'.join(structure_lines) + "\n\n"
                + f"Expected target pydantic type in JSON format to be extracted from the {self.file_type().upper()}:\n"
                + schema
            )
            
            # Generate clean ordering information to append
            ordering_hint = self._generate_field_ordering_hint(self.model)
            if ordering_hint:
                return base_hint + "\n\n" + ordering_hint
            else:
                return base_hint
        else:
            return f"Please return only valid {self.file_type()}, with no explanation or extra text."

    def _get_model_schema_hint(self) -> str:
        """Generate the JSON schema hint for this model."""
        if self.model is not None:
            if not SHOULD_GENERATE_JSON_SCHEMA:
                return ""
            schema = get_pydantic_json_schema(self.model)
            return f"Expected target pydantic type in JSON format to be extracted from the {self.file_type().upper()}:\n{schema}"
        return ""

    @abstractmethod
    def extract_payload(self, response: str) -> str | None:
        """Extract the relevant data block as a string from the response.
        
        This method should locate and extract the valid payload content from the LLM response,
        handling both cases where the payload is embedded in markdown code blocks and where 
        it appears as plain text.
        
        Args:
            response: The full response string from the LLM that may contain extra text
            
        Returns:
            str: The extracted clean payload if valid content is found
            None: If no valid payload can be extracted from the response
            
        Examples:
            For JSON validator:
            - Input: "Here's the JSON: ```json\n{\"key\": \"value\"}\n```"
            - Returns: "{\"key\": \"value\"}"
            
            - Input: "No JSON content here"
            - Returns: None
        """
        pass

    @abstractmethod
    def load_payload(self, payload: str) -> Any:
        """Convert the extracted payload string into a Python object.
        
        This method parses the clean payload string (returned by extract_payload) 
        into the appropriate Python data structure for the file format.
        
        Args:
            payload: A clean payload string (never None - that case is handled before this method)
            
        Returns:
            Any: The parsed Python object (dict, list, ElementTree, etc.)
            
        Raises:
            Exception: Should raise appropriate parsing exceptions for invalid payloads
                      (these will be caught and converted to InvalidPayloadError by the framework)
                      
        Examples:
            For JSON validator:
            - Input: "{\"key\": \"value\"}"
            - Returns: {"key": "value"}
            
            For XML validator:
            - Input: "<root><item>value</item></root>"
            - Returns: ElementTree object
        """
        pass

    @abstractmethod
    def find_element(self, tree: Any, key: str) -> Any:
        """Find an element or field in the parsed structure.
        
        This method searches for a direct child element/field with the given key
        in the parsed tree structure. Used during strict validation to match
        Pydantic model fields.
        
        Args:
            tree: The parsed data structure (result of load_payload)
            key: The name/key/tag to search for
            
        Returns:
            Any: The found element/value if the key exists
            None: If the key is not found
            
        Examples:
            For JSON (tree = {"name": "John", "age": 30}):
            - find_element(tree, "name") -> "John"
            - find_element(tree, "missing") -> None
            
            For XML (tree = <root><name>John</name></root>):
            - find_element(tree, "name") -> <name>John</name> element
        """
        pass

    @abstractmethod
    def get_text(self, element: Any) -> Any:
        """Extract text or primitive value from an element.
        
        This method extracts the actual value/content from a parsed element,
        converting it to the appropriate Python primitive type.
        
        Args:
            element: An element from the parsed structure
            
        Returns:
            Any: The primitive value (str, int, float, bool, list, dict, None)
            
        Examples:
            For JSON: element = "hello" -> returns "hello"
            For XML: element = <name>John</name> -> returns "John"
            For YAML: element = 42 -> returns 42
        """
        pass

    @abstractmethod
    def has_nested(self, element: Any) -> bool:
        """Return True if the element has nested elements/fields (not just text).
        
        This method determines whether an element contains nested structure
        that requires recursive validation, or if it's a leaf node with
        primitive content.
        
        Args:
            element: An element from the parsed structure
            
        Returns:
            bool: True if the element has nested structure, False for primitives
            
        Examples:
            For JSON:
            - has_nested({"name": "John"}) -> True (dict with fields)
            - has_nested("hello") -> False (primitive string)
            - has_nested([1, 2, 3]) -> True (list with items)
            
            For XML:
            - has_nested(<person><name>John</name></person>) -> True (has children)
            - has_nested(<name>John</name>) -> False (text content only)
        """
        pass

    @abstractmethod
    def iter_direct_children(self, tree: Any) -> Iterator[Any]:
        """Iterate over direct children of the tree/element.
        
        This method yields the immediate child elements of a tree/element,
        used for recursive traversal during validation. Should only yield
        direct children, not all descendants.
        
        Args:
            tree: The parsed data structure or element
            
        Yields:
            Any: Direct child elements/values
            
        Examples:
            For JSON dict {"a": 1, "b": {"c": 2}}:
            - Yields: 1, {"c": 2}
            
            For JSON list [1, 2, {"x": 3}]:
            - Yields: 1, 2, {"x": 3}
            
            For XML <root><a>1</a><b><c>2</c></b></root>:
            - Yields: <a>1</a>, <b><c>2</c></b>
        """
        pass

    @abstractmethod
    def get_name(self, element: Any) -> Optional[str]:
        """Get the name/tag/field of the element.
        
        This method extracts the identifier/name of an element, which is
        format-specific (XML tag name, JSON key, etc.).
        
        Args:
            element: An element from the parsed structure
            
        Returns:
            str | None: The name/tag/key of the element, or None if not applicable
            
        Examples:
            For XML element <person>John</person>: returns "person"
            For JSON this method might not be used (keys handled in iteration)
            For HTML element <div class="content">: returns "div"
        """
        pass

    @abstractmethod
    def find_all(self, tree: Any, key: str) -> List[Any]:
        """Find all elements/fields with the given key anywhere in the tree.
        
        This method performs a recursive search through the entire tree structure
        to find all occurrences of elements with the specified key/tag/name.
        Used for permissive validation where fields might be nested anywhere.
        
        Args:
            tree: The parsed data structure to search
            key: The name/key/tag to search for
            
        Returns:
            List[Any]: List of all matching elements/values (empty list if none found)
            
        Examples:
            For JSON {"a": {"name": "John"}, "b": {"name": "Jane"}}:
            - find_all(tree, "name") -> ["John", "Jane"]
            
            For XML <root><person><name>John</name></person><item><name>Item1</name></item></root>:
            - find_all(tree, "name") -> [<name>John</name>, <name>Item1</name>]
        """
        pass

    @abstractmethod
    def get_subtree_string(self, elem: Any) -> str:
        """Convert an element back to its string representation in the original format.
        
        This method serializes an element back to its original format string,
        used for error reporting and debugging to show users what was found
        vs what was expected.
        
        Args:
            elem: An element from the parsed structure
            
        Returns:
            str: String representation in the original format
            
        Examples:
            For JSON element {"name": "John"}: returns '{"name": "John"}'
            For XML element <person>John</person>: returns "<person>John</person>"
            For YAML element {name: John}: returns "name: John"
        """
        pass

    @abstractmethod
    def get_field_order(self, tree: Any) -> List[str]:
        """Get the order of fields/keys/tags as they appear in the parsed document.
        
        This method is used for OrderedDict validation to ensure that fields
        appear in the expected order within the document structure.
        
        Args:
            tree: The parsed data structure (root level for the validation)
            
        Returns:
            List[str]: List of field names in the order they appear in the document
            
        Examples:
            For JSON {"title": "Test", "count": 5}: returns ["title", "count"]
            For XML <root><title>Test</title><count>5</count></root>: returns ["title", "count"]
            For HTML with child elements: returns list of child tag names in order
        """
        pass

    def _combine_tag_and_selector(self, tag: str, selector: str) -> str:
        """Combine tag name with selector. Helper for tag-based validators (HTML/XML).
        
        Args:
            tag: The tag name (e.g., 'div', 'span')
            selector: The selector from json_schema_extra (e.g., '.class', '#id')
            
        Returns:
            Combined selector string
            
        Raises:
            ValueError: If selector already contains the tag name
        """
        # Detect if selector already contains tag name
        if self._selector_contains_tag(tag, selector):
            raise ValueError(f"Selector '{selector}' already contains tag '{tag}'. Use just the attribute part (e.g., '.class' not 'div.class').")
        
        # CSS selector combining
        if selector.startswith(('.', '#', ':', '[')):
            return f"{tag}{selector}"  # div.class, span#id, input[type='text']
        elif selector.startswith(' '):
            return f"{tag}{selector}"  # div > child, span + sibling
        elif selector.startswith('//') or selector.startswith('/'):
            # XPath - prepend tag to path
            if selector.startswith('//'):
                return f"//{tag}{selector[2:]}"
            else:
                return f"/{tag}{selector[1:]}"
        else:
            # Full selector override - use as-is
            return selector

    def _selector_contains_tag(self, tag: str, selector: str) -> bool:
        """Check if selector already contains the tag name.
        
        Args:
            tag: The tag name to check for
            selector: The selector string
            
        Returns:
            True if selector already contains the tag
        """
        # CSS: check if starts with tag name followed by selector chars
        css_indicators = ['.', '#', '[', ':']
        for indicator in css_indicators:
            if selector.startswith(f"{tag}{indicator}"):
                return True
        
        # XPath: check if contains tag in path
        xpath_patterns = [f"/{tag}[", f"//{tag}[", f"/{tag}.", f"//{tag}."]
        for pattern in xpath_patterns:
            if pattern in selector:
                return True
                
        return False

    def get_selector_for_field(self, field_name: str, field_info: Any) -> str:
        """Get selector for field. Default implementation for key-based formats (JSON, YAML, CSV).
        
        For key-based formats, selectors don't make sense, so always return field name.
        Tag-based formats (HTML, XML) should override this method.
        
        Args:
            field_name: The field name
            field_info: Pydantic field info object
            
        Returns:
            The selector string to use for finding elements/values
        """
        # For key-based formats, ignore selectors and just return field name
        return field_name

    def _check_element_existence_ignoring_types(self, tree, selector):
        """Check if element exists when ignoring type constraints completely.
        
        When we encounter a missing element, we re-search ignoring all type constraints
        to determine if the element exists but was filtered due to type mismatches.
        
        Args:
            tree: The parsed data structure to search
            selector: The selector to search for
            
        Returns:
            bool: True if element exists (ignoring types), False if truly missing
        """
        # Find all elements matching the selector, ignoring any type constraints
        all_elements = self.find_all(tree, selector)
        return len(all_elements) > 0

    def _validate_tree(self, tree, model, permissive=False):
        errors = []
        values = {}
        is_valid = True
        info_loss = {}

        # Handle both Pydantic BaseModel and OrderedDict cases
        if isinstance(model, dict):  # OrderedDict is a dict
            model_fields = list(model.items())
            is_ordered_dict = True
        else:  # Pydantic BaseModel
            # PATCH: If model has __ordered_fields__, always create a dynamic model with only those fields
            if hasattr(model, '__ordered_fields__') and isinstance(model.__ordered_fields__, OrderedDict):
                dynamic_model_fields: dict[str, tuple[type, Any]] = {}
                for field_name, field_info in model.model_fields.items():
                    dynamic_model_fields[field_name] = (getattr(field_info, "annotation", field_info), ...)

                for field_name, field_type in model.__ordered_fields__.items():
                    dynamic_model_fields[field_name] = (field_type, ...)

                # Create a brand-new model class that merges both sets.
                original_ordered_fields = model.__ordered_fields__
                model = create_model(f"{model.__name__}Dynamic", **dynamic_model_fields)  # type: ignore[arg-type]
                model.__ordered_fields__ = original_ordered_fields  # type: ignore[attr-defined]
                model_fields = [(fname, finfo) for fname, finfo in model.model_fields.items()]
                for fname, ftype in model.__ordered_fields__.items():
                    if fname not in {name for name, _ in model_fields}:  # avoid duplicates
                        model_fields.append((fname, ftype))
            else:
                model_fields = [(field, field_info) for field, field_info in model.model_fields.items()]
            is_ordered_dict = False

        # Check field order enforcement for OrderedDict or BaseModel with __ordered_fields__
        needs_order_check = (is_ordered_dict and isinstance(model, OrderedDict)) or \
                           (not is_ordered_dict and hasattr(model, '__ordered_fields__') and isinstance(model.__ordered_fields__, OrderedDict))
        
        if needs_order_check:
            # Get the actual field order from the parsed document using the abstract method
            actual_field_order = self.get_field_order(tree)
            if is_ordered_dict:
                expected_field_order = [field for field, _ in model_fields]
            else:  # BaseModel with __ordered_fields__
                expected_field_order = list(model.__ordered_fields__.keys())
            # Only consider fields that are present in both expected and actual
            relevant_actual_fields = [f for f in actual_field_order if f in expected_field_order]
            relevant_expected_fields = [f for f in expected_field_order if f in relevant_actual_fields]
            if relevant_actual_fields != relevant_expected_fields:
                errors.append(f"Field order mismatch: expected order {relevant_expected_fields} but found {relevant_actual_fields}")
                is_valid = False
                return ValidationResult(
                    is_valid=is_valid,
                    typed_result=None,
                    validated_text=self.get_subtree_string(tree),
                    error_message='; '.join(errors),
                    info_loss=None
                )

        # --- Support ordered field selection in permissive mode ---
        last_selected_position = -1
        ordered_fields_seq = None
        tree_string_cache = None

        if permissive and not is_ordered_dict and hasattr(model, "__ordered_fields__") and isinstance(model.__ordered_fields__, OrderedDict):
            ordered_fields_seq = list(model.__ordered_fields__.keys())
            try:
                # Use validator-specific string conversion for reliable ordering checks
                tree_string_cache = self.get_subtree_string(tree)
            except Exception:
                tree_string_cache = None

        for field_name, field_info_or_type in model_fields:
            if is_ordered_dict or isinstance(field_info_or_type, type):
                expected_type = field_info_or_type  # For OrderedDict or __ordered_fields__, it's directly the type
                field_info = None  # No field info for OrderedDict
                field = field_name  # Keep original field name
            else:
                expected_type = field_info_or_type.annotation  # For BaseModel, it's field_info.annotation
                field_info = field_info_or_type
                # Use alias if available, otherwise use original field name
                field = field_info.alias if field_info.alias else field_name

            # Get the appropriate selector for this field (using original field_name for tag-based searching)
            selector = self.get_selector_for_field(field_name, field_info)

            if permissive:
                elems = self.find_all(tree, selector)
                
                # For string fields, prefer leaf nodes (no nested content)
                if expected_type is str:
                    elems = [elem for elem in elems if not self.has_nested(elem)]

                # When multiple matches exist, prefer a direct child of the current tree (root-level field)
                prefer_direct = isinstance(tree, dict) or last_selected_position >= 0
                if len(elems) > 1 and prefer_direct:
                    direct_candidate = self.find_element(tree, selector)
                    if direct_candidate is not None and direct_candidate in elems:
                        # Apply same leaf filtering constraint for strings
                        if not (expected_type is str and self.has_nested(direct_candidate)):
                            elems = [direct_candidate]

                # When ordered fields are defined, ensure we only consider elements that appear after the last selected one
                if ordered_fields_seq is not None and tree_string_cache is not None and last_selected_position >= 0:
                    valid_elems = []
                    for i, elem in enumerate(elems):
                        try:
                            elem_str = self.get_subtree_string(elem)
                            pos = tree_string_cache.find(elem_str)
                            if pos > last_selected_position:
                                valid_elems.append(elem)
                        except Exception as e:
                            pass
                    # If filtering removes all candidates, fall back to original list to avoid false negatives
                    elems = valid_elems if valid_elems else elems

                elem = elems[0] if elems else None
            else:
                elem = self.find_element(tree, selector)
                
                # For string fields, ensure it's a leaf node
                if elem and expected_type is str and self.has_nested(elem):
                    elem = None

            # --- Update last_selected_position for ordered field traversal ---
            if elem is not None and ordered_fields_seq is not None and tree_string_cache is not None:
                try:
                    # Generalize: if elem is a non-empty list, use last item's string; else use elem's string
                    if isinstance(elem, list) and elem:
                        last_item_str = self.get_subtree_string(elem[-1])
                        pos = tree_string_cache.find(last_item_str)
                        if pos >= 0:
                            last_selected_position = pos + len(last_item_str)
                    else:
                        elem_str_pos = self.get_subtree_string(elem)
                        pos = tree_string_cache.find(elem_str_pos)
                        if pos >= 0:
                            last_selected_position = pos + len(elem_str_pos)
                except Exception:
                    pass

            if elem is None:
                if is_optional(expected_type):
                    values[field] = None
                    continue
                    
                # Check element existence when we encounter a missing element, ignoring types
                element_found_but_filtered = self._check_element_existence_ignoring_types(tree, selector)
                
                if element_found_but_filtered:
                    errors.append(f"Field '{field_name}': Element found but filtered out due to type constraint. Field type '{expected_type.__name__}' expects different content structure. Consider using 'Any' type for container elements.")
                else:
                    # Log detailed information about the missing element
                    logger.warning(f"Validation failed: Could not find element with selector '{selector}' for field '{field_name}'")
                    errors.append(f"Missing <{field_name}>: selector '{selector}' not found")
                is_valid = False
                continue

            # Recursive validation for nested models
            if is_pydantic_model(expected_type):
                nested_result = self._validate_tree(elem, expected_type, permissive)
                if not nested_result.is_valid:
                    errors.append(f"Field {field_name}: {nested_result.error_message}")
                    is_valid = False
                    values[field] = None
                else:
                    values[field] = nested_result.typed_result
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
                        nested_values.append(nested_result.typed_result)
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
                    errors.append(f"Field {field_name}: Expected a leaf string, but found nested structure.")
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
                errors.append(f"Field {field_name}: {match_result.error}")
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
                if is_ordered_dict:
                    # For OrderedDict, preserve the original field order
                    model_instance = OrderedDict()
                    for field, _ in model_fields:
                        if field in values:
                            model_instance[field] = values[field]
                else:
                    # Always use the dynamic model instance for __ordered_fields__
                    model_instance = model(**values)
                    # Ensure ordered field values are accessible as attributes even if they are not declared
                    if hasattr(model, '__ordered_fields__') and isinstance(model.__ordered_fields__, OrderedDict):
                        for field_name in model.__ordered_fields__.keys():
                            if field_name in values and not hasattr(model_instance, field_name):
                                setattr(model_instance, field_name, values[field_name])
            except Exception as e:
                errors.append(f"Model fill error: {e}")
                is_valid = False

        error_message = '; '.join(errors) if errors else None

        return ValidationResult(
            is_valid=is_valid,
            typed_result=model_instance,
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
                return ValidationResult(is_valid=True, validated_text=self.get_subtree_string(tree), typed_result=None)
            return callback(tree, self.model)
        except Exception as e:
            if self.generate_hints:
                hint = self.get_retry_hint(e, e.hint if isinstance(e, BaseValidationError) and e.hint else "")
                return ValidationResult(is_valid=False, error_message=f"Invalid file: {str(e)}", hint=hint)
            else:
                return ValidationResult(is_valid=False, error_message=f"Invalid file: {str(e)}")
