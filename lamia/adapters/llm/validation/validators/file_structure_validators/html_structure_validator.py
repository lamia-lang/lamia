from pydantic import BaseModel, create_model
from bs4 import BeautifulSoup
import importlib
import re
from .document_structure_validator import DocumentStructureValidator
from ...base import ValidationResult

def import_model_from_path(path: str, default_module: str = "models"):
    if "." in path:
        parts = path.split('.')
        module_path = '.'.join(parts[:-1])
        class_name = parts[-1]
        mod = importlib.import_module(module_path)
        return getattr(mod, class_name)
    else:
        mod = importlib.import_module(default_module)
        return getattr(mod, path)

def describe_model_structure(model, indent=0):
    """Recursively describe the expected HTML structure from a Pydantic model."""
    lines = []
    prefix = '  ' * indent
    for field, field_info in model.model_fields.items():
        submodel = field_info.annotation
        if hasattr(submodel, "model_fields"):
            lines.append(f"{prefix}<{field}>")
            lines.extend(describe_model_structure(submodel, indent + 1))
            lines.append(f"{prefix}</{field}>")
        else:
            lines.append(f"{prefix}<{field}>...text...</{field}>")
    return lines

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
            structure_lines = describe_model_structure(self.model)
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
            # Strict: must be only the HTML document
            if not (stripped.lower().startswith("<html") and stripped.lower().endswith("</html>")):
                raise ValueError("Response does not start with <html> and end with </html>.")
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

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        return await super().validate_strict(response, **kwargs)

    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        return await super().validate_permissive(response, **kwargs) 