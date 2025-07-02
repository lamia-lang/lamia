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
     