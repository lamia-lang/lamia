import xml.etree.ElementTree as ET
from pydantic import BaseModel, create_model
from .document_structure_validator import DocumentStructureValidator
from .utils import import_model_from_path, describe_model_structure

class XMLStructureValidator(DocumentStructureValidator):
    """Validates if the XML matches a given Pydantic model structure."""
    def __init__(self, model: BaseModel = None, model_name: str = None, schema: dict = None, strict: bool = True, model_module: str = "models"):
        if model is not None:
            resolved_model = model
        elif model_name is not None:
            resolved_model = import_model_from_path(model_name, default_module=model_module)
        elif schema is not None:
            resolved_model = create_model("XMLStructureModel", **schema)
        else:
            resolved_model = None
        super().__init__(model=resolved_model, strict=strict)

    @classmethod
    def name(cls) -> str:
        return "xml_structure"

    @property
    def initial_hint(self) -> str:
        structure_lines = describe_model_structure(self.model, format_type="xml")
        return (
            "Please ensure the XML matches the required structure.\n"
            "Expected structure:\n"
            + '\n'.join(structure_lines)
        )

    def parse(self, response: str):
        return ET.fromstring(response)

    def find_element(self, tree, key):
        # Only direct children
        for child in tree:
            if child.tag == key:
                return child
        return None

    def get_text(self, element):
        if element is not None:
            if not element.text:
                return element
            else:
                text = element.text.strip()
                print(element, text)
                # Try int
                try:
                    return int(text)
                except ValueError:
                    pass
                # Try float
                try:
                    return float(text)
                except ValueError:
                    pass
                # Try bool
                lower = text.lower()
                if lower == 'true':
                    return True
                if lower == 'false':
                    return False
                return text
        return None

    def has_nested(self, element):
        return len(element) > 0

    def iter_direct_children(self, tree):
        return iter(tree)

    def get_name(self, element):
        return element.tag

    def find_all(self, tree, key):
        return tree.findall(f'.//{key}')

    def get_subtree_string(self, elem):
        return ET.tostring(elem, encoding='unicode') 