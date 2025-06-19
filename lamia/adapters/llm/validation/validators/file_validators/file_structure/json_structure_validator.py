import json
from pydantic import BaseModel, create_model
from .document_structure_validator import DocumentStructureValidator
from ....base import ValidationResult
from .utils import import_model_from_path, describe_model_structure

class JSONStructureValidator(DocumentStructureValidator):
    """Validates if the JSON matches a given Pydantic model structure."""
    def __init__(self, model: BaseModel = None, model_name: str = None, schema: dict = None, strict: bool = True, model_module: str = "models"):
        if model is not None:
            resolved_model = model
            self._structure_check_enabled = True
        elif model_name is not None:
            resolved_model = import_model_from_path(model_name, default_module=model_module)
            self._structure_check_enabled = True
        elif schema is not None:
            resolved_model = create_model("JSONStructureModel", **schema)
            self._structure_check_enabled = True
        else:
            resolved_model = None
            self._structure_check_enabled = False
        super().__init__(model=resolved_model, strict=strict)

    @classmethod
    def name(cls) -> str:
        return "json_structure"

    @property
    def initial_hint(self) -> str:
        if self._structure_check_enabled:
            structure_lines = describe_model_structure(self.model, format_type="json")
            return (
                "Please ensure the JSON matches the required structure.\n"
                "Expected structure:\n"
                + '\n'.join(structure_lines)
            )
        else:
            return "Please return only valid JSON, with no explanation or extra text. The response must be a single JSON object or array."

    def parse(self, response: str):
        import re
        stripped = response.strip()
        if self.strict:
            # Strict: must be only the JSON document
            try:
                return json.loads(stripped)
            except Exception as e:
                raise ValueError(f"Invalid JSON: {e}")
        else:
            # Permissive: extract first JSON object or array
            match = re.search(r'({[\s\S]*})|\[([\s\S]*)\]', stripped)
            if not match:
                raise ValueError("No valid JSON object or array found.")
            json_block = match.group(0)
            try:
                return json.loads(json_block)
            except Exception as e:
                raise ValueError(f"Invalid JSON: {e}")

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
        import json
        return json.dumps(elem, ensure_ascii=False, separators=(',', ':'))
