import xml.etree.ElementTree as ET
from pydantic import BaseModel, create_model
import re
from .document_structure_validator import DocumentStructureValidator, TextAroundPayloadError
from .utils import import_model_from_path

class XMLStructureValidator(DocumentStructureValidator):
    """Validates if the XML matches a given Pydantic model structure."""
    def __init__(self, model: BaseModel = None, model_name: str = None, schema: dict = None, strict: bool = True, model_module: str = "models", generate_hints: bool = False):
        if model is not None:
            resolved_model = model
        elif model_name is not None:
            resolved_model = import_model_from_path(model_name, default_module=model_module)
        elif schema is not None:
            resolved_model = create_model("XMLStructureModel", **schema)
        else:
            resolved_model = None
        super().__init__(model=resolved_model, strict=strict, generate_hints=generate_hints)

    @classmethod
    def name(cls) -> str:
        return "xml_structure"

    @classmethod
    def file_type(cls) -> str:
        return "xml"

    @property
    def initial_hint(self) -> str:
        if self.model is not None:
            structure_lines = self._describe_structure(self.model)
            return (
                "Please ensure the XML matches the required structure.\n"
                "Expected structure:\n"
                + '\n'.join(structure_lines)
            )
        else:
            return "Please return only valid XML, with no explanation or extra text."
    
    def extract_payload(self, response: str) -> str:
        markdown_match = re.search(r'```(?:xml)?\s*\n?(.*?)\n?```', response, re.DOTALL | re.IGNORECASE)
        if markdown_match:
            return markdown_match.group(1).strip()
        else:
            lines = response.split('\n')
            xml_lines = []
            for line in lines:
                line = line.strip()
                # Look for lines that contain XML-like content
                if line.startswith('<') and '>' in line:
                    xml_lines.append(line)
            
            if xml_lines:
                xml_candidate = ''.join(xml_lines)
                try:
                    ET.fromstring(xml_candidate)
                except ET.ParseError:
                    return None
                
                return xml_candidate

    def load_payload(self, payload: str) -> any:
        return ET.fromstring(payload)

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
                lines.append(f'{prefix}<{field}>...text...</{field}>')
        return lines 