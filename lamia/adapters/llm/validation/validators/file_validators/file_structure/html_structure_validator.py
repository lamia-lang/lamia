from pydantic import BaseModel, create_model
from bs4 import BeautifulSoup
import re
from .document_structure_validator import DocumentStructureValidator
from ....base import ValidationResult
from .utils import import_model_from_path, describe_model_structure

class HTMLStructureValidator(DocumentStructureValidator):
    """Validates if the HTML matches a given Pydantic model structure.
    - Accepts a Pydantic model class or a string (model name or full dotted path).
    - Can be used from config (with model name or full path) or from Lamia(...) constructor (with model class).
    """
    def __init__(self, model: BaseModel = None, model_name: str = None, schema: dict = None, strict: bool = True, model_module: str = "models"):
        if model is not None:
            resolved_model = model
            self._structure_check_enabled = True
        elif model_name is not None:
            resolved_model = import_model_from_path(model_name, default_module=model_module)
            self._structure_check_enabled = True
        elif schema is not None:
            resolved_model = create_model("HTMLStructureModel", **schema)
            self._structure_check_enabled = True
        else:
            resolved_model = None
            self._structure_check_enabled = False
        super().__init__(model=resolved_model, strict=strict)

    @classmethod
    def name(cls) -> str:
        return "html_structure"

    @property
    def initial_hint(self) -> str:
        if self._structure_check_enabled:
            structure_lines = describe_model_structure(self.model, format_type="html")
            return (
                "Please ensure the HTML matches the required structure.\n" +
                "Expected structure:\n" +
                '\n'.join(structure_lines)
            )
        else:
            return "Please return only the HTML code, starting with <html> and ending with </html>, with no explanation or extra text."

    def parse(self, response: str):
        stripped = response.strip()
        if self.strict:
            html_block = stripped
        else:
            # Permissive: extract first <html>...</html> block
            match = re.search(r'(<html[\s\S]*?</html>)', stripped, re.IGNORECASE)
            if not match:
                raise ValueError("No valid <html>...</html> block found.")
            html_block = match.group(1)
        # Always check for well-formed HTML
        soup = BeautifulSoup(html_block, "html.parser")
        if not soup.html:
            raise ValueError("No <html> tag found or HTML is malformed.")
        return soup

    def find_element(self, tree, key):
        # Only direct children
        for child in tree.children:
            if getattr(child, 'name', None) == key:
                return child
        return None

    def get_text(self, element):
        return element.get_text(strip=True) if element else None

    def has_nested(self, element):
        # Returns True if there are any tag children
        return any(getattr(child, 'name', None) for child in element.children)

    def iter_direct_children(self, tree):
        return (child for child in tree.children if getattr(child, 'name', None))

    def get_name(self, element):
        return getattr(element, 'name', None)

    def find_all(self, tree, key):
        return tree.find_all(key)

    # Overrides the base class method to add the <html> tag to the tree
    # TODO: Can be done by adding html field to the model, but this is a good demonstration that base class can be overridden
    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        try:
            tree = self.parse(response)
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid file: {e}",
                hint=self.initial_hint
            )
        # If the root has an <html> element, start validation from there
        html_elem = self.find_element(tree, "html")
        if html_elem is not None:
            tree = html_elem
        else:
            return ValidationResult(
                is_valid=False,
                error_message="No <html> tag found",
                hint=self.initial_hint
            )
        valid, err = self.validate_strict_recursive(tree, self.model)
        if not valid:
            return ValidationResult(
                is_valid=False,
                error_message=f"Strict validation failed: {err}",
                hint=self.initial_hint
            )
        return ValidationResult(is_valid=True)

    # Overrides the base class method to add the <html> tag to the tree
    # TODO: Can be done by adding html field to the model, but this is a good demonstration that base class can be overridden
    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        try:
            tree = self.parse(response)
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid file: {e}",
                hint=self.initial_hint
            )
        # If the root has an <html> element, start validation from there
        html_elem = self.find_element(tree, "html")
        if html_elem is not None:
            tree = html_elem
        else:
            return ValidationResult(
                is_valid=False,
                error_message="No <html> tag found",
                hint=self.initial_hint
            )
        valid, err = self.validate_permissive_recursive(tree, self.model)
        if not valid:
            return ValidationResult(
                is_valid=False,
                error_message=f"Permissive validation failed: {err}",
                hint=self.initial_hint
            )
        return ValidationResult(is_valid=True) 