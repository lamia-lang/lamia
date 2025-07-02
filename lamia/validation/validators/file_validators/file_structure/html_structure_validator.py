from pydantic import BaseModel, create_model
from bs4 import BeautifulSoup
import re
from .document_structure_validator import DocumentStructureValidator, TextAroundPayloadError
from ....base import ValidationResult
from .utils import import_model_from_path
from typing import Any, List
from .document_structure_validator import InvalidPayloadError
import json
import typing

class HTMLStructureValidator(DocumentStructureValidator):
    """Validates if the HTML matches a given Pydantic model structure.
    - Accepts a Pydantic model class or a string (model name or full dotted path).
    - Can be used from config (with model name or full path) or from Lamia(...) constructor (with model class).
    """
    def __init__(self, model: BaseModel = None, model_name: str = None, schema: dict = None, strict: bool = True, model_module: str = "models", generate_hints: bool = False):
        if model is not None:
            resolved_model = model
        elif model_name is not None:
            resolved_model = import_model_from_path(model_name, default_module=model_module)
        elif schema is not None:
            resolved_model = create_model("HTMLStructureModel", **schema)
        else:
            resolved_model = None
        super().__init__(model=resolved_model, strict=strict, generate_hints=generate_hints)

    @classmethod
    def name(cls) -> str:
        return "html_structure"
    
    @classmethod
    def file_type(cls) -> str:
        return "html"

    @property
    def initial_hint(self) -> str:
        if self.model is not None:
            structure_lines = self._describe_structure(self.model)
            json_schema_str = self._get_model_schema_hint()
            
            # Build base hint
            if self.strict:
                base_hint = (
                    "Please ensure the HTML matches the required structure exactly.\n" +
                    "Expected structure (as direct children under <html>):\n" +
                    '\n'.join(structure_lines) + "\n" +
                    json_schema_str
                )
            else:
                base_hint = (
                    "Please ensure the HTML contains the required fields somewhere in the structure.\n" +
                    "The fields can be nested within other HTML elements like <body>, <div>, etc.\n" +
                    "Required fields that must be present somewhere under <html> root tags:\n" +
                    '\n'.join(structure_lines) + "\n" +
                    json_schema_str
                )
            
            # Add clean ordering information  
            ordering_hint = self._generate_field_ordering_hint(self.model)
            if ordering_hint:
                return base_hint + "\n\n" + ordering_hint
            else:
                return base_hint
        else:
            return "Please return only the HTML code, starting with <html> and ending with </html>, with no explanation or extra text."

    def extract_payload(self, response: str) -> str:
        match = re.search(r'(<html[\s\S]*?</html>)', response, re.IGNORECASE)
        return match.group(1) if match else None

    def load_payload(self, payload: str) -> Any:
        if self.strict:
            # TODO: The folowing logic might need to be changed.
            # Beautifulsoup can perfectly parse even if the LLM is chatty around the HTML tag,
            # We fail intentionally here to have the same behavior as other validators.
            # Also, if there will be a lot of requests to get HTMLs from the LLM, this can save the token usage
            html_match = re.search(r'(<html[\s\S]*?</html>)', payload, re.IGNORECASE)
            if not html_match:
                raise InvalidPayloadError(
                    expected_file_format=self.file_type(),
                    text=payload,
                )
            else:
                html_content = html_match.group(1)
                # Check if there's extra text around the HTML content
                if payload.strip() != html_content.strip():
                    raise TextAroundPayloadError(
                        expected_file_format=self.file_type(),
                        original_text=payload,
                        payload_text=html_content
                    )
                else:
                    return BeautifulSoup(html_content, "html.parser")
        else:
            return BeautifulSoup(payload, "html.parser")

    def find_element(self, tree, key):
        # Only direct children that are tags
        for child in tree.children:
            if getattr(child, 'name', None) == key:
                return child
        return None

    def get_text(self, element):
        text = element.get_text(strip=True) if element else None
        return text
        
    def extract_html_text_for_string_field(self, element, field_name):
        """Extract text content for string fields, handling nested HTML structures.
        
        For HTML, we need special logic to handle cases where string fields
        should extract specific parts of nested content.
        """
        if not element:
            return None
            
        element_name = getattr(element, 'name', None)
        
        # For ordered fields, we need to respect the fact that string fields 
        # should be leaf nodes (no nested elements)
        if element_name == field_name:
            return element.get_text(strip=True)
            
        # Default behavior
        return element.get_text(strip=True)

    def has_nested(self, element):
        # Returns True if there are any tag children
        return any(getattr(child, 'name', None) for child in element.children)

    def iter_direct_children(self, tree):
        # Only yield children that are tags
        return (child for child in tree.children if getattr(child, 'name', None) is not None)

    def get_name(self, element):
        return getattr(element, 'name', None)

    def find_all(self, tree, key):
        return tree.find_all(key)

    def get_subtree_string(self, elem):
        # For HTML, return the tag as a string
        return str(elem)

    def get_field_order(self, tree):
        """Get the order of child element names as they appear in the HTML."""
        return [child.name for child in tree.children if hasattr(child, 'name') and child.name]
    


    # Overrides the base class method to add the <html> tag to the tree
    # TODO: Can be done by adding html field to the model, but this is a good demonstration that base class can be overridden
    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        try:
            tree = self.parse(response)
        except Exception as e:
            error_msg = f"Invalid file: {str(e)}"
            return ValidationResult(
                is_valid=False,
                error_message=error_msg,
                hint=self.get_retry_hint(error=e)
            )
        # If the root has an <html> element, start validation from there
        if self.model is None:
            return ValidationResult(
                is_valid=True,
                result_type=None,
                validated_text=self.get_subtree_string(tree),
                raw_text=response
            )
        html_elem = self.find_element(tree, "html")
        if html_elem is not None:
            tree = html_elem
        else:
            error_msg = "No <html> tag found"
            return ValidationResult(
                is_valid=False,
                error_message=error_msg,
                hint=self.get_retry_hint(retry_hint=error_msg)
            )
        return self.validate_strict_recursive(tree, self.model)

    # Overrides the base class method to add the <html> tag to the tree
    # TODO: Can be done by adding html field to the model, but this is a good demonstration that base class can be overridden
    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        try:
            tree = self.parse(response)
        except Exception as e:
            error_msg = f"Invalid file: {str(e)}"
            return ValidationResult(
                is_valid=False,
                error_message=error_msg,
                hint=self.get_retry_hint(error=e)
            )
        if self.model is None:
            return ValidationResult(
                is_valid=True,
                result_type=None,
                validated_text=self.get_subtree_string(tree),
                raw_text=response
            )
        # If the root has an <html> element, start validation from there
        html_elem = self.find_element(tree, "html")
        if html_elem is not None:
            tree = html_elem
        else:
            error_msg = "No <html> tag found"
            return ValidationResult(
                is_valid=False,
                error_message=error_msg,
                hint=self.get_retry_hint(retry_hint=error_msg)
            )
        return self.validate_permissive_recursive(tree, self.model)

    def _describe_structure(self, model, indent=0):
        lines = []
        prefix = '  ' * indent
        for field, field_info in model.model_fields.items():
            submodel = field_info.annotation
            if hasattr(submodel, "model_fields"):
                lines.append(f'{prefix}<{field}>')
                lines.extend(self._describe_structure(submodel, indent + 1))
                lines.append(f'{prefix}</{field}>')
            else:
                # Always show type-specific hints for better LLM guidance
                type_hint = self._get_type_hint(submodel)
                lines.append(f'{prefix}<{field}>{type_hint}</{field}>')
        return lines

    def _get_type_hint(self, annotation):
        """Get a user-friendly type hint for the annotation."""
        if annotation == str:
            return "string value"
        elif annotation == int:
            return "integer value"
        elif annotation == float:
            return "float value"
        elif annotation == bool:
            return "boolean value"
        else:
            return "value"
            
    def _validate_tree(self, tree, model, permissive=False):
        """Override base validation to handle HTML-specific string field extraction."""
        from collections import OrderedDict
        from typing import get_origin, get_args, Any, Union
        from lamia.validation.utils.type_matcher import TypeMatcher
        from ....base import ValidationResult
        
        def is_optional(field_type: Any) -> bool:
            return get_origin(field_type) is Union and type(None) in get_args(field_type)

        def is_any(field_type: Any) -> bool:
            return field_type is Any

        def is_pydantic_model(field_type: Any) -> bool:
            try:
                return issubclass(field_type, BaseModel)
            except TypeError:
                return False

        def is_list_of_models(field_type: Any) -> bool:
            origin = get_origin(field_type)
            args = get_args(field_type)
            return origin in (list, typing.List) and args and is_pydantic_model(args[0])
        
        errors = []
        values = {}
        is_valid = True
        info_loss = {}
        field_processed = set()
        


        # Handle both Pydantic BaseModel and OrderedDict cases
        if isinstance(model, dict):  # OrderedDict is a dict
            model_fields = list(model.items())
            is_ordered_dict = True
        else:  # Pydantic BaseModel
            model_fields = [(field, field_info) for field, field_info in model.model_fields.items()]
            
            # Check if model has __ordered_fields__ but no regular model fields
            if not model_fields and hasattr(model, '__ordered_fields__') and isinstance(model.__ordered_fields__, OrderedDict):
                # Create FieldInfo-like objects for __ordered_fields__
                from pydantic import Field
                from pydantic.fields import FieldInfo
                model_fields = []
                for field_name, field_type in model.__ordered_fields__.items():
                    # Create a minimal FieldInfo with the type annotation
                    field_info = FieldInfo(annotation=field_type, default=...)
                    model_fields.append((field_name, field_info))
                    
                # Create a dynamic model with the ordered fields as actual Pydantic fields
                dynamic_model_fields = {name: (typ, ...) for name, typ in model.__ordered_fields__.items()}
                original_ordered_fields = model.__ordered_fields__
                model = create_model(f"{model.__name__}Dynamic", **dynamic_model_fields)
                # Preserve the original __ordered_fields__ on the new model
                model.__ordered_fields__ = original_ordered_fields
            
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
            
            # Check if actual fields match expected order (only for fields that exist)
            if actual_field_order:
                # Filter out fields that don't exist in the model
                relevant_actual_fields = [f for f in actual_field_order if f in expected_field_order]
                # Get the expected order for these fields
                relevant_expected_fields = [f for f in expected_field_order if f in relevant_actual_fields]
                
                if relevant_actual_fields != relevant_expected_fields:
                    errors.append(f"Field order mismatch: expected order {relevant_expected_fields} but found {relevant_actual_fields}")
                    is_valid = False

        # Check if model has __ordered_fields__ and process them in order
        if not is_ordered_dict and hasattr(model, '__ordered_fields__') and isinstance(model.__ordered_fields__, OrderedDict):
            # For ordered fields, track document positions to ensure proper ordering
            last_selected_position = -1
            
            # Process ordered fields first
            for field, field_type in model.__ordered_fields__.items():
                if permissive:
                    elems = self.find_all(tree, field)
                    # For string fields, filter out elements with nested content
                    if field_type is str:
                        elems = [elem for elem in elems if not self.has_nested(elem)]
                    
                    # For ordered fields, only consider elements that come after the last selected position
                    if last_selected_position >= 0:
                        html_text = str(tree)
                        valid_elems = []
                        for elem in elems:
                            elem_position = html_text.find(str(elem))
                            if elem_position > last_selected_position:
                                valid_elems.append(elem)
                        elems = valid_elems
                    
                    elem = elems[0] if elems else None
                else:
                    elem = self.find_element(tree, field)
                    # For string fields, ensure it's a leaf node
                    if elem and field_type is str and self.has_nested(elem):
                        elem = None

                if elem is None:
                    if is_optional(field_type):
                        values[field] = None
                        continue
                    errors.append(f"Missing <{field}>")
                    is_valid = False
                    continue

                # Update the last selected position for document ordering
                if elem is not None:
                    html_text = str(tree)
                    elem_position = html_text.find(str(elem))
                    if elem_position >= 0:
                        last_selected_position = elem_position + len(str(elem))

                # Recursive validation for nested models
                if is_pydantic_model(field_type):
                    nested_result = self.validate_permissive_recursive(elem, field_type) if permissive else self.validate_strict_recursive(elem, field_type)
                    if nested_result.is_valid:
                        values[field] = nested_result.result_type
                    else:
                        errors.extend(nested_result.errors)
                        is_valid = False
                    continue

                # Type validation using get_text
                text_content = self.get_text(elem)
                
                # Handle Any type - capture full element
                if field_type is Any:
                    values[field] = self.get_subtree_string(elem)
                    continue

                # Type conversion for specific types
                if hasattr(self, 'type_matcher'):
                    match_result = self.type_matcher.validate_and_convert(text_content, field_type)
                    if match_result.is_valid:
                        values[field] = match_result.value
                        if match_result.info_loss:
                            info_loss[field] = match_result.info_loss
                    else:
                        errors.append(f"Type conversion error for <{field}>: {match_result.error}")
                        is_valid = False
                        continue
                else:
                    # Fallback to simple assignment for basic types
                    values[field] = text_content

            # Mark ordered fields as processed
            for field in model.__ordered_fields__.keys():
                field_processed.add(field)
        else:
            # Regular processing for non-ordered fields
            for field, field_info_or_type in model_fields:
                if is_ordered_dict:
                    expected_type = field_info_or_type  # For OrderedDict, it's directly the type
                else:
                    expected_type = field_info_or_type.annotation  # For BaseModel, it's field_info.annotation
                if permissive:
                    elems = self.find_all(tree, field)
                    # For string fields, filter out elements with nested content
                    if expected_type is str:
                        elems = [elem for elem in elems if not self.has_nested(elem)]
                    elem = elems[0] if elems else None
                else:
                    elem = self.find_element(tree, field)
                    # For string fields, ensure it's a leaf node
                    if elem and expected_type is str and self.has_nested(elem):
                        elem = None

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

                # Special handling for str and Any - HTML-specific logic
                if expected_type is str:
                    # For HTML, allow nested structure and use custom extraction
                    value = self.extract_html_text_for_string_field(elem, field)
                    if value is None:
                        errors.append(f"Field {field}: Unable to extract text content.")
                        is_valid = False
                        values[field] = None
                    else:
                        values[field] = value
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
                if is_ordered_dict:
                    # For OrderedDict, preserve the original field order
                    model_instance = OrderedDict()
                    for field, _ in model_fields:
                        if field in values:
                            model_instance[field] = values[field]
                else:
                    # For BaseModel with __ordered_fields__, create model instance but also 
                    # populate the __ordered_fields__ with the extracted values
                    model_instance = model(**values)
                    
                    # If model has __ordered_fields__, make sure the values are accessible as attributes
                    if hasattr(model, '__ordered_fields__') and isinstance(model.__ordered_fields__, OrderedDict):
                        for field_name in model.__ordered_fields__.keys():
                            if field_name in values and not hasattr(model_instance, field_name):
                                # Dynamically set the attribute if it doesn't exist
                                setattr(model_instance, field_name, values[field_name])
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



