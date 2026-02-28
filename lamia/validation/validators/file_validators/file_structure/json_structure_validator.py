import json
import re
from collections import OrderedDict
from typing import Optional, Type, Any

from pydantic import BaseModel, create_model

from .document_structure_validator import DocumentStructureValidator, DuplicateKeyError
from .utils import import_model_from_path


class JSONStructureValidator(DocumentStructureValidator):
    """Validates if the JSON matches a given Pydantic model structure."""
    def __init__(self, model: Optional[Type[BaseModel]] = None, model_name: Optional[str] = None, schema: Optional[dict] = None, strict: bool = True, model_module: str = "models", generate_hints: bool = False):
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
        # Handle case where no model is provided (regular JSON validation)
        if self.model is None:
            return "Please return only valid json, with no explanation or extra text."
        
        # Generate clean JSON structure with proper object formatting
        structure_lines = self._describe_structure(self.model, strict_mode=self.strict)
        json_structure = "{\n" + '\n'.join(f"  {line}" for line in structure_lines) + "\n}"
        
        schema_hint = self._get_model_schema_hint()
        # Fix case sensitivity for json vs JSON
        if self.strict:
            schema_hint = schema_hint.replace("JSON format to be extracted from the JSON:", "json format to be extracted from the JSON:")
        
        # Add clean ordering information only for models with ordered fields
        from ....utils.pydantic_utils import get_ordered_dict_fields
        ordering_hint = ""
        if get_ordered_dict_fields(self.model):
            ordering_hint = self._generate_field_ordering_hint(self.model)
        
        if self.strict:
            base_hint = (
                "Please ensure the json matches the required structure exactly.\n"
                "Expected structure:\n"
                f"{json_structure}\n"
                f"{schema_hint}"
            )
        else:
            base_hint = (
                "Please ensure the JSON contains the required fields with the correct types.\n"
                "The fields can be nested within other JSON objects.\n"
                "Required fields that must be present:\n"
                f"{json_structure}\n"
                f"{schema_hint}"
            )
        
        # Add ordering hint if present
        if ordering_hint:
            return base_hint + "\n\n" + ordering_hint
        return base_hint

    def extract_payload(self, response: str) -> str:
        match = re.search(r'({[\s\S]*})|\[[\s\S]*\]', response)
        return match.group(0) if match else None

    def load_payload(self, payload: str) -> Any:
        def _reject_duplicates(pairs: list) -> OrderedDict:
            obj: OrderedDict = OrderedDict()
            for k, v in pairs:
                if k in obj:
                    raise DuplicateKeyError(k, filetype="JSON object")
                obj[k] = v
            return obj

        return json.loads(payload, object_pairs_hook=_reject_duplicates)

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

    def get_field_order(self, tree):
        """Get the order of keys as they appear in the JSON object."""
        if isinstance(tree, dict):
            return list(tree.keys())
        return []
    
    def _describe_structure(self, model, indent=0, strict_mode=True):
        lines = []
        prefix = '  ' * indent
        
        field_items = list(model.model_fields.items())
        for i, (field, field_info) in enumerate(field_items):
            submodel = field_info.annotation
            is_last = (i == len(field_items) - 1)
            comma = "" if is_last else ","
            
            if hasattr(submodel, "model_fields"):
                lines.append(f'{prefix}"{field}": {{')
                lines.extend(self._describe_structure(submodel, indent + 1, strict_mode))
                lines.append(f'{prefix}}}{comma}')
            else:
                lines.append(f'{prefix}"{field}": ...{comma}')
        
        return lines
