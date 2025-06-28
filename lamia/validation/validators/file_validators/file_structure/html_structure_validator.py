from pydantic import BaseModel, create_model
from bs4 import BeautifulSoup
import re
from .document_structure_validator import DocumentStructureValidator, TextAroundPayloadError
from ....base import ValidationResult
from .utils import import_model_from_path
from typing import Any
from .document_structure_validator import InvalidPayloadError
import json

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
            if self.strict:
                return (
                    "Please ensure the HTML matches the required structure exactly.\n" +
                    "Expected structure (as direct children under <html>):\n" +
                    '\n'.join(structure_lines) + "\n" +
                    json_schema_str
                )
            else:
                return (
                    "Please ensure the HTML contains the required fields somewhere in the structure.\n" +
                    "The fields can be nested within other HTML elements like <body>, <div>, etc.\n" +
                    "Required fields that must be present somewhere under <html> root tags:\n" +
                    '\n'.join(structure_lines) + "\n" +
                    json_schema_str
                )
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
            match = re.search(r'<html', payload, re.IGNORECASE)
            if not match:
                raise InvalidPayloadError(
                    expected_file_format=self.file_type(),
                    text=payload,
                )
            else:
                raise TextAroundPayloadError(
                    expected_file_format=self.file_type(),
                    original_text=payload,
                    payload_text=match.group(0)
                )
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

