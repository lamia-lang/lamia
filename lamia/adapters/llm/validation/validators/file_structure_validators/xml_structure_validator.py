import xml.etree.ElementTree as ET
import importlib
from pydantic import BaseModel, create_model
from .document_structure_validator import DocumentStructureValidator

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
    lines = []
    prefix = '  ' * indent
    for field, field_info in model.model_fields.items():
        submodel = field_info.annotation
        if hasattr(submodel, "model_fields"):
            lines.append(f'{prefix}<{field}>')
            lines.extend(describe_model_structure(submodel, indent + 1))
            lines.append(f"{prefix}</{field}>")
        else:
            lines.append(f'{prefix}<{field}>...text...</{field}>')
    return lines

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
            raise ValueError("XMLStructureValidator requires a Pydantic model, model_name, or a schema dict.")
        super().__init__(model=resolved_model, strict=strict)

    @classmethod
    def name(cls) -> str:
        return "xml_structure"

    @property
    def initial_hint(self) -> str:
        structure_lines = describe_model_structure(self.model)
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
        return element.text.strip() if element is not None and element.text else None

    def has_nested(self, element):
        return len(element) > 0

    def iter_direct_children(self, tree):
        return iter(tree)

    def get_name(self, element):
        return element.tag

    def find_all(self, tree, key):
        return tree.findall(f'.//{key}') 