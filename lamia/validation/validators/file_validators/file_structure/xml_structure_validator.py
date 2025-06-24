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
        structure_lines = describe_model_structure(self.model, format_type="xml")
        return (
            "Please ensure the XML matches the required structure.\n"
            "Expected structure:\n"
            + '\n'.join(structure_lines)
        )

    def parse(self, response: str):
        stripped = response.strip()
        
        if not self.strict:
            # Strategy 1: Try markdown code blocks first
            markdown_match = re.search(r'```(?:xml)?\s*\n?(.*?)\n?```', stripped, re.DOTALL | re.IGNORECASE)
            if markdown_match:
                xml_candidate = markdown_match.group(1).strip()
                try:
                    return ET.fromstring(xml_candidate)
                except ET.ParseError:
                    pass  # Continue to next strategy
            
            # Strategy 2: Extract any content that looks like XML
            lines = stripped.split('\n')
            xml_lines = []
            for line in lines:
                line = line.strip()
                # Look for lines that contain XML-like content
                if line.startswith('<') and '>' in line:
                    xml_lines.append(line)
            
            if xml_lines:
                xml_candidate = ''.join(xml_lines)
                try:
                    return ET.fromstring(xml_candidate)
                except ET.ParseError:
                    pass  # Continue to next strategy
            
            # Strategy 3: Try the whole thing (fallback)
            try:
                return ET.fromstring(stripped)
            except ET.ParseError:
                pass
            
            # If nothing worked, raise error
            raise TextAroundPayloadError(
                validator_class_name="XML",
                original_text=response,
                parsed_text=stripped
            )
        else:
            # Strict mode: parse as-is
            try:
                return ET.fromstring(stripped)
            except ET.ParseError as e:
                raise TextAroundPayloadError(
                    validator_class_name="XML",
                    original_text=response,
                    parsed_text=stripped
                ) from e

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