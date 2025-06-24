import json
import re
from pydantic import BaseModel, create_model
from .document_structure_validator import DocumentStructureValidator, TextAroundPayloadError, InvalidPayloadError
from ....base import ValidationResult
from .utils import import_model_from_path

class JSONStructureValidator(DocumentStructureValidator):
    """Validates if the JSON matches a given Pydantic model structure."""
    def __init__(self, model: BaseModel = None, model_name: str = None, schema: dict = None, strict: bool = True, model_module: str = "models", generate_hints: bool = False):
        if model is not None:
            resolved_model = model
        elif model_name is not None:
            resolved_model = import_model_from_path(model_name, default_module=model_module)
        elif schema is not None:
            resolved_model = create_model("JSONStructureModel", **schema)
        else:
            resolved_model = None
        super().__init__(model=resolved_model, strict=strict, generate_hints=generate_hints)

    @classmethod
    def name(cls) -> str:
        return "json_structure"
    
    @classmethod
    def file_type(cls) -> str:
        return "json"

    @property
    def initial_hint(self) -> str:
        if self.model is not None:
            structure_lines = self._describe_structure(self.model)
            return (
                "Please ensure the JSON matches the required structure.\n"
                "Expected structure:\n"
                + '\n'.join(structure_lines)
            )
        else:
            return "Please return only valid JSON, with no explanation or extra text. The response must be a single JSON object or array."    
    
    def extract_payload(self, response: str) -> str:
        match = re.search(r'({[\s\S]*})|\[[\s\S]*\]', response)
        return match.group(0) if match else None

    def load_payload(self, payload: str) -> any:
        return json.loads(payload)

    def find_element(self, tree, key):
        # Only direct children for strict mode
        if isinstance(tree, dict):
            return tree.get(key)
        return None

    def get_text(self, element):
        # For JSON, leaf nodes are primitives
        if isinstance(element, (str, int, float, bool, list, dict)) or element is None:
            return element
        return None

    def has_nested(self, element):
        # True if element is a dict (object) or list (array) and not a primitive
        return isinstance(element, (dict, list))

    def iter_direct_children(self, tree):
        if isinstance(tree, dict):
            for k, v in tree.items():
                yield v
        elif isinstance(tree, list):
            for item in tree:
                yield item

    def get_name(self, element):
        # Not used for JSON, but for dict children, we need the key
        # This is handled in iter_direct_children by yielding values only
        return None

    def find_all(self, tree, key):
        # Recursively find all values for a given key in the tree
        found = []
        def _find_all(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k == key:
                        found.append(v)
                    _find_all(v)
            elif isinstance(obj, list):
                for item in obj:
                    _find_all(item)
        _find_all(tree)
        return found

    def get_subtree_string(self, elem):
        return json.dumps(elem, ensure_ascii=False, separators=(',', ':'))
    
    def _describe_structure(self, model, indent=0):
        lines = []
        prefix = '  ' * indent
        
        for field, field_info in model.model_fields.items():
            submodel = field_info.annotation
            
            if hasattr(submodel, "model_fields"):
                lines.append(f'{prefix}"{field}": {{')
                lines.extend(self._describe_structure(submodel, indent + 1))
                lines.append(f"{prefix}}}")
            else:
                lines.append(f'{prefix}"{field}": ...')
        
        return lines
